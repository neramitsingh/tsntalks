import sys
from pathlib import Path

import pytest

PAGES = ["/", "/live/", "/partner/"]
NAMES = {"/": "home", "/live/": "live", "/partner/": "partner"}
SHOTS = Path(__file__).parent / "shots"

# An element may legitimately stick out of the viewport when some ancestor scrolls
# horizontally — the nav strip and the column chart both do. Walk up, do not stop
# at the parent.
OVERFLOW_JS = """() => {
  const w = document.documentElement.clientWidth;
  const scrolls = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
    }
    return false;
  };
  return [...document.querySelectorAll('body *')]
    .filter((el) => el.getBoundingClientRect().right > w + 1 && !scrolls(el))
    .map((el) => `${el.tagName}.${el.className}`).slice(0, 5);
}"""


@pytest.mark.parametrize("path", PAGES)
def test_no_horizontal_overflow(page, base_url, path):
    page.goto(base_url + path, wait_until="networkidle")
    page.wait_for_timeout(400)
    assert page.evaluate(OVERFLOW_JS) == []
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


@pytest.mark.parametrize("path", PAGES)
def test_no_console_or_page_errors(page, base_url, path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(base_url + path, wait_until="networkidle")
    page.wait_for_timeout(800)
    assert errors == []


@pytest.mark.parametrize("path", PAGES)
def test_display_and_text_fonts_load(page, base_url, path):
    page.goto(base_url + path, wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.evaluate("document.fonts.check('600 48px \"Bodoni Moda\"')")
    assert page.evaluate("document.fonts.check('500 16px \"Hanken Grotesk\"')")


# --- the numbers on the page are the numbers in live.json --------------------

def test_home_hero_is_the_newest_episode(desktop, base_url, live_data):
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    newest = max(live_data["episodes"], key=lambda e: e["published_at"])
    assert desktop.inner_text("#guest").strip() == newest["guest"]
    assert desktop.get_attribute("#watch", "href") == newest["url"]


def test_home_strap_carries_the_real_totals(desktop, base_url, live_data):
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    strap = desktop.inner_text("#strap")
    assert f"{live_data['total_views']:,}" in strap
    assert f"{live_data['total_followers']:,}" in strap
    assert f"{len(live_data['episodes'])} episodes" in strap


def test_every_episode_has_a_date_and_a_role(live_data):
    """The page cannot order or label episodes honestly without these."""
    missing_date = [e["guest"] for e in live_data["episodes"] if not e["published_at"]]
    missing_role = [e["guest"] for e in live_data["episodes"] if not e["role"]]
    assert missing_date == []
    assert missing_role == []


def test_episodes_arrive_newest_first(live_data):
    dates = [e["published_at"] for e in live_data["episodes"]]
    assert dates == sorted(dates, reverse=True)


def test_season_one_index_is_complete(desktop, base_url, live_data):
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    roles = desktop.eval_on_selector_all("#s1 li small", "els => els.map(e => e.textContent.trim())")
    assert len(roles) == sum(1 for e in live_data["episodes"] if e["season"] == 1)
    assert all(roles)


def test_poster_wall_has_one_big_and_two_mid(desktop, base_url):
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    assert desktop.locator("#wall .po.big").count() == 1
    assert desktop.locator("#wall .po.mid").count() == 2


def test_live_chart_has_a_table_twin_with_the_same_months(desktop, base_url, live_data):
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    months = len({r["m"] for r in live_data["months"]})
    assert desktop.locator("#cols .col").count() == months
    assert desktop.locator("#monthstab tr").count() - 1 == months


def test_live_legend_totals_match_the_data(desktop, base_url, live_data):
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    text = desktop.inner_text("#legend")
    for p in live_data["platforms"].values():
        assert f"{p['views']:,}" in text
        assert f"{p['followers']:,}" in text


def _baht(n):
    return f"฿{n:,}"


def test_partner_carries_no_live_numbers(desktop, base_url, pricing):
    """Prices are editorial. They must be readable with JS off and greppable by Sunny.

    Baked from data/pricing.json by infra/build_pricing.py — so this asserts the
    page carries every figure the rate card names, whatever those figures become.
    """
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    html = desktop.content()
    assert "live-data" not in html
    for t in pricing["tiers"]:
        assert _baht(t["amount"]) in html, t["id"]
        for o in t.get("options", []):
            assert _baht(o["amount"]) in html, f'{t["id"]}/{o["name"]}'
    for b in pricing["bundles"]:
        assert _baht(b["amount"]) in html, b["id"]
        assert _baht(b["regular"]) in html, f'{b["id"]} regular'
        assert f'{b["reach"]:,} guaranteed reach' in html, f'{b["id"]} reach'


def test_prices_survive_javascript_being_off(browser, base_url, pricing):
    """The rate card is the money page. It may not depend on a script running."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, java_script_enabled=False)
    pg = ctx.new_page()
    for path in ("/", "/partner/"):
        pg.goto(base_url + path, wait_until="domcontentloaded")
        body = pg.inner_text("body")
        for t in pricing["tiers"]:
            assert _baht(t["amount"]) in body, f'{path} {t["id"]}'
    ctx.close()


def test_home_and_partner_quote_the_same_tier_prices(desktop, base_url, pricing):
    """One rate card, two pages. They came apart once; they cannot again."""
    seen = {}
    for path in ("/", "/partner/"):
        desktop.goto(base_url + path, wait_until="networkidle")
        prices = desktop.eval_on_selector_all(
            ".tiers .tier .p", "els => els.map(e => e.firstChild.textContent.trim())")
        seen[path] = prices
    assert seen["/"] == seen["/partner/"]
    assert seen["/"] == [_baht(t["amount"]) for t in pricing["tiers"]]


def test_pages_are_in_step_with_pricing_json():
    """The guard the Pages workflow runs, run here too so drift never reaches CI."""
    import subprocess
    r = subprocess.run([sys.executable, "infra/build_pricing.py", "--check"],
                       cwd=Path(__file__).resolve().parents[2],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_partner_footnotes_the_guaranteed_reach(desktop, base_url):
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    body = desktop.inner_text("body")
    assert "targets we underwrite, not" in body
    assert "measurements" in body


# --- behaviour ---------------------------------------------------------------

def test_reduced_motion_stops_every_animation(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(base_url + "/", wait_until="networkidle")
    pg.wait_for_timeout(800)
    running = pg.evaluate("""() => [...document.querySelectorAll('*')]
        .flatMap((el) => el.getAnimations({subtree: false}))
        .filter((a) => a.playState === 'running').length""")
    assert running == 0
    ctx.close()


def test_page_still_renders_when_storage_is_down(browser, base_url, live_data):
    """The baked copy is the whole point: a dead Storage must not blank the page."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.route("**/storage/v1/object/public/public/live.json", lambda r: r.abort())
    pg.goto(base_url + "/", wait_until="networkidle")
    pg.wait_for_timeout(800)
    assert pg.inner_text("#guest").strip() != ""
    assert f"{live_data['total_views']:,}" in pg.inner_text("#strap")
    ctx.close()


def test_stale_data_drops_the_live_dot(browser, base_url, live_data):
    import copy
    import json as _json
    old = copy.deepcopy(live_data)
    old["fetched_at"] = "2020-01-01T00:00:00+00:00"
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.route("**/data/live.json", lambda r: r.fulfill(
        status=200, content_type="application/json", body=_json.dumps(old)))
    pg.route("**/storage/v1/object/public/public/live.json", lambda r: r.fulfill(
        status=200, content_type="application/json", body=_json.dumps(old)))
    pg.goto(base_url + "/", wait_until="networkidle")
    pg.wait_for_timeout(800)
    assert pg.locator("#strap.stale").count() == 1
    assert pg.locator("#strap .live").count() == 0
    ctx.close()


@pytest.mark.parametrize("path", PAGES)
def test_screenshot(page, base_url, path):
    SHOTS.mkdir(exist_ok=True)
    page.goto(base_url + path, wait_until="networkidle")
    page.wait_for_timeout(900)
    size = "desk" if page.viewport_size["width"] > 800 else "mobile"
    page.screenshot(path=str(SHOTS / f"{NAMES[path]}-{size}.png"), full_page=True)
