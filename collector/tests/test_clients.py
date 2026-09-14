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