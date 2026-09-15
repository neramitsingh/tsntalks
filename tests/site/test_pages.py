import sys
from pathlib import Path

import pytest

PAGES = ["/", "/live/", "/partner/"]
NAMES = {"/": "home", "/live/": "live", "/partner/": "partner"}
SHOTS = Path(__file__).parent / "shots"
ROOT = Path(__file__).resolve().parents[2]
LIVE_JSON = ROOT / "data" / "live.json"

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
    """document.fonts.check() answers true for a family the document has never
    heard of, so it cannot tell you a webfont arrived — the old version of this
    test passed just as happily with the display face deleted. Ask the font set
    what it actually loaded, and confirm the heading is rendered in it."""
    page.goto(base_url + path, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(700)
    loaded = page.evaluate(
        "[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)")
    assert "Antonio" in loaded, f"display face did not load: {sorted(set(loaded))}"
    assert "Hanken Grotesk" in loaded, f"text face did not load: {sorted(set(loaded))}"

    # And it is actually in use: a condensed 800 heading must not be measuring
    # the same as the fallback stack.
    assert page.evaluate("""() => {
      const h = document.querySelector('h1, h2');
      const cs = getComputedStyle(h);
      return cs.fontFamily.includes('Antonio')
          && cs.textTransform === 'uppercase'
          && Number(cs.fontWeight) >= 700;
    }""")


# --- the numbers on the page are the numbers in live.json --------------------

def test_home_hero_is_the_offer_and_the_room_shows_the_newest_episode(desktop, base_url, live_data):
    """The <h1> is the offer, not the week's guest — a heading that changed every
    episode announced a stranger's name as the page title. The room's photograph
    is a frame from the newest episode that has one in site/img/episodes/, and
    the caption names that guest. This assumes the newest episode has a still;
    when a new episode drops without one, this fails on purpose: extract it."""
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    newest = max(live_data["episodes"], key=lambda e: e["published_at"])
    assert desktop.inner_text("h1").strip().lower() == "put your brand in this room"
    assert newest["guest"] in desktop.inner_text("#herocap")
    assert desktop.get_attribute("#watch", "href") == newest["url"]
    src = desktop.get_attribute("#roomart img", "src") or ""
    assert src.endswith(f"/img/episodes/{newest['youtube_video_id']}.jpg"), src


def test_hero_quotes_the_entry_price_in_the_first_screen(desktop, base_url):
    """A sponsor arrives from a LINE link with seconds to spare. The floor price
    is generated from data/pricing.json, so it cannot drift from the rate card."""
    import json as _json
    pricing = _json.loads((ROOT / "data" / "pricing.json").read_text(encoding="utf-8"))
    floor = min(t["amount"] for t in pricing["tiers"])
    desktop.goto(base_url + "/", wait_until="networkidle")
    assert f"฿{floor:,}" == desktop.inner_text("#floor").strip()
    box = desktop.locator(".offer").bounding_box()
    assert box["y"] < 900, "the entry price must be in the first screen"


def test_no_text_is_printed_over_a_photograph(desktop, base_url):
    """The tell that made the old wall read as machine-made: the show bakes its
    headline and the guest's name into every thumbnail, so a caption laid over
    one collided with type already in the pixels — and an 11px platform-coloured
    kicker over a photo measured as low as 1.4:1. Captions sit below the image."""
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    overlapping = desktop.evaluate("""() => {
      const bad = [];
      for (const po of document.querySelectorAll('.po, .face')) {
        const img = po.querySelector('img'), cap = po.querySelector('.t');
        if (!img || !cap) continue;
        // a face tile zooms a fallback thumbnail inside an overflow-hidden box:
        // the visible photograph is that box, not the transformed <img>
        const frame = po.querySelector('.sq') || img;
        const a = frame.getBoundingClientRect(), b = cap.getBoundingClientRect();
        if (b.top < a.bottom - 1) bad.push(po.className);
      }
      return bad;
    }""")
    assert overlapping == []


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
    names = desktop.eval_on_selector_all("#s1 .face .g", "els => els.map(e => e.textContent.trim())")
    assert len(names) == sum(1 for e in live_data["episodes"] if e["season"] == 1)
    assert all(names)


@pytest.mark.parametrize("path", PAGES)
def test_no_image_is_stretched_out_of_its_own_aspect_ratio(desktop, base_url, path):
    """A width/height attribute pair defeats `aspect-ratio` unless `height: auto`
    is set, and the result is a silently distorted photograph. It happened twice:
    the founder portrait rendered 29% narrow, and the partner showreel cropped
    episode artwork mid-word. `contain` letterboxes and `cover` crops — both are
    deliberate and neither distorts. `fill`, the default, is the one that
    silently stretches a face, so that is what this catches."""
    desktop.goto(base_url + path, wait_until="networkidle")
    desktop.wait_for_timeout(900)
    desktop.evaluate("""async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 700) {
        window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60));
      }
      window.scrollTo(0, 0);
      await Promise.all([...document.images].filter(i => !i.complete)
        .map(i => new Promise(r => { i.onload = i.onerror = r; })));
    }""")
    desktop.wait_for_timeout(700)
    bad = desktop.evaluate("""() => {
      const out = [];
      for (const i of document.images) {
        if (!i.naturalWidth || i.naturalWidth < 3) continue;
        const cs = getComputedStyle(i);
        if (cs.objectFit !== 'fill') continue;   // contain/cover never distort
        const r = i.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) continue;
        const natural = i.naturalWidth / i.naturalHeight;
        const drawn = r.width / r.height;
        if (Math.abs(drawn - natural) / natural > 0.02) {
          out.push({ src: i.currentSrc.slice(-42), natural: +natural.toFixed(3),
                     drawn: +drawn.toFixed(3), fit: cs.objectFit });
        }
      }
      return out;
    }""")
    assert bad == [], f"images not rendering at their true aspect ratio: {bad}"


def test_the_room_strip_is_every_season_two_guest_newest_first(desktop, base_url, live_data):
    """Ranking tiles by view count guaranteed the biggest tile carried the biggest
    number and every tile after it visibly decayed — a deficit gradient, which is
    the one shape PRODUCT.md's first principle rules out. Newest first, no view
    counts on the tiles, and never a thumbnail with text printed over it."""
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    s2 = [e for e in live_data["episodes"] if e["season"] == 2]
    assert desktop.locator("#faces .face").count() == len(s2)
    order = desktop.eval_on_selector_all("#faces .face .g", "els => els.map(e => e.textContent)")
    by_date = [e["guest"] for e in sorted(s2, key=lambda e: e["published_at"], reverse=True)]
    assert order == by_date


def test_a_face_tile_never_ships_as_an_empty_box(desktop, base_url):
    """Each tile walks a chain — face crop, episode still, thumbnail — and only
    when every source has failed does it fall back to the initials on wood.
    Either way a visitor sees a face or a name, never a blank rectangle."""
    desktop.goto(base_url + "/", wait_until="networkidle")
    desktop.evaluate("""async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) {
        window.scrollTo(0, y); await new Promise(r => setTimeout(r, 80));
      }
      await Promise.all([...document.images].filter(i => !i.complete)
        .map(i => new Promise(r => { i.onload = i.onerror = r; })));
    }""")
    desktop.wait_for_timeout(800)
    blank = desktop.evaluate("""() => [...document.querySelectorAll('#faces .face, #s1 .face')]
      .filter(f => !f.classList.contains('nopic'))
      .filter(f => { const i = f.querySelector('img'); return !i || !i.complete || i.naturalWidth < 3; })
      .map(f => f.querySelector('.g').textContent)""")
    assert blank == [], blank


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


def test_partner_opens_on_a_fork_quoting_both_floors(desktop, base_url, pricing):
    """Ten prices in one column made every reader start at the wrong one. The
    page opens on two plates, one episode or a campaign, each quoting the
    cheapest price on its side, generated from pricing.json like every other
    figure. Both must be in the first screen."""
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    ep = desktop.inner_text("#fork-ep")
    camp = desktop.inner_text("#fork-camp")
    assert _baht(min(t["amount"] for t in pricing["tiers"])) in ep
    assert _baht(min(b["amount"] for b in pricing["bundles"])) in camp
    assert desktop.locator("#fork-camp").bounding_box()["y"] < 900
    assert desktop.get_attribute("#fork-ep", "href") == "#episode"
    assert desktop.get_attribute("#fork-camp", "href") == "#campaign"


def test_partner_reel_is_frames_from_the_room_not_thumbnails(desktop, base_url):
    """Every photograph on the site is a frame from an episode. The rate card
    used to show three YouTube thumbnails 'as published' — the one place the
    system's rule was broken, on the money page."""
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    srcs = desktop.eval_on_selector_all(".reel img", "els => els.map(e => e.currentSrc)")
    assert len(srcs) == 3
    for s in srcs:
        assert "/img/episodes/" in s and "ytimg" not in s, s
    loaded = desktop.eval_on_selector_all(".reel img", "els => els.map(e => e.complete && e.naturalWidth > 3)")
    assert all(loaded), loaded
    caps = desktop.eval_on_selector_all(".reel figcaption b", "els => els.map(e => e.textContent.trim())")
    assert all(caps)


def test_partner_campaigns_are_rows_on_one_plate(desktop, base_url, pricing):
    """Five identical bordered cards named Bundle A/B/C became rows on the same
    wood as the tiers: one column of prices to compare down, the flagship marked
    by a rule rather than a different card."""
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    rows = desktop.locator("#campaign .deal")
    assert rows.count() == len(pricing["bundles"])
    flags = desktop.locator("#campaign .deal.flag")
    assert flags.count() == sum(1 for b in pricing["bundles"] if b.get("flagship"))
    flagship = next(b for b in pricing["bundles"] if b.get("flagship"))
    assert _baht(flagship["amount"]) in flags.first.inner_text()
    terms = desktop.eval_on_selector_all("#campaign .deal .n", "els => els.map(e => e.textContent.trim())")
    assert terms == [b["term"] for b in pricing["bundles"]]
    # the tier rows carry a reply link that names the option in the subject
    asks = desktop.eval_on_selector_all("#episode .tier a.ask", "els => els.map(e => e.href)")
    assert len(asks) == len(pricing["tiers"])
    assert all(a.startswith("mailto:") and "subject=" in a for a in asks)


def test_the_reply_channel_becomes_line_on_every_page_when_the_link_exists(browser, base_url):
    """The sponsor arrived from a LINE thread. Until Sunny sends his link the
    buttons are mailto:; the moment contact.json carries it, every primary
    button on home and the rate card is LINE, from one shared module."""
    import json as _json
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    _stub = {"email": "x@example.com", "line": "https://lin.ee/abc123"}
    pg.route("**/data/contact.json", lambda r: r.fulfill(
        status=200, content_type="application/json", body=_json.dumps(_stub)))
    pg.route("**/storage/v1/object/public/public/live.json", lambda r: r.abort())
    for path in ("/", "/partner/"):
        pg.goto(base_url + path, wait_until="networkidle")
        pg.wait_for_timeout(500)
        for sel in ("#cta", "#cta2", "#navcta"):
            assert pg.get_attribute(sel, "href") == _stub["line"], f"{path} {sel}"
            assert "line" in (pg.get_attribute(sel, "class") or ""), f"{path} {sel}"
        # text_content, not inner_text: the button is uppercased by CSS
        assert pg.text_content("#cta").strip() == "Message us on LINE"
    ctx.close()


def test_the_reply_channel_stays_email_until_then(desktop, base_url):
    desktop.goto(base_url + "/partner/", wait_until="networkidle")
    desktop.wait_for_timeout(500)
    for sel in ("#cta", "#cta2", "#navcta"):
        assert (desktop.get_attribute(sel, "href") or "").startswith("mailto:"), sel


# --- /live in the same room ---------------------------------------------------

def test_live_leads_with_the_90_day_position(desktop, base_url, live_data):
    """Position, not deficit. The first figures on the page are the platform's
    rolling 90 days, in the same strap the home page uses, above the lifetime
    total — so the page says where the show is before what it has ever done."""
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    y = live_data["yt_90d"]
    strap = desktop.inner_text("#strap90")
    assert f"{y['views']:,}" in strap
    assert f"{round(y['minutes'] / 60):,}" in strap
    net = y["subs_gained"] - y["subs_lost"]
    assert f"{'+' if net >= 0 else ''}{net:,}" in strap
    assert desktop.locator("#strap90").bounding_box()["y"] < desktop.locator("#total").bounding_box()["y"]


def test_live_has_no_heading_level_skip(desktop, base_url):
    """live.js used to inject <h3>TikTok</h3> straight under the <h1>."""
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    levels = desktop.evaluate(
        "[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => Number(h.tagName[1]))")
    assert levels[0] == 1
    for a, b in zip(levels, levels[1:]):
        assert b <= a + 1, levels
    assert desktop.locator("#legend h3").count() == 0


def test_live_now_playing_is_the_second_section(desktop, base_url):
    """Sunny checks the page after an episode drops; the episode was fourth."""
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    heads = desktop.eval_on_selector_all("main > section .head h1, main > section .head h2",
                                         "els => els.map(e => e.textContent.trim().toLowerCase())")
    assert heads[1] == "now playing", heads


def test_live_names_the_post_that_carries_the_peak_month(desktop, base_url, live_data):
    """The tallest column reads as 'the show peaked' unless the page says it is
    one clip. When a platform's best post falls in the peak month and carries
    more than half of it, the note under the chart says so with the figures."""
    from collections import defaultdict
    totals = defaultdict(int)
    for r in live_data["months"]:
        totals[r["m"]] += r["views"]
    peak = max(totals, key=totals.get)
    carriers = [p["top"] for p in live_data["platforms"].values()
                if p["top"]["date"][:7] == peak and p["top"]["views"] * 2 > totals[peak]]
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    note = desktop.locator("#peaknote")
    if carriers:
        top = max(carriers, key=lambda t: t["views"])
        assert note.is_visible()
        text = note.inner_text()
        assert f"{top['views']:,}" in text and f"{totals[peak]:,}" in text
    else:
        assert not note.is_visible()


def test_live_now_playing_never_ships_a_blank_box_when_a_cover_expires(browser, base_url, live_data):
    """Instagram and TikTok covers are signed URLs that expire. The tile used to
    keep an empty <img> above its caption: a 300px blank box on desktop, 600px
    on a phone. When a cover fails the image goes and the caption stands."""
    covers = {p["top"]["thumb"] for p in live_data["platforms"].values() if p["top"].get("thumb")}
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.route(lambda url: url in covers, lambda r: r.abort())
    pg.route("**/storage/v1/object/public/public/live.json", lambda r: r.fulfill(
        status=200, content_type="application/json", body=LIVE_JSON.read_text(encoding="utf-8")))
    pg.goto(base_url + "/live/", wait_until="networkidle")
    pg.wait_for_timeout(1200)
    assert pg.locator("#top .po").count() == 4
    blank = pg.evaluate("""() => [...document.querySelectorAll('#top .po img')]
      .filter(i => i.complete && i.naturalWidth < 3).length""")
    assert blank == 0
    # every tile still carries its caption
    assert pg.locator("#top .po .g").count() == 4
    # and the best YouTube post, being an episode with a committed frame, shows
    # that frame rather than YouTube's own thumbnail
    import re as _re
    yt_id = _re.search(r"[?&]v=([\w-]{11})", live_data["platforms"]["youtube"]["top"]["url"]).group(1)
    if (ROOT / "site" / "img" / "episodes" / f"{yt_id}.jpg").exists():
        srcs = pg.eval_on_selector_all("#top .po img", "els => els.map(e => e.currentSrc)")
        assert any(s.endswith(f"/img/episodes/{yt_id}.jpg") for s in srcs), srcs
    ctx.close()


def test_live_shares_are_of_everyone_the_platform_placed(desktop, base_url, live_data):
    """A share computed over the six rows on show said Bangkok was 83% of
    Instagram; over everyone Instagram places in a city it is smaller, and that
    is the honest figure."""
    cities = live_data["demographics"]["ig_city"]
    placed = sum(c["value"] for c in cities)
    bkk = next(c for c in cities if c["dimension"].startswith("Bangkok"))
    want = f"{round(bkk['value'] / placed * 100)}%"
    desktop.goto(base_url + "/live/", wait_until="networkidle")
    desktop.wait_for_timeout(600)
    row = desktop.locator("#igcitytab tr", has_text="Bangkok").first.inner_text()
    assert want in row, row
    assert want in desktop.inner_text("#facts")


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
    assert pg.inner_text("#herocap").strip() != ""
    assert pg.locator("#faces .face").count() > 0
    assert f"{live_data['total_views']:,}" in pg.inner_text("#strap")
    ctx.close()


def test_a_total_data_failure_says_so_instead_of_shipping_blank(browser, base_url):
    """live-data.js sets .data-failed when both sources die. It used to set a
    class no stylesheet matched, so the page shipped headings over empty slots
    and said nothing at all."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.route("**/data/live.json", lambda r: r.abort())
    pg.route("**/storage/v1/object/public/public/live.json", lambda r: r.abort())
    pg.goto(base_url + "/", wait_until="networkidle")
    pg.wait_for_timeout(800)
    assert pg.locator("html.data-failed").count() == 1
    msg = pg.locator(".datamsg")
    assert msg.is_visible()
    assert "not available" in msg.inner_text().lower()
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
