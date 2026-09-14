from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    zernio_api_key: str
    supabase_url: str
    supabase_service_key: str
    youtube_channel_url: str = "https://www.youtube.com/@TSNTalksTH/videos"
    tz_name: str = "Asia/Bangkok"


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, no quotes handling, no override of real env."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def settings_from_env() -> Settings:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    missing = [k for k in ("ZERNIO_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")
    return Settings(
        zernio_api_key=os.environ["ZERNIO_API_KEY"],
        supabase_url=os.environ["SUPABASE_URL"].rstrip("/"),
        supabase_service_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        youtube_channel_url=os.environ.get("YOUTUBE_CHANNEL_URL", Settings.youtube_channel_url),
        tz_name=os.environ.get("TZ_NAME", Settings.tz_name),
    )