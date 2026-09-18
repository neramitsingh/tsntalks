"""The hourly collection run. Orchestration only; every mapping lives in transform/episodes."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from . import episodes as E
from . import transform as T
from .youtube import upload_date_to_iso

PLATFORMS = ("youtube", "instagram", "tiktok")

OVERRIDE_FIELDS = ("season", "number", "guest", "role")
DEFAULT_OVERRIDE_PATH = Path(__file__).resolve().parents[2] / "data" / "episodes.json"


def load_episode_overrides(path: Path = DEFAULT_OVERRIDE_PATH) -> dict[str, dict]:
    """Curated episode truth from the repo, keyed by YouTube video id. Missing file means no overrides."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}


def override_rows(existing: list[dict], overrides: dict[str, dict]) -> list[dict]:
    """The episodes whose curated values differ from what is stored, as patches. Never invents an episode.

    A patch, not an upsert: `episodes.title` is NOT NULL and the curated file does not
    carry it, so an upsert's insert arm would fail and its update arm would clobber
    `match_terms`. Each row is `{youtube_video_id, <only the fields that changed>}`.
    """
    rows = []
    for e in existing:
        ov = overrides.get(e.get("youtube_video_id"))
        if not ov:
            continue
        diff = {f: ov[f] for f in OVERRIDE_FIELDS if f in ov and ov[f] != e.get(f)}
        if diff:
            rows.append({"youtube_video_id": e["youtube_video_id"], **diff})
    return rows


def apply_episode_overrides(supa, path: Path = DEFAULT_OVERRIDE_PATH) -> int:
    """Patch every episode whose curated truth differs from the stored parse. Returns rows touched."""
    overrides = load_episode_overrides(path)
    if not overrides:
        return 0
    existing = supa.select("episodes", select="youtube_video_id,season,number,guest,role")
    n = 0
    for row in override_rows(existing, overrides):
        values = {k: v for k, v in row.items() if k != "youtube_video_id"}
        supa.update("episodes", {"youtube_video_id": row["youtube_video_id"]}, values)
        n += 1
    return n


@dataclass
class RunResult:
    status: str = "ok"
    rows: int = 0
    notes: dict[str, Any] = field(default_factory=lambda: {"errors": [], "warnings": [], "steps": {}})


