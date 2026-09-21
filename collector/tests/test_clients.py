import json
from pathlib import Path

import responses

from tsn_collector.zernio import Zernio
from tsn_collector.youtube import parse_flat_catalogue

FX = Path(__file__).parent / "fixtures"
B = "https://zernio.com/api/v1"


@responses.activate
def test_analytics_pages_until_done():
    page1 = {"posts": [{"_id": "a"}], "pagination": {"page": 1, "pages": 2}}
    page2 = {"posts": [{"_id": "b"}], "pagination": {"page": 2, "pages": 2}}
    responses.add(responses.GET, f"{B}/analytics", json=page1, match=[responses.matchers.query_param_matcher(
        {"platform": "youtube", "fromDate": "2025-09-15", "toDate": "2026-09-14", "limit": "100", "page": "1", "source": "all"})])
    responses.add(responses.GET, f"{B}/analytics", json=page2, match=[responses.matchers.query_param_matcher(
        {"platform": "youtube", "fromDate": "2025-09-15", "toDate": "2026-09-14", "limit": "100", "page": "2", "source": "all"})])
    z = Zernio("k")
    out = z.analytics("youtube", "2025-09-15", "2026-09-14")
    assert [p["_id"] for p in out["posts"]] == ["a", "b"]
    assert responses.calls[0].request.headers["Authorization"] == "Bearer k"


@responses.activate
def test_simple_getters():
    responses.add(responses.GET, f"{B}/accounts", json={"accounts": [1]})
    responses.add(responses.GET, f"{B}/accounts/health", json={"accounts": []})
    responses.add(responses.GET, f"{B}/accounts/follower-stats", json={"accounts": []})
    z = Zernio("k")
    assert z.accounts() == [1]
    assert z.health() == {"accounts": []}
    assert z.follower_stats() == {"accounts": []}


@responses.activate
def test_yt_channel_insights_params():
    responses.add(responses.GET, f"{B}/analytics/youtube/channel-insights", json={"metrics": {}}, match=[
        responses.matchers.query_param_matcher({"accountId": "acc", "since": "2026-06-18", "until": "2026-09-11",
                                                "metricType": "time_series",
                                                "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"})])
    assert Zernio("k").yt_channel_insights("acc", "2026-06-18", "2026-09-11") == {"metrics": {}}


@responses.activate
def test_error_raises_with_body():
    responses.add(responses.GET, f"{B}/accounts", json={"error": "nope"}, status=401)
    try:
        Zernio("k").accounts()
    except RuntimeError as e:
        assert "401" in str(e) and "nope" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_parse_flat_catalogue():
    flat = json.loads((FX / "ytdlp_flat.json").read_text(encoding="utf-8"))
    vids = parse_flat_catalogue(flat)
    assert len(vids) == 32
    assert vids[0] == {"id": "AXukyl9hVp0", "title": "TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love", "duration": 2206.0}

# --- YouTube Data API: exact counts for the catalogue videos Zernio never imported ---------------------------------
#
# yt-dlp's per-video extraction is blocked by YouTube's bot check from GitHub's runners (seen 2026-09-18 on Ep. 12),
# and the flat channel listing only carries rounded counts (103K, 1.2K). The Data API returns exact statistics for
# fifty ids per call at one quota unit, so it is the source whenever a key exists.

import pytest

from tsn_collector.youtube import fetch_video_stats, fetch_video_stats_api, video_stats_source

YT = "https://www.googleapis.com/youtube/v3/videos"


