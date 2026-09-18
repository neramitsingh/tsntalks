from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings_from_env
from .run import HourlyRun
from .supa import Supa
from .youtube import fetch_flat_catalogue, parse_flat_catalogue, video_stats_source
from .zernio import Zernio


def is_daily_slot(now_utc: datetime, tz_name: str, force: bool) -> bool:
    """True on the first hourly run after 03:00 Bangkok (i.e. the 03:xx run), or when forced."""
    if force:
        return True
    local = now_utc.astimezone(ZoneInfo(tz_name))
    return local.hour == 3


def cmd_collect(args) -> int:
    st = settings_from_env()
    now = datetime.now(timezone.utc)
    daily = is_daily_slot(now, st.tz_name, args.daily)
    catalogue = parse_flat_catalogue(fetch_flat_catalogue(st.youtube_channel_url)) if daily else None
    run = HourlyRun(Zernio(st.zernio_api_key), Supa(st.supabase_url, st.supabase_service_key), now=now, daily=daily,
                    youtube_catalogue=catalogue,
                    video_stats=video_stats_source(st.youtube_api_key, catalogue) if daily else None)
    result = run.execute()
    print(json.dumps({"status": result.status, "rows": result.rows, "daily": daily, "notes": result.notes}, indent=1))
    return 0 if result.status == "ok" else 1


def cmd_health(args) -> int:
    st = settings_from_env()
    print(json.dumps(Zernio(st.zernio_api_key).health()["summary"], indent=1))
    return 0


def cmd_publish(args) -> int:
    st = settings_from_env()
    s = Supa(st.supabase_url, st.supabase_service_key)
    payload = s.rpc("live_json", {})
    data = json.dumps(payload, ensure_ascii=False, indent=None).encode("utf-8")
    s.upload_public("public", "live.json", data, "application/json")
    if args.out:
        with open(args.out, "wb") as f:
            f.write(data)
    print("published live.json", len(data), "bytes")
    return 0


def cmd_backfill(args) -> int:
    from .backfill import backfill_youtube
    st = settings_from_env()
    n = backfill_youtube(Zernio(st.zernio_api_key), Supa(st.supabase_url, st.supabase_service_key), months=args.months, top_videos=args.top)
    print("backfill rows", n)
    return 0


def cmd_apply_episodes(args) -> int:
    from .run import apply_episode_overrides
    st = settings_from_env()
    n = apply_episode_overrides(Supa(st.supabase_url, st.supabase_service_key))
    print(f"applied {n} episode overrides")
    return 0


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="tsn-collect")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--daily", action="store_true", help="force the daily steps"); c.set_defaults(fn=cmd_collect)
    h = sub.add_parser("health"); h.set_defaults(fn=cmd_health)
    p = sub.add_parser("publish-live-json"); p.add_argument("--out", default=None); p.set_defaults(fn=cmd_publish)
    b = sub.add_parser("backfill-youtube"); b.add_argument("--months", type=int, default=12); b.add_argument("--top", type=int, default=30); b.set_defaults(fn=cmd_backfill)
    a = sub.add_parser("apply-episodes"); a.set_defaults(fn=cmd_apply_episodes)
    args = ap.parse_args(argv)
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
