"""Serve site/ and answer every Supabase call from the committed fixtures.

There is no database here and there never will be: this worktree has no
credentials and no network path to Supabase, by design. So the suite stubs the
HTTP underneath supabase-js — PostgREST and GoTrue are plain REST — exactly the
way tests/site/conftest.py stubs the Storage copy of live.json.

Three things get intercepted:

  cdnjs supabase-js   -> tests/analytics/stubs/supabase-shim.js, a thin
                         stand-in that turns the supabase-js calls the dashboard
                         makes into real fetches at the real URLs. See the file
                         header for what that does and does not prove.
  supa.js             -> served with a test anon key patched into the literal,
                         because the real one is not in this worktree.
  /rest/v1, /auth/v1  -> answered from tests/analytics/fixtures/.

Everything between those three and the assertions is the dashboard's own code.
"""
import base64
import datetime as dt
import json
import re
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
FIX = Path(__file__).parent / "fixtures"
SHIM = Path(__file__).parent / "stubs" / "supabase-shim.js"
VENDOR = Path(__file__).parent / "stubs" / "vendor"

BANGKOK = dt.timezone(dt.timedelta(hours=7))

ANALYTICS = "/analytics/"
# Playwright's 30s default is plenty on an idle box and tight on a busy one — a
# second test run, an antivirus sweep, a CI box doing three things at once. When
# it is tight the failure lands in whichever wait happened to be running, which
# looks like a different broken test every time. Raising the default for the
# whole context covers all of them at once, and waiting longer costs nothing on
# a run that passes.
DEFAULT_TIMEOUT = 90_000

TEST_ANON_KEY = "test-anon-key-not-a-real-one"
ALLOWED_EMAIL = "ney@example.test"

# supabase-js is served from jsDelivr (cdnjs does not host it at all); SheetJS
# from cdnjs. Both are matched loosely so a version bump does not silently let
# the real library through and turn a stubbed test into a live one.
# A regex, not a glob: the dashboard is opened with a query string as often as
# without one, and a glob would match only the bare path.
DASHBOARD_PAGE = re.compile(r"/analytics/(artifacts/[\w-]+\.html|index\.html)?(\?|$)")

CDN_SUPABASE = "**/supabase*.js"
CDN_SHEETJS = "**/xlsx.full.min.js"

# YouTube stills. The fixture video ids are deliberately fake, so the real CDN
# 404s on both; the stub answers the way YouTube really does — no maxresdefault
# for a video that never had one, hqdefault always there — which exercises the
# artifact's fallback chain instead of leaving a 404 in the console.
YT_STILL = "**/i.ytimg.com/**"

# Google Fonts. A render-blocking <link> to a third party is the one thing in
# these pages that can hang, and when it hangs the page never paints, so
# wait_for_selector never sees anything "visible" and the fixture times out —
# which reads as a broken test rather than a bad minute on someone else's CDN.
# Stubbed with an empty stylesheet so the suite is hermetic.
#
# What this gives up: these tests no longer prove the webfonts load.
# tests/site/test_pages.py already checks that against the real Google Fonts for
# the public pages, and test_auth.py checks statically that the dashboard asks
# for the right families. What they DO still prove is the family that resolves —
# Hanken Grotesk in the dashboard, Bodoni in the artifacts — because that comes
# from the CSS, not from the font file.
GOOGLE_FONTS = "**/fonts.googleapis.com/**"
GOOGLE_FONT_FILES = "**/fonts.gstatic.com/**"

# A 1x1 transparent PNG.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
REST = "**/rest/v1/**"
AUTH = "**/auth/v1/**"

RPCS = ("rollup_views", "rollup_followers", "rollup_engagement",
        "post_deltas", "episode_rollup", "demographics_compare")