def _item(vid, views, likes="7", comments="2", published="2025-08-30T05:00:00Z"):
    snippet = {"title": f"title {vid}", "publishedAt": published,
               "thumbnails": {"maxres": {"url": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"}}}
    stats = {"viewCount": str(views)}
    if likes is not None:
        stats["likeCount"] = likes
    if comments is not None:
        stats["commentCount"] = comments
    return {"id": vid, "snippet": snippet, "statistics": stats}


@responses.activate
def test_data_api_stats_come_back_in_the_ytdlp_shape():
    responses.add(responses.GET, YT, json={"items": [_item("YdxkrDzVDjQ", 103512, likes="1070", comments="12"),
                                                     _item("0qgsjhonhwc", 1301, likes=None, comments=None)]},
                  match=[responses.matchers.query_param_matcher(
                      {"part": "snippet,statistics", "id": "YdxkrDzVDjQ,0qgsjhonhwc,9AxuohprUbU", "maxResults": "50", "key": "k"})])
    out = fetch_video_stats_api(["YdxkrDzVDjQ", "0qgsjhonhwc", "9AxuohprUbU"], "k")
    assert out["YdxkrDzVDjQ"] == {"id": "YdxkrDzVDjQ", "title": "title YdxkrDzVDjQ", "view_count": 103512, "like_count": 1070,
                                  "comment_count": 12, "upload_date": "20250830",
                                  "thumbnail": "https://i.ytimg.com/vi/YdxkrDzVDjQ/maxresdefault.jpg"}
    # likes hidden and comments off come back as 0, like yt-dlp's `or 0`
    assert (out["0qgsjhonhwc"]["like_count"], out["0qgsjhonhwc"]["comment_count"]) == (0, 0)
    # a video the API does not return (deleted, private) is simply absent
    assert "9AxuohprUbU" not in out


@responses.activate
def test_data_api_batches_fifty_ids_per_call():
    ids = [f"id{i:09d}" for i in range(60)]
    for chunk in (ids[:50], ids[50:]):
        responses.add(responses.GET, YT, json={"items": [_item(v, 1) for v in chunk]},
                      match=[responses.matchers.query_param_matcher(
                          {"part": "snippet,statistics", "id": ",".join(chunk), "maxResults": "50", "key": "k"})])
    out = fetch_video_stats_api(ids, "k")
    assert len(out) == 60 and len(responses.calls) == 2


@responses.activate
def test_data_api_error_names_the_reason():
    responses.add(responses.GET, YT, status=403, json={"error": {"message": "The request cannot be completed because you have exceeded your quota."}})
    with pytest.raises(RuntimeError, match="quota"):
        fetch_video_stats_api(["YdxkrDzVDjQ"], "k")


def test_video_stats_source_is_ytdlp_without_a_key():
    assert video_stats_source(None, [{"id": "YdxkrDzVDjQ"}]) is fetch_video_stats
    assert video_stats_source("", [{"id": "YdxkrDzVDjQ"}]) is fetch_video_stats


@responses.activate
def test_video_stats_source_with_a_key_looks_the_whole_catalogue_up_once():
    responses.add(responses.GET, YT, json={"items": [_item("YdxkrDzVDjQ", 103512), _item("0qgsjhonhwc", 1301)]},
                  match=[responses.matchers.query_param_matcher(
                      {"part": "snippet,statistics", "id": "YdxkrDzVDjQ,0qgsjhonhwc", "maxResults": "50", "key": "k"})])
    stats = video_stats_source("k", [{"id": "YdxkrDzVDjQ"}, {"id": "0qgsjhonhwc"}])
    assert len(responses.calls) == 0  # nothing fetched until a video is asked for
    assert stats("YdxkrDzVDjQ")["view_count"] == 103512
    assert stats("0qgsjhonhwc")["view_count"] == 1301
    assert len(responses.calls) == 1
    with pytest.raises(RuntimeError, match="9AxuohprUbU"):
        stats("9AxuohprUbU")


def test_settings_read_the_optional_youtube_api_key(monkeypatch):
    from tsn_collector.config import settings_from_env
    for k, v in {"ZERNIO_API_KEY": "z", "SUPABASE_URL": "https://x.supabase.co/", "SUPABASE_SERVICE_ROLE_KEY": "s"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    assert settings_from_env().youtube_api_key is None  # the secret is empty when unset in Actions
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    assert settings_from_env().youtube_api_key == "k"


# ── the channel's own subscriber count (2026-09-21) ─────────────────────────────────────────────────────────────────

from tsn_collector.youtube import channel_stats_source, fetch_channel_stats_api, handle_from_channel_url


def test_handle_from_channel_url():
    assert handle_from_channel_url("https://www.youtube.com/@TSNTalksTH/videos") == "TSNTalksTH"
    assert handle_from_channel_url("https://www.youtube.com/@TSNTalksTH") == "TSNTalksTH"
    assert handle_from_channel_url("https://www.youtube.com/channel/UCCD") is None


@responses.activate
def test_fetch_channel_stats_api_maps_statistics():
    responses.add(responses.GET, "https://www.googleapis.com/youtube/v3/channels",
                  json={"items": [{"id": "UCCD", "statistics": {"subscriberCount": "2350", "viewCount": "257933",
                                                                "videoCount": "112", "hiddenSubscriberCount": False}}]})
    assert fetch_channel_stats_api("TSNTalksTH", "key") == {"subscribers": 2350, "views": 257933, "videos": 112}


@responses.activate
def test_fetch_channel_stats_api_refuses_a_hidden_count():
    responses.add(responses.GET, "https://www.googleapis.com/youtube/v3/channels",
                  json={"items": [{"id": "UCCD", "statistics": {"subscriberCount": "0", "hiddenSubscriberCount": True}}]})
    try:
        fetch_channel_stats_api("TSNTalksTH", "key")
    except RuntimeError as e:
        assert "hidden" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


@responses.activate
def test_fetch_channel_stats_api_raises_with_googles_reason():
    responses.add(responses.GET, "https://www.googleapis.com/youtube/v3/channels",
                  json={"error": {"message": "API key not valid"}}, status=400)
    try:
        fetch_channel_stats_api("TSNTalksTH", "key")
    except RuntimeError as e:
        assert "400" in str(e) and "API key not valid" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_channel_stats_source_is_none_without_a_key_or_a_handle():
    assert channel_stats_source(None, "https://www.youtube.com/@TSNTalksTH/videos") is None
    assert channel_stats_source("key", "https://www.youtube.com/channel/UCCD") is None
    assert callable(channel_stats_source("key", "https://www.youtube.com/@TSNTalksTH/videos"))
