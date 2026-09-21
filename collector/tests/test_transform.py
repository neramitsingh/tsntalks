import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tsn_collector import transform as T

FX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc)


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_account_rows():
    rows = T.account_rows(fx("accounts.json")["accounts"])
    ig = next(r for r in rows if r["platform"] == "instagram")
    assert ig["id"] == "6aa7d545726ebfe037e9d502"
    assert ig["handle"] == "tsntalks"
    assert ig["display_name"] == "TSN Talks"
    assert ig["active"] is True
    assert ig["connected_at"].startswith("2026-09-14")


def test_account_snapshot_rows():
    rows = T.account_snapshot_rows(fx("follower_stats.json"), NOW)
    by = {r["account_id"]: r for r in rows}
    assert by["6aa7d4ef726ebfe037e9d35c"]["followers"] == 6098
    assert by["6aa7d50c726ebfe037e9d45c"]["followers"] == 2350
    assert all(r["taken_at"] == NOW.isoformat() for r in rows)


def test_post_key():
    assert T.post_key("youtube", "https://www.youtube.com/watch?v=PpnI7_--PUg", "z1") == "yt:PpnI7_--PUg"
    assert T.post_key("instagram", "https://www.instagram.com/reel/DO0ULVGEzt6/", "z2") == "ig:DO0ULVGEzt6"
    assert T.post_key("instagram", "https://www.instagram.com/p/DRJt3KGE7bH/", "z3") == "ig:DRJt3KGE7bH"
    assert T.post_key("tiktok", "https://www.tiktok.com/@tsntalks.th/video/7608030276714774544?utm_source=x", "z4") == "tt:7608030276714774544"
    assert T.post_key("tiktok", None, "z5") == "zr:z5"


def test_post_rows_youtube():
    posts, snaps = T.post_rows(fx("analytics_youtube.json"), "youtube", "6aa7d50c726ebfe037e9d45c", NOW)
    assert len(posts) == 48 and len(snaps) == 48
    top = max(snaps, key=lambda s: s["views"])
    assert top["views"] == 71444 and top["post_id"] == "yt:PpnI7_--PUg"
    p = next(x for x in posts if x["id"] == "yt:PpnI7_--PUg")
    assert p["platform_post_id"] == "PpnI7_--PUg"
    assert p["published_at"].startswith("2025-09-20")
    assert p["title"].startswith("TSN Talks Ep. 13")
    assert p["account_id"] == "6aa7d50c726ebfe037e9d45c"


def test_post_rows_tiktok_reach():
    posts, snaps = T.post_rows(fx("analytics_tiktok.json"), "tiktok", "6aa7d4ef726ebfe037e9d35c", NOW)
    top = max(snaps, key=lambda s: s["views"])
    assert top["views"] == 943699 and top["reach"] == 766117 and top["likes"] == 64327


def test_yt_channel_metric_rows():
    rows = T.yt_channel_metric_rows(fx("yt_channel_insights.json"), "6aa7d50c726ebfe037e9d45c")
    # fixture was fetched as total_value, so no per-day rows are produced
    assert rows == []


def test_yt_channel_metric_rows_time_series():
    payload = {"metrics": {"views": {"values": [{"date": "2026-09-01", "value": 100}, {"date": "2026-09-02", "value": 50}]},
                           "subscribersGained": {"values": [{"date": "2026-09-01", "value": 3}]}}}
    rows = T.yt_channel_metric_rows(payload, "acc")
    assert {"account_id": "acc", "day": "2026-09-01", "metric": "yt_views", "value": 100} in rows
    assert {"account_id": "acc", "day": "2026-09-01", "metric": "yt_subs_gained", "value": 3} in rows
    assert len(rows) == 3


def test_demographic_rows_youtube():
    rows = T.demographic_rows("yt", fx("yt_demographics.json")["demographics"], "acc", "2025-09-14", "2026-09-11", NOW)
    age = [r for r in rows if r["kind"] == "yt_age"]
    assert {r["dimension"]: r["value"] for r in age}["25-34"] == 38.1
    country = {r["dimension"]: r["value"] for r in rows if r["kind"] == "yt_country"}
    assert country["IN"] == 70183 and country["TH"] == 57519
    assert all(r["window_start"] == "2025-09-14" and r["window_end"] == "2026-09-11" for r in rows)


def test_demographic_rows_instagram_skips_empty_dims():
    rows = T.demographic_rows("ig", fx("ig_demographics.json")["demographics"], "acc", "2026-09-01", "2026-09-14", NOW)
    kinds = {r["kind"] for r in rows}
    assert kinds == {"ig_age", "ig_city", "ig_country", "ig_gender"}
    city = {r["dimension"]: r["value"] for r in rows if r["kind"] == "ig_city"}
    assert city["Bangkok, Bangkok"] == 509


def test_series_metric_rows():
    payload = {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 6098}]},
                           "likes_count": {"total": 109909}}}
    rows = T.series_metric_rows(payload, "acc", {"follower_count": "tt_followers", "likes_count": "tt_likes"})
    assert rows == [{"account_id": "acc", "day": "2026-09-14", "metric": "tt_followers", "value": 6098}]


def test_health_rows():
    rows = T.health_rows(fx("health.json"), NOW)
    tt = next(r for r in rows if r["account_id"] == "6aa7d4ef726ebfe037e9d35c")
    assert tt["status"] == "healthy" and tt["needs_reconnect"] is False and tt["can_fetch_analytics"] is True
    assert tt["token_expires_at"].startswith("2026-09-15")

# ── follower source (2026-09-21) ────────────────────────────────────────────────────────────────────────────────────


def test_override_followers_replaces_one_account_and_returns_what_it_replaced():
    rows = [{"account_id": "yt", "followers": 1870}, {"account_id": "tt", "followers": 6095}]
    assert T.override_followers(rows, "yt", 2350) == 1870
    assert rows[0]["followers"] == 2350
    assert rows[1]["followers"] == 6095


def test_override_followers_on_an_absent_account_changes_nothing():
    rows = [{"account_id": "tt", "followers": 6095}]
    assert T.override_followers(rows, "yt", 2350) is None
    assert rows == [{"account_id": "tt", "followers": 6095}]


def test_follower_moves_names_a_swing_past_the_threshold():
    rows = [{"account_id": "yt", "followers": 1870}, {"account_id": "tt", "followers": 6095}]
    notes = T.follower_moves(rows, {"yt": 2350, "tt": 6098}, {"yt": "youtube", "tt": "tiktok"})
    assert len(notes) == 1
    assert "youtube" in notes[0] and "2350" in notes[0] and "1870" in notes[0]


def test_follower_moves_is_silent_without_a_previous_snapshot_or_a_zero_baseline():
    rows = [{"account_id": "yt", "followers": 1870}, {"account_id": "ig", "followers": 12}]
    assert T.follower_moves(rows, {"ig": 0}, {"yt": "youtube", "ig": "instagram"}) == []
