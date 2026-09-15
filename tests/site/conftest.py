"""Serve site/ on a free port and hand every test a page.

The Supabase Storage copy is stubbed with the committed data/live.json, so the
suite never depends on the network or on what today's numbers happen to be.
"""
import json
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
LIVE_JSON = ROOT / "data" / "live.json"
STORAGE = "**/storage/v1/object/public/public/live.json"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):        # the suite is noisy enough
        pass


@pytest.fixture(scope="session")
def base_url():
    # The Pages workflow bakes these two; a local run has to do it itself.
    (SITE / "data").mkdir(exist_ok=True)
    (SITE / "data" / "live.json").write_bytes(LIVE_JSON.read_bytes())
    eps = SITE / "img" / "episodes"
    (eps / "index.json").write_text(json.dumps(sorted(p.stem for p in eps.glob("*.jpg"))), encoding="utf-8")

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def live_data():
    return json.loads(LIVE_JSON.read_text(encoding="utf-8"))


def _stub_storage(pg):
    pg.route(STORAGE, lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=LIVE_JSON.read_text(encoding="utf-8")))


@pytest.fixture(params=[(1440, 900), (390, 844)], ids=["desktop", "phone"])
def page(request, browser, base_url):
    w, h = request.param
    ctx = browser.new_context(viewport={"width": w, "height": h})
    pg = ctx.new_page()
    _stub_storage(pg)
    yield pg
    ctx.close()


@pytest.fixture
def desktop(browser, base_url):
    """One desktop page, for the checks that do not vary by viewport."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    _stub_storage(pg)
    yield pg
    ctx.close()
