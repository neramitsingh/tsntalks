"""The run is exercised with fake clients so the orchestration is tested without network."""
import json
from datetime import datetime, timezone
from pathlib import Path

from tsn_collector.run import HourlyRun

FX = Path(__file__).parent / "fixtures"


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class FakeZernio:
    def accounts(self): return fx("accounts.json")["accounts"]
    def health(self): return fx("health.json")
    def follower_stats(self): return fx("follower_stats.json")
    def analytics(self, platform, a, b): return fx(f"analytics_{platform}.json")
    def yt_channel_insights(self, *a): return {"metrics": {"views": {"values": [{"date": "2026-09-10", "value": 90}]}}}
    def yt_demographics(self, *a, **k): return fx("yt_demographics.json")
    def ig_account_insights(self, *a): return {"metrics": {"reach": {"values": [{"date": "2026-09-13", "value": 300}]}}}
    def ig_follower_history(self, *a): return {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 1533}]}}}
    def ig_demographics(self, *a): return fx("ig_demographics.json")
    def tt_account_insights(self, *a): return {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 6098}]}}}


class FakeSupa:
    def __init__(self):
        self.writes = {}
        self.rows = {"episodes": [], "post_snapshots": []}
    def upsert(self, table, rows, on_conflict):
        self.writes.setdefault(table, []).extend(rows); return len(rows)
    def insert(self, table, row):
        row = dict(row, id=1); self.writes.setdefault(table, []).append(row); return row
    def update(self, table, match, values):
        self.writes.setdefault(f"update:{table}", []).append((match, values))
    def select(self, table, **params):
        return self.rows.get(table, [])
    def rpc(self, fn, args):
        return {"fetched_at": "x"}
    def upload_public(self, *a, **k):
        self.writes.setdefault("upload", []).append(a[1])


def test_hourly_run_writes_every_table():
    z, s = FakeZernio(), FakeSupa()
    run = HourlyRun(z, s, now=datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc), daily=False, youtube_catalogue=None)
    result = run.execute()
    assert result.status == "ok"
    assert len(s.writes["accounts"]) == 3
    assert len(s.writes["account_snapshots"]) == 3
    assert len(s.writes["posts"]) == 48 + 81 + 77
    assert len(s.writes["post_snapshots"]) == 48 + 81 + 77
    assert len(s.writes["account_health"]) == 3
    assert "metric_daily" not in s.writes  # not a daily run
    assert s.writes["upload"] == ["live.json"]
    assert s.writes["collector_runs"][0]["status"] == "running"
    assert s.writes["update:collector_runs"][0][1]["status"] == "ok"


def test_daily_run_adds_metrics_and_demographics_and_episodes():
    z, s = FakeZernio(), FakeSupa()
    catalogue = [{"id": "AXukyl9hVp0", "title": "TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love", "duration": 2206.0},
                 {"id": "PpnI7_--PUg", "title": "TSN Talks Ep. 13 - Dr. Sunil (Part 2)", "duration": 3000.0}]
    run = HourlyRun(z, s, now=datetime(2026, 9, 14, 20, 30, tzinfo=timezone.utc), daily=True, youtube_catalogue=catalogue,
                    video_stats=lambda vid: {"id": vid, "title": "t", "view_count": 5, "like_count": 1, "comment_count": 0,
                                             "upload_date": "20260901", "thumbnail": None})
    result = run.execute()
    assert result.status == "ok"
    metrics = {(r["metric"], r["day"]) for r in s.writes["metric_daily"]}
    assert ("yt_views", "2026-09-10") in metrics and ("ig_reach", "2026-09-13") in metrics
    assert ("ig_followers", "2026-09-14") in metrics and ("tt_followers", "2026-09-14") in metrics
    kinds = {r["kind"] for r in s.writes["demographics"]}
    assert {"yt_age", "yt_country", "ig_city"} <= kinds
    eps = s.writes["episodes"]
    assert {(e["season"], e["number"]) for e in eps} == {(2, "10"), (1, "13")}
    # the catalogue video Zernio did not return becomes a post with a snapshot from yt-dlp
    assert any(p["id"] == "yt:AXukyl9hVp0" for p in s.writes["posts"])


