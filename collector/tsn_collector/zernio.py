from __future__ import annotations

from typing import Any

import requests

BASE = "https://zernio.com/api/v1"
YT_METRICS = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"


class Zernio:
    def __init__(self, api_key: str, timeout: int = 60):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {api_key}"})
        self.timeout = timeout

    def get(self, path: str, **params: Any) -> Any:
        r = self.s.get(f"{BASE}/{path}", params={k: v for k, v in params.items() if v is not None}, timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"zernio GET {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    def accounts(self) -> list[dict[str, Any]]:
        return self.get("accounts")["accounts"]

    def health(self) -> dict[str, Any]:
        return self.get("accounts/health")

    def follower_stats(self) -> dict[str, Any]:
        return self.get("accounts/follower-stats")

    def analytics(self, platform: str, from_date: str, to_date: str) -> dict[str, Any]:
        posts: list[dict[str, Any]] = []
        page = 1
        first: dict[str, Any] | None = None
        while True:
            d = self.get("analytics", platform=platform, fromDate=from_date, toDate=to_date, limit=100, page=page, source="all")
            first = first or d
            posts.extend(d.get("posts", []))
            pages = (d.get("pagination") or {}).get("pages") or 1
            if page >= pages:
                break
            page += 1
        out = dict(first or {})
        out["posts"] = posts
        return out

    def yt_channel_insights(self, account_id: str, since: str, until: str) -> dict[str, Any]:
        return self.get("analytics/youtube/channel-insights", accountId=account_id, since=since, until=until,
                        metricType="time_series", metrics=YT_METRICS)

    def yt_demographics(self, account_id: str, start: str, end: str, video_id: str | None = None) -> dict[str, Any]:
        return self.get("analytics/youtube/demographics", accountId=account_id, startDate=start, endDate=end, videoId=video_id)

    def yt_daily_views(self, account_id: str, video_id: str, start: str, end: str) -> dict[str, Any]:
        return self.get("analytics/youtube/daily-views", accountId=account_id, videoId=video_id, startDate=start, endDate=end)

    def ig_account_insights(self, account_id: str, since: str, until: str) -> dict[str, Any]:
        return self.get("analytics/instagram/account-insights", accountId=account_id, since=since, until=until,
                        metrics="reach", metricType="time_series")

    def ig_follower_history(self, account_id: str, since: str, until: str) -> dict[str, Any]:
        return self.get("analytics/instagram/follower-history", accountId=account_id, since=since, until=until,
                        metricType="time_series")

    def ig_demographics(self, account_id: str) -> dict[str, Any]:
        return self.get("analytics/instagram/demographics", accountId=account_id)

    def tt_account_insights(self, account_id: str, since: str, until: str) -> dict[str, Any]:
        return self.get("analytics/tiktok/account-insights", accountId=account_id, since=since, until=until,
                        metricType="time_series")