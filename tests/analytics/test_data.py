"""The data layer: window maths, every call against its fixture, compare windows.

These run the real `site/js/analytics/data.js` inside the real page, against the
stubbed PostgREST. Nothing here reimplements the module in Python — a test that
recomputes what the code computes only proves the two agree with each other.
"""
import datetime as dt
import json
from pathlib import Path

import pytest


FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def js(page, body):
    """Run an expression with data.js and format.js in scope."""
    return page.evaluate("""async (src) => {
      const data = await import('/js/analytics/data.js');
      const format = await import('/js/analytics/format.js');
      return await (new Function('data', 'format', `return (async () => { ${src} })()`))(
        data, format);
    }""", body)


@pytest.fixture
def d(dashboard):
    """A signed-in page; call js(d, ...) to drive the data layer inside it."""
    return dashboard


# --- Bangkok, which is the whole ball game ----------------------------------

def test_the_bangkok_offset_never_moves_across_a_whole_year(d):
    """Thailand has observed no daylight saving since 1952 and the window maths
    relies on +07:00 being a constant. If that ever changes this fails here,
    loudly, instead of shifting every period boundary by an hour for six months.
    """
    offsets = js(d, """
      const out = new Set();
      for (let day = 0; day < 366; day += 1) {
        const t = new Date(Date.UTC(2026, 0, 1) + day * 86400000);
        const local = new Date(t.toLocaleString('en-US', { timeZone: 'Asia/Bangkok' }));
        const utc = new Date(t.toLocaleString('en-US', { timeZone: 'UTC' }));
        out.add(Math.round((local - utc) / 60000));
      }
      return [...out];
    """)
    assert offsets == [7 * 60]


@pytest.mark.parametrize("instant,granularity,expected", [
    # 02:30 Bangkok on 9 Sep is 19:30 UTC on 8 Sep — the day boundary that a
    # naive UTC truncation gets wrong.
    ("2026-09-08T19:30:00Z", "day", "2026-09-08T17:00:00.000Z"),
    ("2026-09-08T16:59:59Z", "day", "2026-09-07T17:00:00.000Z"),
    ("2026-09-08T19:30:00Z", "hour", "2026-09-08T19:00:00.000Z"),
    # Weeks start Monday, the same as Postgres date_trunc('week', …).
    ("2026-09-11T05:00:00Z", "week", "2026-09-06T17:00:00.000Z"),
    # A month edge: 00:30 Bangkok on 1 Sep is 17:30 UTC on 31 Aug.
    ("2026-08-31T17:30:00Z", "month", "2026-08-31T17:00:00.000Z"),
    ("2026-08-31T16:30:00Z", "month", "2026-07-31T17:00:00.000Z"),
])
def test_period_boundaries_are_bangkok_midnight_not_utc(d, instant, granularity, expected):
    got = js(d, f"""
      return data.floorPeriod(new Date('{instant}'), '{granularity}').toISOString();
    """)
    assert got == expected


def test_adding_periods_is_calendar_aware(d):
    """+1 month from 31 January is 28 February, not 3 March."""
    got = js(d, """
      const jan31 = data.bangkokDate('2026-01-31');
      return {
        month: data.bangkokDateString(data.addPeriods(jan31, 'month', 1)),
        week: data.bangkokDateString(data.addPeriods(jan31, 'week', 1)),
        back: data.bangkokDateString(data.addPeriods(jan31, 'month', -1)),
      };
    """)
    assert got == {"month": "2026-02-28", "week": "2026-02-07", "back": "2025-12-31"}


def test_a_bangkok_date_string_round_trips(d):
    got = js(d, """
      return data.bangkokDateString(data.bangkokDate('2026-09-15'));
    """)
    assert got == "2026-09-15"


# --- windows ----------------------------------------------------------------

@pytest.mark.parametrize("frame,granularity,periods", [
    ("7d", "day", 7),
    ("30d", "day", 30),
    ("90d", "week", 13),
    ("12m", "month", 12),
])
def test_each_frame_spans_the_periods_it_claims(d, frame, granularity, periods):
    got = js(d, f"""
      const w = await data.windowFor({{ frame: '{frame}', granularity: '{granularity}' }});
      return data.countPeriods(w.from, w.to, '{granularity}');
    """)
    # 90 days is 13 whole weeks plus a part-week, and a 12-month frame ends
    # inside the current month; both land on the period that contains today.
    assert got in (periods, periods + 1)


