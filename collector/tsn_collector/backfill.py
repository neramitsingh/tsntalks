"""One-off YouTube history: channel insights month by month (Zernio caps a call at 88 days), daily views for the top videos."""
from __future__ import annotations

from datetime import date, timedelta

from . import transform as T


def month_chunks(months: int, today: date | None = None) -> list[tuple[str, str]]:
    today = today or date.today()
    end = today - timedelta(days=3)
    chunks = []
    for _ in range(months):
        start = (end.replace(day=1) - timedelta(days=1)).replace(day=1) if end.day < 28 else end.replace(day=1)
        start = max(start, end - timedelta(days=87))
        chunks.append((start.isoformat(), end.isoformat()))
        end = start - timedelta(days=1)
    return chunks


def backfill_youtube(z, s, months: int = 12, top_videos: int = 30) -> int:
    acct = next((a for a in s.select("accounts", select="id,platform", platform="eq.youtube")), None)
    if not acct:
        raise SystemExit("no youtube account in the database yet; run `collect` first")
    n = 0
    for start, end in month_chunks(months):
        rows = T.yt_channel_metric_rows(z.yt_channel_insights(acct["id"], start, end), acct["id"])
        n += s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")
    top = s.select("v_post_latest", select="platform_post_id,views", platform="eq.youtube", order="views.desc", limit=str(top_videos))
    for v in top:
        vid = v["platform_post_id"]
        if not vid:
            continue
        for start, end in month_chunks(months):
            try:
                d = z.yt_daily_views(acct["id"], vid, start, end)
            except RuntimeError as ex:  # YouTube's analytics backend returns transient 500s; skip the chunk, keep going
                print(f"skip {vid} {start}..{end}: {str(ex)[:120]}")
                continue
            rows = [{"account_id": acct["id"], "day": x["date"][:10], "metric": f"ytv_{vid}_views", "value": x.get("views") or 0}
                    for x in d.get("dailyViews") or []]
            n += s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")
    return n
