"""Pure functions: API JSON in, database rows out. No I/O here."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

YT_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]{6,})")
IG_RE = re.compile(r"instagram\.com/(?:reel|p|reels)/([A-Za-z0-9_-]+)")
TT_RE = re.compile(r"tiktok\.com/@[^/]+/video/(\d+)")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def account_rows(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for a in accounts:
        rows.append({
            "id": a["_id"],
            "platform": a["platform"],
            "handle": a.get("username") or "",
            "display_name": a.get("displayName"),
            "avatar_url": a.get("profilePicture"),
            "connected_at": (a.get("metadata") or {}).get("connectedAt") or a.get("createdAt"),
            "active": bool(a.get("isActive", True)),
        })
    return rows


def account_snapshot_rows(follower_stats: dict[str, Any], taken_at: datetime) -> list[dict[str, Any]]:
    rows = []
    for a in follower_stats.get("accounts", []):
        rows.append({
            "account_id": a["_id"],
            "taken_at": _iso(taken_at),
            "followers": a.get("currentFollowers"),
            "following": None,
            "total_likes": None,
            "post_count": None,
        })
    return rows


def post_key(platform: str, url: str | None, zernio_id: str) -> str:
    if url:
        if platform == "youtube" and (m := YT_RE.search(url)):
            return f"yt:{m.group(1)}"
        if platform == "instagram" and (m := IG_RE.search(url)):
            return f"ig:{m.group(1)}"
        if platform == "tiktok" and (m := TT_RE.search(url)):
            return f"tt:{m.group(1)}"
    return f"zr:{zernio_id}"


def post_rows(analytics: dict[str, Any], platform: str, account_id: str, taken_at: datetime):
    posts, snaps = [], []
    for p in analytics.get("posts", []):
        url = p.get("platformPostUrl")
        zid = p.get("_id") or p.get("postId") or ""
        key = post_key(platform, url, zid)
        a = p.get("analytics") or {}
        posts.append({
            "id": key,
            "account_id": account_id,
            "platform": platform,
            "platform_post_id": key.split(":", 1)[1] if not key.startswith("zr:") else None,
            "url": url,
            "title": (p.get("content") or "").strip()[:500] or None,
            "media_type": p.get("mediaType"),
            "published_at": p.get("publishedAt"),
            "thumb_url": p.get("thumbnailUrl"),
            "last_seen_at": _iso(taken_at),
        })
        snaps.append({
            "post_id": key,
            "taken_at": _iso(taken_at),
            "views": a.get("views") or 0,
            "likes": a.get("likes") or 0,
            "comments": a.get("comments") or 0,
            "shares": a.get("shares") or 0,
            "saves": a.get("saves") or 0,
            "reach": a.get("reach") or 0,
            "impressions": a.get("impressions") or 0,
            "engagement_rate": a.get("engagementRate"),
        })
    return posts, snaps


YT_METRIC_NAMES = {
    "views": "yt_views",
    "estimatedMinutesWatched": "yt_minutes",
    "averageViewDuration": "yt_avg_duration",
    "subscribersGained": "yt_subs_gained",
    "subscribersLost": "yt_subs_lost",
}


def series_metric_rows(payload: dict[str, Any], account_id: str, names: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for api_name, metric in names.items():
        m = (payload.get("metrics") or {}).get(api_name) or {}
        for v in m.get("values") or []:
            if v.get("value") is None:
                continue
            rows.append({"account_id": account_id, "day": v["date"][:10], "metric": metric, "value": v["value"]})
    return rows


def yt_channel_metric_rows(payload: dict[str, Any], account_id: str) -> list[dict[str, Any]]:
    return series_metric_rows(payload, account_id, YT_METRIC_NAMES)


def demographic_rows(prefix: str, demographics: dict[str, Any], account_id: str,
                     window_start: str, window_end: str, taken_at: datetime) -> list[dict[str, Any]]:
    rows = []
    for dim_name, entries in (demographics or {}).items():
        for e in entries or []:
            rows.append({
                "account_id": account_id,
                "kind": f"{prefix}_{dim_name}",
                "dimension": str(e["dimension"]),
                "value": e["value"],
                "window_start": window_start,
                "window_end": window_end,
                "taken_at": _iso(taken_at),
            })
    return rows


def health_rows(health: dict[str, Any], checked_at: datetime) -> list[dict[str, Any]]:
    rows = []
    for a in health.get("accounts", []):
        rows.append({
            "account_id": a["accountId"],
            "checked_at": _iso(checked_at),
            "status": a.get("status", "unknown"),
            "can_fetch_analytics": a.get("canFetchAnalytics"),
            "needs_reconnect": a.get("needsReconnect"),
            "token_expires_at": a.get("tokenExpiresAt"),
        })
    return rows

FOLLOWER_SWING = 0.10


def override_followers(rows: list[dict[str, Any]], account_id: str, followers: int) -> int | None:
    """Replace one account's follower count in a snapshot batch. Returns the value replaced, None if absent."""
    for r in rows:
        if r["account_id"] == account_id:
            was, r["followers"] = r["followers"], followers
            return was
    return None


def follower_moves(rows: list[dict[str, Any]], previous: dict[str, int],
                   platforms: dict[str, str] | None = None, threshold: float = FOLLOWER_SWING) -> list[str]:
    """One note per account whose follower count moved more than `threshold` since its last stored snapshot.

    A warning, never a refusal: a real exodus is data and must land. It exists because on 2026-09-21 an aggregator
    reported a 20% YouTube drop that the platform itself did not agree with, and nothing said so."""
    notes = []
    for r in rows:
        was, now = previous.get(r["account_id"]), r.get("followers")
        if not was or now is None:
            continue
        if abs(now - was) / was > threshold:
            who = (platforms or {}).get(r["account_id"], r["account_id"])
            notes.append(f"followers: {who} moved {was} -> {now} in one run, more than {threshold:.0%}")
    return notes