# SheetJS, pinned and hashed exactly as site/js/analytics/artifacts/csv.js pins
# it. Unlike supabase-js, this one is stubbed with THE REAL LIBRARY: the plan
# asks that an exported workbook open as a valid one, and a hand-written stand-in
# could not prove that. Fetched once and cached under stubs/vendor/ (gitignored),
# so the suite is hermetic from the second run onward.
SHEETJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"
SHEETJS_SRI = "sha384-vtjasyidUo0kW94K5MXDXntzOJpQgBKXmE7e2Ga4LG0skTTLeBi97eFAXsqewJjw"


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def sheetjs_bytes():
    """The real SheetJS, or None if it has never been fetched and cannot be now.

    Verified against the same SRI hash the page uses, so the cache cannot drift
    from what a browser would actually accept.
    """
    cached = VENDOR / "xlsx.full.min.js"
    if cached.exists():
        return cached.read_bytes()
    try:
        import base64
        import hashlib
        import urllib.request
        with urllib.request.urlopen(SHEETJS_URL, timeout=30) as response:
            data = response.read()
        digest = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
        if digest != SHEETJS_SRI:
            raise AssertionError(
                f"SheetJS at {SHEETJS_URL} no longer matches the pinned hash: {digest}")
        VENDOR.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        return data
    except AssertionError:
        raise
    except Exception:
        return None


class QuietHandler(SimpleHTTPRequestHandler):
    """The static server for the suite.

    HTTP/1.1, so connections are kept alive and reused. The default is HTTP/1.0,
    which closes after every response — and this suite makes on the order of ten
    thousand requests, each leaving a socket in TIME_WAIT for minutes. On Windows
    that eventually exhausts the ephemeral port range, and the symptom is one
    page that simply never loads, which shows up as a fixture timing out in a
    different test every run rather than as anything resembling its cause.
    """

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):        # the suite is noisy enough
        pass


@pytest.fixture(scope="session")
def base_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(SITE)))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