def test_a_custom_window_covers_the_days_the_user_picked(d):
    got = js(d, """
      const w = await data.windowFor(
        { frame: 'custom', from: '2026-09-09', to: '2026-09-15', granularity: 'day' });
      return { from: w.from.toISOString(), days: data.countPeriods(w.from, w.to, 'day') };
    """)
    assert got["from"] == "2026-09-08T17:00:00.000Z"   # Bangkok midnight, 9 Sep
    assert got["days"] == 7                            # the 9th to the 15th inclusive


def test_a_custom_window_never_reaches_into_the_future(d):
    """`to` is clamped to now: the snapshot functions read "the last snapshot at
    or before to_ts", so a future `to` would report the present as the future."""
    ahead = js(d, """
      const w = await data.windowFor(
        { frame: 'custom', from: '2026-09-01', to: '2099-01-01', granularity: 'day' });
      return w.to.getTime() - Date.now();
    """)
    assert ahead <= 1000


@pytest.mark.parametrize("granularity", ["hour", "day", "week", "month"])
def test_the_compare_window_is_exactly_adjacent(d, granularity):
    """No gap and no overlap: previous.to is the same instant as current.from."""
    got = js(d, f"""
      const w = await data.windowFor(
        {{ frame: '90d', granularity: '{granularity}', compare: true }});
      const p = data.previousWindow(w);
      return {{
        adjacent: p.to.getTime() === w.from.getTime(),
        currentPeriods: data.countPeriods(w.from, w.to, '{granularity}'),
        previousPeriods: data.countPeriods(p.from, p.to, '{granularity}'),
      }};
    """)
    assert got["adjacent"]
    assert got["previousPeriods"] == got["currentPeriods"]


def test_a_twelve_month_comparison_lands_on_month_boundaries(d):
    """Shifting by milliseconds instead of by periods puts the previous window's
    edge in the middle of a month, and every label after it is a day or two out."""
    got = js(d, """
      const w = await data.windowFor({ frame: '12m', granularity: 'month', compare: true });
      const p = data.previousWindow(w);
      return { from: data.bangkokDateString(p.from), to: data.bangkokDateString(p.to) };
    """)
    assert got["from"].endswith("-01")
    assert got["to"].endswith("-01")


# --- every call against its fixture -----------------------------------------

@pytest.fixture
def win(d):
    """The fixture window, as a JS expression tests can paste in."""
    return ("await data.windowFor({ frame: 'custom', from: '2026-09-09', "
            "to: '2026-09-15', granularity: 'day', platform: 'all' })")


def test_views_matches_the_rollup_views_fixture(d, win):
    got = js(d, f"const r = await data.views({win}); return r.ok && r.current;")
    rows = load("rollup_views")
    assert got["total"] == sum(r["views"] for r in rows)
    assert got["postsPublished"] == sum(r["posts_published"] for r in rows)
    assert got["byPlatform"] == {"youtube": 9700, "instagram": 36900, "tiktok": 23300}
    assert len(got["series"]) == len(rows)


def test_followers_reports_the_last_value_not_the_sum(d, win):
    """Followers are a stock. Summing 21 rows of them is how a dashboard claims
    nine million followers for a show with nine thousand."""
    got = js(d, f"const r = await data.followers({win}); return r.ok && r.current;")
    assert got["latest"] == {"youtube": 4080, "instagram": 3080, "tiktok": 2100}
    assert got["total"] == 4080 + 3080 + 2100
    rows = load("rollup_followers")
    assert got["gained"] == sum(r["gained"] for r in rows)
    assert got["lost"] == sum(r["lost"] for r in rows)
    assert got["lost"] > 0, "the fixture has Instagram losing followers; do not lose that"


def test_engagement_rate_is_interactions_over_views_for_the_window(d, win):
    got = js(d, f"const r = await data.engagement({win}); return r.ok && r.current;")
    eng = load("rollup_engagement")
    interactions = sum(r["likes"] + r["comments"] + r["shares"] for r in eng)
    views = sum(r["views"] for r in load("rollup_views"))
    assert got["interactions"] == interactions
    assert got["rate"] == pytest.approx(interactions / views)
    # Not the mean of the per-period rates, which is a different number.
    mean_of_rates = sum(r["engagement_rate"] for r in eng) / len(eng)
    assert got["rate"] != pytest.approx(mean_of_rates, rel=1e-4)


