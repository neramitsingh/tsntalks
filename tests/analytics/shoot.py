"""Screenshots of the six tabs on the committed fixtures, for review.
Run: python tests/analytics/shoot.py  (from the repo root; uses the same stubs as the suite).

Everything here is what the `dashboard` fixture in conftest.py does, minus pytest:
the same static server over site/, the same Supabase stub, the same sign-in."""
import socket
import sys
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "analytics"))

from playwright.sync_api import sync_playwright  # noqa: E402

from conftest import ANALYTICS, DEFAULT_TIMEOUT, SITE, QuietHandler, Supabase, sign_in  # noqa: E402
from test_tabs import open_tab  # noqa: E402

OUT = ROOT / "docs" / "superpowers" / "plans" / "plan-4-shots"
TABS = ["overview", "growth", "posts", "episodes", "audience", "health"]


def serve_site():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(SITE)))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    httpd, base_url = serve_site()
    stub = Supabase()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # accept_downloads and the timeout mirror conftest's _context(), so a
        # slow box takes longer rather than shooting a half-drawn tab.
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  accept_downloads=True)
        ctx.set_default_timeout(DEFAULT_TIMEOUT)
        page = ctx.new_page()
        stub.install(page)
        sign_in(page)
        page.goto(base_url + ANALYTICS)
        page.wait_for_selector("#shell:not([hidden])")
        for tab in TABS:
            open_tab(page, tab)
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"{tab}.png"), full_page=True)
            print("shot", tab)
        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