class Supabase:
    """The database, as far as the page under test can tell.

    Tests mutate the attributes to describe a world: `stub.allowed = False` is
    a signed-in user who is not in allowed_users; `stub.fail('post_deltas')` is
    one endpoint down while the rest of the tab still draws.
    """

    def __init__(self):
        self.allowed = True
        self.rpc = {name: fixture(name) for name in RPCS}
        self.tables = {
            "allowed_users": [{"email": ALLOWED_EMAIL}],
            "accounts": fixture("accounts"),
            "collector_runs": fixture("collector_runs"),
            "account_health": fixture("account_health"),
            "metric_daily": fixture("metric_daily"),
            "post_snapshots": fixture("post_snapshots"),
            "account_snapshots": fixture("account_snapshots"),
            "episodes": [],
        }
        self.counts = {"posts": 10, "post_snapshots": 4200, "accounts": 3,
                       "account_snapshots": 504, "metric_daily": 360,
                       "demographics": 48, "episodes": 3, "collector_runs": 168,
                       "account_health": 168}
        self.failures = {}
        self.calls = []
        # The RPC stubs answer with the same fixture whatever window they are
        # asked for, which is fine for one window and useless for two. A hook
        # lets a test say what the PREVIOUS month looked like without teaching
        # the stub to actually aggregate anything.
        self.rpc_hook = None
        # Freshness is age, so a fixture with a fixed stamp in it would go stale
        # on its own next week and the suite would start failing for no reason.
        # The three time-relative tables are re-anchored on the way out: the
        # newest collector run lands this many minutes before now, and the daily
        # metrics end today. Tests that care set these.
        self.last_run_minutes_ago = 25
        self.anchor_metric_daily = True

    def fail(self, name, status=500, message="stubbed failure"):
        self.failures[name] = (status, message)

    # --- keeping the clock out of the fixtures ---------------------------

    def _anchored(self, table, rows):
        if not rows:
            return rows
        if table == "collector_runs":
            target = _now() - dt.timedelta(minutes=self.last_run_minutes_ago)
            return _shift(rows, ("started_at", "finished_at"),
                          target - _parse(max(r["finished_at"] for r in rows)))
        if table == "account_snapshots":
            target = _now() - dt.timedelta(minutes=self.last_run_minutes_ago)
            return _shift(rows, ("taken_at",),
                          target - _parse(max(r["taken_at"] for r in rows)))
        if table == "account_health":
            target = _now() - dt.timedelta(minutes=self.last_run_minutes_ago)
            return _shift(rows, ("checked_at",),
                          target - _parse(max(r["checked_at"] for r in rows)))
        if table == "metric_daily" and self.anchor_metric_daily:
            today = dt.datetime.now(dt.timezone.utc).astimezone(BANGKOK).date()
            offset = today - dt.date.fromisoformat(max(r["day"] for r in rows))
            return [{**r, "day": (dt.date.fromisoformat(r["day"]) + offset).isoformat()}
                    for r in rows]
        return rows

    # --- routing ---------------------------------------------------------

    def install(self, page):
        page.route(DASHBOARD_PAGE, self._index)
        page.route(CDN_SUPABASE, self._shim)
        page.route(CDN_SHEETJS, self._sheetjs)
        page.route(YT_STILL, self._still)
        page.route(GOOGLE_FONTS, lambda route: route.fulfill(
            status=200, content_type="text/css", body="/* fonts stubbed */"))
        page.route(GOOGLE_FONT_FILES, lambda route: route.abort())
        page.route("**/js/analytics/supa.js", self._supa_js)
        page.route(REST, self._rest)
        page.route(AUTH, self._auth)

    def _index(self, route):
        """The dashboard page, with the supabase-js integrity attribute removed.

        Subresource integrity is checked against whatever body arrives, and the
        body that arrives here is the shim rather than the real library — so the
        browser blocks it and the page never boots. Stripping the attribute is
        the same kind of honest substitution as patching the anon key into
        supa.js, and test_auth.py asserts separately that the real file still
        carries a well-formed hash.

        SheetJS is NOT stripped: that one is served with its real bytes, so its
        integrity attribute is genuinely exercised.
        """
        path = urlsplit(route.request.url).path
        rel = path.split("/analytics/", 1)[-1] or "index.html"
        src = (SITE / "analytics" / rel).read_text(encoding="utf-8")
        patched, n = re.subn(r'\s*integrity="sha384-[^"]+"', "", src, count=1)
        assert n == 1, f"site/analytics/{rel} no longer pins supabase-js with an SRI hash"
        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=patched)

    def _shim(self, route):
        route.fulfill(status=200, content_type="application/javascript",
                      body=SHIM.read_text(encoding="utf-8"))

    def _still(self, route):
        if "maxresdefault" in route.request.url:
            return route.fulfill(status=404, content_type="text/plain", body="")
        route.fulfill(status=200, content_type="image/png", body=PIXEL)

    def _sheetjs(self, route):
        """The real library, served locally. The page's integrity hash is checked
        against these exact bytes, so SRI is exercised rather than bypassed."""
        data = sheetjs_bytes()
        if data is None:
            return route.fulfill(status=503, content_type="text/plain",
                                 body="SheetJS unavailable offline")
        route.fulfill(status=200, content_type="application/javascript", body=data)

    def _supa_js(self, route):
        """Serve supa.js with a key in it.

        The real anon key is not in this worktree — supa.js ships an empty
        literal with a TODO(nav). The substitution is written so it works
        whether the literal is still empty or Nav has filled it in.
        """
        src = (SITE / "js" / "analytics" / "supa.js").read_text(encoding="utf-8")
        patched, n = re.subn(r"SUPABASE_ANON_KEY = '[^']*'",
                             f"SUPABASE_ANON_KEY = '{TEST_ANON_KEY}'", src, count=1)
        assert n == 1, "supa.js no longer has a single SUPABASE_ANON_KEY literal"
        route.fulfill(status=200, content_type="application/javascript", body=patched)

    def _auth(self, route):
        path = urlsplit(route.request.url).path
        self.calls.append(("auth", path))
        if "otp" in path:
            if "otp" in self.failures:
                status, message = self.failures["otp"]
                return route.fulfill(status=status, content_type="application/json",
                                     body=json.dumps({"message": message}))
            return route.fulfill(status=200, content_type="application/json", body="{}")
        route.fulfill(status=200, content_type="application/json", body="{}")

    def _rest(self, route):
        req = route.request
        parts = urlsplit(req.url)
        path = parts.path.split("/rest/v1/", 1)[-1]

        if path.startswith("rpc/"):
            return self._rpc(route, path[4:], req)
        return self._table(route, path, parts.query, req)

    def _rpc(self, route, name, req):
        args = json.loads(req.post_data or "{}")
        self.calls.append(("rpc", name, args))
        if name in self.failures:
            status, message = self.failures[name]
            return route.fulfill(status=status, content_type="application/json",
                                 body=json.dumps({"message": message}))
        if name not in self.rpc:
            return route.fulfill(status=404, content_type="application/json",
                                 body=json.dumps({"message": f"no function {name}"}))
        data = self.rpc[name]
        if name == "demographics_compare":
            # keyed by kind in the fixture, one array per kind on the wire
            data = data.get(args.get("kind"), [])
        if self.rpc_hook:
            data = self.rpc_hook(name, args, data)
        return route.fulfill(status=200, content_type="application/json",
                             body=json.dumps(data))

    def _table(self, route, table, query, req):
        self.calls.append(("table", table, query))
        if table in self.failures:
            status, message = self.failures[table]
            return route.fulfill(status=status, content_type="application/json",
                                 body=json.dumps({"message": message}))

        if req.method == "HEAD":
            total = self.counts.get(table, 0)
            return route.fulfill(status=200, headers={
                "content-range": f"0-{max(total - 1, 0)}/{total}",
                "content-type": "application/json",
                # Content-Range is not CORS-safelisted. PostgREST exposes it,
                # and without this line the browser hands the shim a null and
                # every row count reads as unknown.
                "access-control-expose-headers": "content-range",
                "access-control-allow-origin": "*",
            }, body="")

        rows = self._anchored(table, list(self.tables.get(table, [])))
        if table == "allowed_users" and not self.allowed:
            rows = []
        rows = _apply_query(rows, query)
        return route.fulfill(status=200, content_type="application/json",
                             body=json.dumps(rows))


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _parse(stamp):
    return dt.datetime.fromisoformat(stamp)