def test_posts_carries_every_row_including_the_one_that_lost_views(d, win):
    got = js(d, f"const r = await data.posts({win}); return r.ok && r.current.rows;")
    rows = load("post_deltas")
    assert len(got) == len(rows)
    lost = [r for r in got if r["viewsGained"] < 0]
    assert [r["postId"] for r in lost] == ["tt:FIXCLIP03"]
    # publishedAt is a Date object, which Playwright hands back as a datetime.
    # A string here would mean the conversion never happened.
    assert all(isinstance(r["publishedAt"], dt.datetime) for r in got)


def test_reach_is_null_where_a_platform_does_not_report_it_never_zero(d, win):
    """null is "not reported"; 0 would be a claim that nobody saw the post."""
    got = js(d, f"const r = await data.posts({win}); return r.ok && r.current.rows;")
    by_platform = {}
    for r in got:
        by_platform.setdefault(r["platform"], []).append(r["reach"])
    assert all(v is None for v in by_platform["youtube"])
    assert all(v is None for v in by_platform["tiktok"])
    assert all(v and v > 0 for v in by_platform["instagram"])


def test_episodes_matches_the_episode_rollup_fixture(d):
    got = js(d, "const r = await data.episodes(); return r.ok && r.current.rows;")
    rows = load("episode_rollup")
    assert len(got) == len(rows)
    first = next(r for r in got if r["episodeId"] == 1)
    assert first["guest"] == "Testy McFixture"
    assert first["clipViews"] == {"youtube": 3000, "instagram": 18000, "tiktok": 14000}
    assert first["totalReach"] == 47000


def test_audience_computes_shares_over_the_rows_it_got(d):
    """Works for the kinds that are already percentages and the kinds that are
    raw counts, so no renderer has to know which is which."""
    for kind in ("yt_age", "yt_country"):
        got = js(d, f"const r = await data.audience('{kind}', 90); return r.ok && r.current;")
        assert sum(r["share"] for r in got["rows"]) == pytest.approx(1.0)
        assert got["window"]["start"].year == 2026


def test_a_demographic_shift_is_reported_in_percentage_points(d):
    got = js(d, "const r = await data.audience('yt_country', 90); return r.ok && r.current.rows;")
    rows = {r["dimension"]: r for r in got}
    assert rows["TH"]["shareDelta"] > 0
    assert rows["IN"]["shareDelta"] < 0
    # Points, not a relative change: India's share falls by tens of points.
    assert abs(rows["IN"]["shareDelta"]) > 1


def test_a_kind_with_no_earlier_window_comes_back_null_not_zero(d):
    got = js(d, "const r = await data.audience('ig_city', 30); return r.ok && r.current;")
    assert got["prevWindow"] is None
    assert all(r["prevValue"] is None and r["shareDelta"] is None for r in got["rows"])


def test_daily_metrics_name_what_is_missing_rather_than_drawing_zero(d):
    got = js(d, """
      const w = await data.windowFor({ frame: '30d', granularity: 'day', platform: 'all' });
      const r = await data.dailyMetrics(w, ['yt_minutes', 'tt_watch_time', 'ig_watch_time']);
      return r.ok && { missing: r.current.missing, minutes: r.current.byMetric.yt_minutes.length };
    """)
    assert got["missing"] == ["tt_watch_time", "ig_watch_time"]
    assert got["minutes"] > 0


def test_daily_metrics_carry_the_platform_of_their_account(d):
    got = js(d, """
      const w = await data.windowFor({ frame: '30d', granularity: 'day', platform: 'all' });
      const r = await data.dailyMetrics(w, ['yt_views', 'ig_follows', 'tt_followers_gained']);
      return [...new Set(r.current.series.map((s) => s.platform))].sort();
    """)
    assert got == ["instagram", "tiktok", "youtube"]


def test_post_history_reads_one_post_over_the_window(d, win):
    got = js(d, f"""
      const w = {win};
      const r = await data.postHistory('ig:FIXCLIP01', w);
      return r.ok && r.current.series;
    """)
    assert len(got) >= 2
    assert got[0]["views"] <= got[-1]["views"]


def test_last_run_reports_freshness_and_treats_a_failure_as_a_failure(d, stub):
    got = js(d, "const r = await data.lastRun(); return r.ok && "
                "{ stale: r.current.stale, failed: r.current.failed, "
                "status: r.current.run.status };")
    assert got == {"stale": False, "failed": False, "status": "ok"}


def test_account_health_keeps_only_the_latest_check_per_account(d):
    got = js(d, "const r = await data.accountHealth(); return r.ok && r.current.rows;")
    assert len(got) == 3
    assert sorted(r["platform"] for r in got) == ["instagram", "tiktok", "youtube"]
    tiktok = next(r for r in got if r["platform"] == "tiktok")
    assert tiktok["needsReconnect"] is True


