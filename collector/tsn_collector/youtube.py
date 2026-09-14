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