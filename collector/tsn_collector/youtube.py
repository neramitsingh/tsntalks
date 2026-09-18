"""YouTube catalogue via yt-dlp (no API key). Replace with the Data API when a key exists."""
from __future__ import annotations

from typing import Any


def parse_flat_catalogue(flat: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for e in flat.get("entries") or []:
        if not e.get("id"):
            continue
        out.append({"id": e["id"], "title": e.get("title") or "", "duration": e.get("duration")})
    return out


def fetch_flat_catalogue(channel_videos_url: str) -> dict[str, Any]:
    import yt_dlp  # imported lazily so tests never need it

    with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "no_warnings": True, "skip_download": True}) as y:
        return y.extract_info(channel_videos_url, download=False)


def fetch_video_stats(video_id: str) -> dict[str, Any]:
    """Lifetime stats for one video: view_count, like_count, comment_count, upload_date (YYYYMMDD), title."""
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    return {
        "id": video_id,
        "title": info.get("title") or "",
        "view_count": info.get("view_count") or 0,
        "like_count": info.get("like_count") or 0,
        "comment_count": info.get("comment_count") or 0,
        "upload_date": info.get("upload_date"),
        "thumbnail": info.get("thumbnail"),
    }


def upload_date_to_iso(upload_date: str | None) -> str | None:
    if not upload_date or len(upload_date) != 8:
        return None
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T12:00:00+07:00"

# ── YouTube Data API ────────────────────────────────────────────────────────────────────────────────────────────────
# yt-dlp's per-video extraction is blocked by YouTube's bot check from GitHub's runners now and then (2026-09-18, Ep. 12),
# and the flat channel listing only carries rounded counts (103K, 1.2K). The Data API returns exact statistics for
# fifty ids per call at one quota unit, so it is the source for the catalogue videos whenever a key exists.

DATA_API = "https://www.googleapis.com/youtube/v3/videos"
_THUMB_ORDER = ("maxres", "standard", "high", "medium", "default")


def fetch_video_stats_api(video_ids: list[str], api_key: str, timeout: int = 60) -> dict[str, dict[str, Any]]:
    """Exact lifetime stats in fetch_video_stats' shape, keyed by video id. Fifty ids per call. Videos the API does
    not return (deleted, private) are absent from the result. An API error raises with Google's own reason."""
    import requests

    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        r = requests.get(DATA_API, params={"part": "snippet,statistics", "id": ",".join(chunk), "maxResults": 50,
                                           "key": api_key}, timeout=timeout)
        if r.status_code >= 300:
            try:
                reason = (r.json().get("error") or {}).get("message") or r.text[:200]
            except ValueError:
                reason = r.text[:200]
            raise RuntimeError(f"youtube data api {r.status_code}: {reason}")
        for item in r.json().get("items") or []:
            sn, st = item.get("snippet") or {}, item.get("statistics") or {}
            published = sn.get("publishedAt") or ""
            thumbs = sn.get("thumbnails") or {}
            out[item["id"]] = {
                "id": item["id"],
                "title": sn.get("title") or "",
                "view_count": int(st.get("viewCount") or 0),
                "like_count": int(st.get("likeCount") or 0),
                "comment_count": int(st.get("commentCount") or 0),
                "upload_date": published[:10].replace("-", "") if len(published) >= 10 else None,
                "thumbnail": next((thumbs[k]["url"] for k in _THUMB_ORDER if (thumbs.get(k) or {}).get("url")), None),
            }
    return out


def video_stats_source(api_key: str | None, catalogue: list[dict[str, Any]]):
    """What the daily catalogue step calls for one video's lifetime stats. With a Data API key: one batched lookup of
    the whole catalogue on first use, exact counts, no bot check. Without one: yt-dlp per video."""
    if not api_key:
        return fetch_video_stats
    ids = [v["id"] for v in catalogue]
    cache: dict[str, dict[str, Any]] | None = None

    def lookup(video_id: str) -> dict[str, Any]:
        nonlocal cache
        if cache is None:
            cache = fetch_video_stats_api(ids, api_key)
        if video_id not in cache:
            raise RuntimeError(f"{video_id}: not in the Data API response (deleted or private?)")
        return cache[video_id]

    return lookup