def test_row_counts_come_from_the_content_range_header(d):
    got = js(d, "const r = await data.rowCounts(); return r.ok && r.current.counts;")
    assert got["posts"] == 10
    assert got["post_snapshots"] == 4200


def test_headline_derives_its_figures_from_the_other_calls(d, win):
    got = js(d, f"""
      const w = {win};
      const r = await data.headline({{ ...w, compare: true }});
      return r.ok && {{ current: r.current, previous: r.previous }};
    """)
    assert got["current"]["views"] == 69900
    assert got["current"]["followers"] == 9260
    # 9, not 10: ten posts exist, nine of them were published inside the window.
    assert got["current"]["postsPublished"] == 9
    # Compare on: the previous window is fetched and shaped the same way.
    assert got["previous"] is not None
    assert got["previous"]["views"] == got["current"]["views"]   # same stubbed fixture


def test_compare_off_returns_a_null_previous(d, win):
    got = js(d, f"const r = await data.headline({win}); return r.previous;")
    assert got is None


# --- failure is a value, not an exception -----------------------------------

def test_a_failed_call_returns_a_reason_instead_of_throwing(d, stub):
    stub.fail("rollup_views", status=500, message="boom")
    got = js(d, """
      const w = await data.windowFor({ frame: '7d', granularity: 'day' });
      data.clearCache();
      const r = await data.views(w);
      return { ok: r.ok, reason: r.reason };
    """)
    assert got["ok"] is False
    assert got["reason"]


def test_a_missing_function_says_the_sql_may_not_be_applied(d, stub):
    """The likeliest reason a fresh deploy sees this is that
    db/004_analytics.sql has not been run yet. Say so."""
    stub.fail("post_deltas", status=404, message="function public.post_deltas does not exist")
    got = js(d, """
      const w = await data.windowFor({ frame: '7d', granularity: 'day' });
      data.clearCache();
      const r = await data.posts(w);
      return r.reason;
    """)
    assert "004_analytics.sql" in got


def test_one_dead_endpoint_does_not_take_the_others_with_it(d, stub):
    stub.fail("rollup_followers", status=503, message="down")
    got = js(d, """
      const w = await data.windowFor({ frame: '7d', granularity: 'day' });
      data.clearCache();
      const [v, f] = await Promise.all([data.views(w), data.followers(w)]);
      return { views: v.ok, followers: f.ok, viewTotal: v.ok ? v.current.total : null };
    """)
    assert got == {"views": True, "followers": False, "viewTotal": 69900}


def test_a_failure_is_never_cached(d, stub):
    """A panel that failed once must be able to succeed on the next draw."""
    stub.fail("episode_rollup", status=500, message="boom")
    first = js(d, "data.clearCache(); const r = await data.episodes(); return r.ok;")
    assert first is False
    stub.failures.pop("episode_rollup")
    second = js(d, "const r = await data.episodes(); return r.ok;")
    assert second is True


def test_repeating_a_call_hits_the_cache_rather_than_the_database(d, stub):
    stub.calls.clear()          # the Overview tab has already drawn by now
    js(d, """
      const w = await data.windowFor({ frame: '7d', granularity: 'day' });
      data.clearCache();
      await data.views(w);
      await data.views(w);
      await data.views(w);
    """)
    calls = [c for c in stub.calls if c[0] == "rpc" and c[1] == "rollup_views"]
    assert len(calls) == 1


# --- the header -------------------------------------------------------------

def test_the_header_shows_the_last_collector_run(dashboard):
    dashboard.wait_for_function(
        "document.getElementById('fresh').dataset.state !== 'unknown'")
    assert dashboard.get_attribute("#fresh", "data-state") == "ok"
    assert "collected" in dashboard.inner_text("#fresh")


def test_a_collector_that_has_not_run_for_hours_reads_stale(page, stub, analytics_url, signin):
    stub.last_run_minutes_ago = 200          # past the two-hour threshold
    signin(page)
    page.goto(analytics_url)
    page.wait_for_function(
        "document.getElementById('fresh').dataset.state !== 'unknown'")
    assert page.get_attribute("#fresh", "data-state") == "stale"


def test_the_stale_threshold_is_two_hours_not_the_public_pages_three(d):
    got = js(d, "return data.STALE_AFTER_MS;")
    assert got == 2 * 60 * 60 * 1000