class HourlyRun:
    def __init__(self, zernio, supa, now: datetime, daily: bool, youtube_catalogue: list[dict] | None,
                 video_stats: Callable[[str], dict] | None = None):
        self.z, self.s, self.now, self.daily = zernio, supa, now, daily
        self.catalogue = youtube_catalogue or []
        self.video_stats = video_stats
        self.result = RunResult()
        self.accounts: list[dict] = []
        self.zernio_ids: dict[str, set[str]] = {}  # post ids Zernio returned this run, per platform

    # helpers
    def _step(self, name: str, fn: Callable[[], int]) -> None:
        try:
            n = fn()
            self.result.rows += n
            self.result.notes["steps"][name] = n
        except Exception as ex:  # a failing platform never stops the others
            self.result.status = "failed"
            self.result.notes["errors"].append(f"{name}: {ex}")

    def _acct(self, platform: str) -> dict | None:
        return next((a for a in self.accounts if a["platform"] == platform), None)

    def _d(self, days_ago: int) -> str:
        return (self.now - timedelta(days=days_ago)).date().isoformat()

    # steps
    def step_accounts(self) -> int:
        self.accounts = T.account_rows(self.z.accounts())
        n = self.s.upsert("accounts", self.accounts, on_conflict="id")
        health = self.z.health()
        n += self.s.upsert("account_health", T.health_rows(health, self.now), on_conflict="account_id,checked_at")
        bad = [a["username"] for a in health.get("accounts", []) if a.get("needsReconnect")]
        if bad:
            raise RuntimeError(f"needs reconnect: {', '.join(bad)}")
        return n

    def step_followers(self) -> int:
        return self.s.upsert("account_snapshots", T.account_snapshot_rows(self.z.follower_stats(), self.now),
                             on_conflict="account_id,taken_at")

    def step_posts(self, platform: str) -> int:
        acct = self._acct(platform)
        if not acct:
            return 0
        data = self.z.analytics(platform, self._d(365), self._d(0))
        posts, snaps = T.post_rows(data, platform, acct["id"], self.now)
        self.zernio_ids[platform] = {p["id"] for p in posts}
        n = self.s.upsert("posts", posts, on_conflict="id")
        n += self.s.upsert("post_snapshots", snaps, on_conflict="post_id,taken_at")
        return n

    def step_youtube_catalogue(self) -> int:
        """Episodes from titles, plus lifetime stats for catalogue videos Zernio did not return.

        A video Zernio returned this run keeps Zernio's hourly snapshot. Every other catalogue video (season one's
        Ep. 1-12, which Zernio never imported) gets its lifetime stats from yt-dlp on every daily run; pulling them only
        once would freeze their views on the day they were first seen. If Zernio's YouTube step failed this run, fall
        back to pulling only videos never seen before, so a Zernio outage does not turn into sixty yt-dlp calls."""
        acct = self._acct("youtube")
        if not acct or not self.catalogue:
            return 0
        covered = self.zernio_ids.get("youtube")
        if covered is None:
            covered = {p["id"] for p in self.s.select("posts", select="id", platform="eq.youtube")}
        ep_rows, n = [], 0
        for v in self.catalogue:
            parsed = E.parse_title(v["title"])
            if parsed:
                ep_rows.append({"season": parsed.season, "number": parsed.number, "title": v["title"], "guest": parsed.guest,
                                "role": parsed.role, "youtube_video_id": v["id"], "match_terms": E.match_terms(parsed)})
            key = f"yt:{v['id']}"
            if key in covered or not self.video_stats:
                continue
            try:
                st = self.video_stats(v["id"])
            except Exception as ex:  # one blocked video (YouTube's bot check on a runner IP) must not stop the rest
                self.result.notes["warnings"].append(f"youtube_catalogue: {v['id']} skipped: {str(ex)[:160]}")
                continue
            n += self.s.upsert("posts", [{"id": key, "account_id": acct["id"], "platform": "youtube", "platform_post_id": v["id"],
                                          "url": f"https://www.youtube.com/watch?v={v['id']}", "title": st["title"] or v["title"],
                                          "media_type": "video", "published_at": upload_date_to_iso(st.get("upload_date")),
                                          "thumb_url": st.get("thumbnail"), "last_seen_at": self.now.isoformat()}], on_conflict="id")
            n += self.s.upsert("post_snapshots", [{"post_id": key, "taken_at": self.now.isoformat(), "views": st["view_count"],
                                                   "likes": st["like_count"], "comments": st["comment_count"], "shares": 0,
                                                   "saves": 0, "reach": 0, "impressions": 0, "engagement_rate": None}],
                               on_conflict="post_id,taken_at")
        n += self.s.upsert("episodes", ep_rows, on_conflict="youtube_video_id")
        return n

    def step_episode_overrides(self) -> int:
        """Curated guest and role from data/episodes.json win over the title parse."""
        return apply_episode_overrides(self.s)

    def step_match_episodes(self) -> int:
        eps = self.s.select("episodes", select="id,match_terms")
        if not eps:
            return 0
        unmatched = self.s.select("posts", select="id,title", episode_id="is.null")
        n = 0
        for p in unmatched:
            ep = E.match_post(p.get("title"), eps)
            if ep is not None:
                self.s.update("posts", {"id": p["id"]}, {"episode_id": ep})
                n += 1
        for e in eps:
            pass
        return n

    def step_daily_youtube(self) -> int:
        acct = self._acct("youtube")
        if not acct:
            return 0
        rows = T.yt_channel_metric_rows(self.z.yt_channel_insights(acct["id"], self._d(10), self._d(3)), acct["id"])
        n = self.s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")
        demo = self.z.yt_demographics(acct["id"], self._d(93), self._d(3))
        n += self.s.upsert("demographics", T.demographic_rows("yt", demo.get("demographics"), acct["id"], self._d(93), self._d(3), self.now),
                           on_conflict="account_id,kind,dimension,window_start,window_end")
        return n

    def step_daily_instagram(self) -> int:
        acct = self._acct("instagram")
        if not acct:
            return 0
        rows = T.series_metric_rows(self.z.ig_account_insights(acct["id"], self._d(30), self._d(0)), acct["id"], {"reach": "ig_reach"})
        rows += T.series_metric_rows(self.z.ig_follower_history(acct["id"], self._d(30), self._d(0)), acct["id"],
                                     {"follower_count": "ig_followers", "followers_gained": "ig_followers_gained", "followers_lost": "ig_followers_lost"})
        n = self.s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")
        demo = self.z.ig_demographics(acct["id"])
        n += self.s.upsert("demographics", T.demographic_rows("ig", demo.get("demographics"), acct["id"], self._d(30), self._d(0), self.now),
                           on_conflict="account_id,kind,dimension,window_start,window_end")
        return n

    def step_daily_tiktok(self) -> int:
        acct = self._acct("tiktok")
        if not acct:
            return 0
        rows = T.series_metric_rows(self.z.tt_account_insights(acct["id"], self._d(30), self._d(0)), acct["id"],
                                    {"follower_count": "tt_followers", "likes_count": "tt_likes", "video_count": "tt_videos",
                                     "followers_gained": "tt_followers_gained", "followers_lost": "tt_followers_lost"})
        return self.s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")

    def step_publish(self) -> int:
        payload = self.s.rpc("live_json", {})
        self.s.upload_public("public", "live.json", json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
        return 1

    def execute(self) -> RunResult:
        run = self.s.insert("collector_runs", {"started_at": self.now.isoformat(), "status": "running"})
        self._step("accounts", self.step_accounts)
        self._step("followers", self.step_followers)
        for p in PLATFORMS:
            self._step(f"posts:{p}", lambda p=p: self.step_posts(p))
        if self.daily:
            self._step("youtube_catalogue", self.step_youtube_catalogue)
            self._step("episode_overrides", self.step_episode_overrides)
            self._step("daily:youtube", self.step_daily_youtube)
            self._step("daily:instagram", self.step_daily_instagram)
            self._step("daily:tiktok", self.step_daily_tiktok)
        self._step("match_episodes", self.step_match_episodes)
        self._step("publish", self.step_publish)
        self.s.update("collector_runs", {"id": run["id"]}, {"finished_at": datetime.now(self.now.tzinfo).isoformat(),
                                                             "status": self.result.status, "rows_written": self.result.rows,
                                                             "notes": self.result.notes})
        return self.result