def _shift(rows, columns, delta):
    out = []
    for r in rows:
        row = dict(r)
        for c in columns:
            if row.get(c):
                row[c] = (_parse(row[c]) + delta).isoformat()
        out.append(row)
    return out


_OPS = {
    "eq": lambda a, b: str(a) == b,
    "neq": lambda a, b: str(a) != b,
    "gte": lambda a, b: a is not None and str(a) >= b,
    "lte": lambda a, b: a is not None and str(a) <= b,
    "gt": lambda a, b: a is not None and str(a) > b,
    "lt": lambda a, b: a is not None and str(a) < b,
}


def _apply_query(rows, query):
    """Enough of PostgREST's query grammar for what the dashboard sends.

    Filters, order and limit. Deliberately small: if a tab starts sending
    something this does not understand, the test should notice the rows coming
    back unfiltered rather than a stub quietly pretending.
    """
    q = parse_qs(query, keep_blank_values=True)
    for column, values in q.items():
        if column in ("select", "order", "limit", "offset"):
            continue
        for spec in values:
            op, _, operand = spec.partition(".")
            if op == "in":
                wanted = {v.strip('"') for v in operand.strip("()").split(",")}
                rows = [r for r in rows if str(r.get(column)) in wanted]
            elif op in _OPS:
                rows = [r for r in rows if _OPS[op](r.get(column), operand)]
            else:
                raise AssertionError(f"conftest cannot answer PostgREST filter {column}={spec}")
    for spec in reversed(q.get("order", [])):
        column, _, direction = spec.partition(".")
        rows.sort(key=lambda r: (r.get(column) is None, r.get(column)),
                  reverse=direction.startswith("desc"))
    if q.get("limit"):
        rows = rows[: int(q["limit"][0])]
    return rows


