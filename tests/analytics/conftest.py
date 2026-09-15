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

BANGKOK = dt.timezone(dt.timedelta(hours=7))

ANALYTICS = "/analytics/"
TEST_ANON_KEY = "test-anon-key-not-a-real-one"
ALLOWED_EMAIL = "ney@example.test"

CDN_SUPABASE = "**/cdnjs.cloudflare.com/**/supabase*.js"
REST = "**/rest/v1/**"
AUTH = "**/auth/v1/**"

RPCS = ("rollup_views", "rollup_followers", "rollup_engagement",
        "post_deltas", "episode_rollup", "demographics_compare")


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(SITE)))
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
            "episodes": [],
        }
        self.counts = {"posts": 10, "post_snapshots": 4200, "accounts": 3,
                       "account_snapshots": 504, "metric_daily": 360,
                       "demographics": 48, "episodes": 3, "collector_runs": 168,
                       "account_health": 168}
        self.failures = {}
        self.calls = []
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
        if table == "collector_runs":
            target = _now() - dt.timedelta(minutes=self.last_run_minutes_ago)
            return _shift(rows, ("started_at", "finished_at"),
                          target - _parse(max(r["finished_at"] for r in rows)))
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
        page.route(CDN_SUPABASE, self._shim)
        page.route("**/js/analytics/supa.js", self._supa_js)
        page.route(REST, self._rest)
        page.route(AUTH, self._auth)

    def _shim(self, route):
        route.fulfill(status=200, content_type="application/javascript",
                      body=SHIM.read_text(encoding="utf-8"))

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


def _context(browser, width, height):
    return browser.new_context(viewport={"width": width, "height": height})


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
