"""The gate, the shell, and the difference between "signed in" and "allowed".

The interesting case is the third one. Supabase authenticates any address it has
a user for; `allowed_users` is what RLS checks. A user who is authenticated but
not on the list must get a sentence explaining that, never a dashboard full of
zeroes that reads as "the show has no numbers".
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"


def test_signed_out_shows_the_gate(page, analytics_url):
    page.goto(analytics_url)
    page.wait_for_selector("#gate:not([hidden])")
    assert page.is_hidden("#shell")
    assert page.is_hidden("#noaccess")
    assert page.is_visible("#email")


def test_signed_in_and_allowed_shows_the_shell(page, stub, analytics_url, signin, allowed_email):
    signin(page)
    page.goto(analytics_url)
    page.wait_for_selector("#shell:not([hidden])")
    assert page.is_hidden("#gate")
    assert page.inner_text("#who").strip() == allowed_email
    assert page.locator(".a-tab").count() == 6


def test_signed_in_but_not_allowed_gets_a_named_panel(page, stub, analytics_url, signin):
    """Zero rows from allowed_users is a permissions answer, not an empty
    dataset. The panel has to say so."""
    stub.allowed = False
    signin(page, "stranger@example.test")
    page.goto(analytics_url)
    page.wait_for_selector("#noaccess:not([hidden])")
    assert page.is_hidden("#shell")
    assert page.is_hidden("#gate")
    text = page.inner_text("#noaccess")
    assert "doesn't have access" in text
    assert "stranger@example.test" in text


def test_a_database_that_cannot_be_reached_is_not_reported_as_no_access(page, stub, analytics_url, signin):
    """An error from allowed_users means we do not know whether the user is
    allowed. Saying "no access" would be a guess, and the wrong one."""
    stub.fail("allowed_users", status=503, message="service unavailable")
    signin(page)
    page.goto(analytics_url)
    page.wait_for_selector("#shell:not([hidden])")
    assert page.is_hidden("#noaccess")
    assert "Could not reach the database" in page.inner_text("#view")


def test_the_gate_never_says_whether_an_address_is_known(page, stub, analytics_url):
    page.goto(analytics_url)
    page.wait_for_selector("#gate:not([hidden])")
    page.fill("#email", "someone@example.test")
    page.click("#gate-send")
    page.wait_for_function("document.getElementById('gate-msg').textContent.length > 0")

    msg = page.inner_text("#gate-msg")
    assert "on its way" in msg
    assert "not found" not in msg.lower() and "unknown" not in msg.lower()
    assert [c for c in stub.calls if c[0] == "auth" and "otp" in c[1]]


def test_a_malformed_address_never_reaches_the_network(page, stub, analytics_url):
    page.goto(analytics_url)
    page.wait_for_selector("#gate:not([hidden])")
    page.fill("#email", "not-an-address")
    page.click("#gate-send")
    page.wait_for_function("document.getElementById('gate-msg').textContent.length > 0")
    assert "email address" in page.inner_text("#gate-msg")
    assert [c for c in stub.calls if c[0] == "auth"] == []


def test_a_failed_send_shows_the_reason_and_re_enables_the_button(page, stub, analytics_url):
    stub.fail("otp", status=429, message="email rate limit exceeded")
    page.goto(analytics_url)
    page.wait_for_selector("#gate:not([hidden])")
    page.fill("#email", "someone@example.test")
    page.click("#gate-send")
    page.wait_for_function("document.getElementById('gate-msg').textContent.length > 0")
    assert "Too many sign-in attempts" in page.inner_text("#gate-msg")
    assert not page.is_disabled("#gate-send")


def test_sign_out_returns_to_the_gate(dashboard):
    dashboard.click(".a-head [data-signout]")
    dashboard.wait_for_selector("#gate:not([hidden])")
    assert dashboard.is_hidden("#shell")


def test_a_missing_anon_key_shows_a_named_panel_not_a_broken_form(page, stub, analytics_url, signin):
    """The worktree that wrote this page had no anon key. Until Nav pastes it in,
    the page must say which one line is missing rather than fail at a fetch."""
    src = (SITE / "js" / "analytics" / "supa.js").read_text(encoding="utf-8")
    unpatched = re.sub(r"SUPABASE_ANON_KEY = '[^']*'", "SUPABASE_ANON_KEY = ''", src, count=1)
    page.route("**/js/analytics/supa.js", lambda r: r.fulfill(
        status=200, content_type="application/javascript", body=unpatched))

    signin(page)
    page.goto(analytics_url)
    page.wait_for_selector("#unconfigured:not([hidden])")
    assert "anon key is missing" in page.inner_text("#unconfigured-why")
    assert page.is_hidden("#gate") and page.is_hidden("#shell")


def test_the_page_loads_without_a_console_or_page_error(page, errors, analytics_url, signin):
    found = errors(page)
    signin(page)
    page.goto(analytics_url, wait_until="networkidle")
    page.wait_for_selector("#shell:not([hidden])")
    page.wait_for_timeout(400)
    assert found == []


# --- the two static guarantees ----------------------------------------------

SERVICE_ROLE = re.compile(r"service_role|SUPABASE_SERVICE_ROLE|\"role\"\s*:\s*\"service_role\"")


def test_no_service_role_key_anywhere_under_site():
    """The anon key is public by design. The service-role key bypasses RLS
    entirely and must never be shipped to a browser."""
    offenders = []
    for path in SITE.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".jpg", ".png", ".webp", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SERVICE_ROLE.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_the_dashboard_chrome_is_hanken_grotesk_and_never_bodoni(dashboard):
    """Spec: private register is Product. Bodoni appears only in the print
    artifacts, where the brand is the point."""
    html = (SITE / "analytics" / "index.html").read_text(encoding="utf-8")
    markup = re.sub(r"<!--.*?-->", "", html, flags=re.S)   # the comments may name it
    assert "Bodoni" not in markup

    families = dashboard.evaluate("""() => {
      const els = [document.querySelector('.a-head h1'),
                   document.querySelector('.a-tab'),
                   document.querySelector('.a-controls .label')];
      return els.filter(Boolean).map((el) => getComputedStyle(el).fontFamily);
    }""")
    assert families, "no chrome elements found"
    for family in families:
        assert "Hanken Grotesk" in family
        assert "Bodoni" not in family


# The plan says "from cdnjs". cdnjs does not host @supabase/supabase-js at all
# — api.cdnjs.com/libraries?search=supabase returns zero results — so the one
# dependency that cannot come from there comes from jsDelivr at an immutable
# version instead, with an SRI hash cdnjs would not have given us either.
# SheetJS, which cdnjs does host, comes from cdnjs. Nothing else is allowed.
ALLOWED_CDNS = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net")

JS_SOURCES = ("analytics/index.html", "js/analytics/artifacts/csv.js")


def cdn_urls():
    urls = []
    for rel in JS_SOURCES:
        text = (SITE / rel).read_text(encoding="utf-8")
        urls += re.findall(r"https://(?:cdn|unpkg|esm|jsdelivr)[^\s\"'<>]+\.js", text)
    return urls


def test_every_cdn_dependency_is_pinned_to_an_exact_version():
    urls = cdn_urls()
    assert urls, "the dashboard loads no CDN script at all"
    for url in urls:
        assert any(host in url for host in ALLOWED_CDNS), url
        assert "@latest" not in url and "/latest/" not in url, url
        assert re.search(r"[@/]\d+\.\d+\.\d+[/@]", url), f"{url} is not pinned exactly"


def test_the_supabase_bundle_is_the_immutable_one_not_the_generated_minification():
    """jsDelivr generates `.min.js` on the fly, and its bytes — and therefore its
    hash — can change. The published dist file cannot."""
    html = (SITE / "analytics" / "index.html").read_text(encoding="utf-8")
    src = re.search(r'src="(https://cdn\.jsdelivr\.net[^"]+)"', html).group(1)
    assert src.endswith("/dist/umd/supabase.js"), src
    assert ".min.js" not in src, src


def test_every_cdn_script_carries_a_subresource_integrity_hash():
    """A private dashboard that can read the whole database should not execute
    whatever a CDN happens to serve tomorrow."""
    html = (SITE / "analytics" / "index.html").read_text(encoding="utf-8")
    tags = re.findall(r"<script[^>]+src=\"https://[^>]+>", html)
    assert tags
    for tag in tags:
        assert re.search(r'integrity="sha384-[A-Za-z0-9+/=]{60,}"', tag), tag
        assert 'crossorigin="anonymous"' in tag, tag

    csv_js = (SITE / "js" / "analytics" / "artifacts" / "csv.js").read_text(encoding="utf-8")
    assert re.search(r"SHEETJS_SRI = 'sha384-[A-Za-z0-9+/=]{60,}'", csv_js)
    assert "script.integrity = SHEETJS_SRI" in csv_js


def test_numbers_use_tabular_figures(dashboard):
    """Columns of digits line up or the table is decoration."""
    variant = dashboard.evaluate(
        "getComputedStyle(document.querySelector('.a-shell')).fontVariantNumeric")
    assert "tabular-nums" in variant