@pytest.fixture
def stub():
    return Supabase()


# The test modules reach these through fixtures rather than `from conftest
# import …`: tests/analytics is a package (see __init__.py), so its directory is
# not on sys.path and a plain import would not resolve.

def halve_before(cutoff_iso, fields=("views", "posts_published", "gained", "lost",
                                     "likes", "comments", "shares", "views_gained",
                                     "views_end", "views_start")):
    """An rpc_hook that makes anything asked for before `cutoff` half the size.

    Enough to give a month-on-month comparison two different numbers without
    the stub having to understand windows.
    """
    def hook(name, args, data):
        if not isinstance(data, list) or (args.get("from_ts") or "") >= cutoff_iso:
            return data
        out = []
        for row in data:
            copy = dict(row)
            for field in fields:
                if isinstance(copy.get(field), (int, float)):
                    copy[field] = round(copy[field] / 2)
            out.append(copy)
        return out
    return hook


@pytest.fixture
def analytics_url(base_url):
    return base_url + ANALYTICS


@pytest.fixture
def timeout_ms():
    """The context default, for tests that build their own context."""
    return DEFAULT_TIMEOUT


@pytest.fixture
def halve_previous():
    """`stub.rpc_hook = halve_previous("2026-09-01")` — see halve_before()."""
    return halve_before


@pytest.fixture
def signin():
    """`signin(page)` for the allowed user, `signin(page, addr)` for anyone."""
    return sign_in


@pytest.fixture
def allowed_email():
    return ALLOWED_EMAIL


def _context(browser, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              accept_downloads=True)
    ctx.set_default_timeout(DEFAULT_TIMEOUT)
    return ctx


@pytest.fixture
def page(browser, base_url, stub):
    """A signed-out page at /analytics/."""
    ctx = _context(browser, 1440, 900)
    pg = ctx.new_page()
    stub.install(pg)
    yield pg
    ctx.close()


def sign_in(page, email=ALLOWED_EMAIL):
    """Put a session where the shim looks for it, before any page script runs."""
    session = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_at": 4102444800,
        "user": {"id": "00000000-0000-0000-0000-000000000001", "email": email},
    }
    page.add_init_script(
        f"window.localStorage.setItem('sb-test-session', {json.dumps(json.dumps(session))})")


@pytest.fixture
def dashboard(browser, base_url, stub):
    """A page signed in as an allowed user, with the shell drawn."""
    ctx = _context(browser, 1440, 900)
    pg = ctx.new_page()
    stub.install(pg)
    sign_in(pg)
    pg.goto(base_url + ANALYTICS)
    pg.wait_for_selector("#shell:not([hidden])")
    yield pg
    ctx.close()


@pytest.fixture
def phone(browser, base_url, stub):
    """The same, at 390px. The ship bar is every page on desktop and phone."""
    ctx = _context(browser, 390, 844)
    pg = ctx.new_page()
    stub.install(pg)
    sign_in(pg)
    pg.goto(base_url + ANALYTICS)
    pg.wait_for_selector("#shell:not([hidden])")
    yield pg
    ctx.close()


@pytest.fixture
def errors(request):
    """Collect page errors and console errors from whichever page fixture ran."""
    found = []

    def attach(pg):
        pg.on("pageerror", lambda e: found.append(str(e)))
        pg.on("console", lambda m: found.append(m.text) if m.type == "error" else None)
        return found

    return attach