def test_needs_reconnect_marks_run_failed():
    z, s = FakeZernio(), FakeSupa()
    bad = fx("health.json"); bad["accounts"][0]["needsReconnect"] = True
    z.health = lambda: bad
    result = HourlyRun(z, s, now=datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc), daily=False, youtube_catalogue=None).execute()
    assert result.status == "failed"
    assert "needs reconnect" in result.notes["errors"][0]

# --- episode overrides -------------------------------------------------------

from pathlib import Path

from tsn_collector.run import apply_episode_overrides, load_episode_overrides, override_rows

FIX = Path(__file__).parent / "fixtures" / "episodes_override.json"


def test_load_episode_overrides_drops_readme_key():
    ov = load_episode_overrides(FIX)
    assert "_README" not in ov
    assert ov["vid1"]["guest"] == "Curated Name"


def test_load_episode_overrides_missing_file_is_empty():
    assert load_episode_overrides(Path("does-not-exist.json")) == {}


def test_override_rows_only_touches_known_videos():
    existing = [
        {"youtube_video_id": "vid1", "guest": "Parsed Name", "role": "Parsed Role", "season": 1, "number": "3"},
        {"youtube_video_id": "vid2", "guest": "Other", "role": "Other Role", "season": 1, "number": "4"},
        {"youtube_video_id": "vid3", "guest": "Untouched", "role": "Untouched Role", "season": 1, "number": "5"},
    ]
    rows = override_rows(existing, load_episode_overrides(FIX))
    by_id = {r["youtube_video_id"]: r for r in rows}
    assert set(by_id) == {"vid1", "vid2"}                      # vid3 unchanged, missing_vid not invented
    assert by_id["vid1"] == {"youtube_video_id": "vid1", "guest": "Curated Name", "role": "Curated Role"}
    assert by_id["vid2"] == {"youtube_video_id": "vid2", "season": 2, "number": "11"}


def test_apply_episode_overrides_patches_and_never_upserts():
    """episodes.title is NOT NULL and match_terms is parser-owned: these must be PATCHes."""
    class FakeSupa:
        def __init__(self):
            self.updates, self.upserts = [], []

        def select(self, table, **kw):
            return [
                {"youtube_video_id": "vid1", "guest": "Parsed Name", "role": "Parsed Role", "season": 1, "number": "3"},
                {"youtube_video_id": "vid3", "guest": "Untouched", "role": "Untouched Role", "season": 1, "number": "5"},
            ]

        def update(self, table, match, values):
            self.updates.append((table, match, values))

        def upsert(self, *a, **kw):
            self.upserts.append(a)
            return 0

    s = FakeSupa()
    assert apply_episode_overrides(s, FIX) == 1
    assert s.upserts == []
    assert s.updates == [("episodes", {"youtube_video_id": "vid1"},
                          {"guest": "Curated Name", "role": "Curated Role"})]


def test_apply_episode_overrides_is_a_no_op_second_time():
    class FakeSupa:
        def __init__(self):
            self.updates = []

        def select(self, table, **kw):
            return [{"youtube_video_id": "vid1", "guest": "Curated Name", "role": "Curated Role",
                     "season": 1, "number": "3"}]

        def update(self, table, match, values):
            self.updates.append(values)

    s = FakeSupa()
    assert apply_episode_overrides(s, FIX) == 0
    assert s.updates == []


def test_override_rows_skips_rows_already_correct():
    existing = [{"youtube_video_id": "vid1", "guest": "Curated Name", "role": "Curated Role", "season": 1, "number": "3"}]
    assert override_rows(existing, load_episode_overrides(FIX)) == []
