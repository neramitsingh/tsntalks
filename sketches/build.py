"""Build standalone sketch HTML files from templates + real Zernio data.

Usage:  python sketches/build.py
Reads   sketches/data.json (raw Zernio pulls, see session notes) and
        sketches/episodes.json (parsed from index.html),
writes  sketches/out/live-<X>.html and copies them into the Ney-OS tummy
        folder so they show up at /tummy.

Sketches are throwaway design probes, not production code.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
TUMMY = Path(r"C:\Users\Ney\Codes and Scripts\personal-dashboard\web\tummy")

raw = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
episodes = json.loads((HERE / "episodes.json").read_text(encoding="utf-8"))

HANDLES = {"youtube": "@TSNTalksTH", "instagram": "@tsntalks", "tiktok": "@tsntalks.th"}
ORDER = ["tiktok", "instagram", "youtube"]  # stack order, largest first


def post_slim(p: dict) -> dict:
    return {
        "title": p["title"],
        "views": p["views"],
        "likes": p["likes"],
        "comments": p["comments"],
        "date": p["date"],
        "url": p["url"],
        "thumb": p.get("thumb"),
    }


platforms = {}
for key in ORDER:
    src = raw["platforms"][key]
    platforms[key] = {
        "handle": HANDLES[key],
        "followers": src["followers"],
        "views": src["views"],
        "posts": src["synced_posts"],
        "likes": src["likes"],
        "comments": src["comments"],
        "top": post_slim(src["top"]),
    }

# Monthly views by publish month, Sep 2025 -> Sep 2026, zero-filled.
months = []
y, m = 2025, 9
while (y, m) <= (2026, 9):
    k = f"{y}-{m:02d}"
    row = {"m": k}
    for key in ORDER:
        row[key] = raw["monthly_views"].get(k, {}).get(key, 0)
    months.append(row)
    m += 1
    if m == 13:
        y, m = y + 1, 1

yt_demo = raw["yt_demo"]
country = sorted(yt_demo["country"], key=lambda r: -r["value"])
top_c = country[:5]
other = sum(r["value"] for r in country[5:])
yt = {
    "age": [{"band": r["dimension"], "pct": r["value"]} for r in yt_demo["age"]],
    "gender": [{"g": r["dimension"], "pct": r["value"]} for r in yt_demo["gender"] if r["value"] > 0],
    "country": [{"cc": r["dimension"], "views": r["value"]} for r in top_c] + [{"cc": "Other", "views": other}],
    "ch88": {
        "views": raw["yt_channel_88d"]["views"],
        "minutes": raw["yt_channel_88d"]["estimatedMinutesWatched"],
        "avgDur": raw["yt_channel_88d"]["averageViewDuration"],
        "subsGained": raw["yt_channel_88d"]["subscribersGained"],
        "subsLost": raw["yt_channel_88d"]["subscribersLost"],
        "since": raw["yt_channel_88d"]["range"]["since"],
    },
}

ig_demo = raw["ig_demo"]
ig = {
    "age": [{"band": r["dimension"], "n": r["value"]} for r in ig_demo["age"]],
    "city": [
        {"city": r["dimension"].split(",")[0], "n": r["value"]}
        for r in sorted(ig_demo["city"], key=lambda r: -r["value"])[:5]
    ],
    "acct30": raw["ig_acct_30d"],
}
tt = {
    "followers": raw["tt_acct"]["follower_count"],
    "likes": raw["tt_acct"]["likes_count"],
    "videos": raw["tt_acct"]["video_count"],
}

# Episodes joined with live YouTube numbers where Zernio synced the video.
by_id = {}
for p in raw["posts"]["youtube"]:
    mm = re.search(r"v=([A-Za-z0-9_-]+)", p["url"] or "")
    if mm:
        by_id[mm.group(1)] = p
eps = []
for e in episodes:
    p = by_id.get(e["id"])
    eps.append(
        {
            "id": e["id"],
            "num": e["num"].replace("\u00b7", "\u00b7"),
            "guest": e["guest"],
            "role": e["role"],
            "views": p["views"] if p else None,
            "likes": p["likes"] if p else None,
            "comments": p["comments"] if p else None,
            "date": p["date"] if p else None,
            "thumb": f"https://img.youtube.com/vi/{e['id']}/hqdefault.jpg",
        }
    )

top_posts = {
    key: [post_slim(p) for p in sorted(raw["posts"][key], key=lambda r: -r["views"])[:5]]
    for key in ORDER
}
latest = []
for key in ORDER:
    for p in raw["posts"][key]:
        q = post_slim(p)
        q["platform"] = key
        latest.append(q)
latest.sort(key=lambda r: r["date"], reverse=True)
latest = latest[:8]

DATA = {
    "fetched": "2026-09-14T18:07:00+07:00",
    "total_views": raw["total_views"],
    "total_followers": sum(p["followers"] for p in platforms.values()),
    "platforms": platforms,
    "months": months,
    "yt": yt,
    "ig": ig,
    "tt": tt,
    "episodes": eps,
    "top_posts": top_posts,
    "latest": latest,
}

OUT.mkdir(exist_ok=True)
blob = json.dumps(DATA, ensure_ascii=False)
IMG = HERE / "img"
for dst in [OUT / "img", TUMMY / "img"]:
    if dst.parent.exists():
        dst.mkdir(exist_ok=True)
        for f in IMG.glob("tsn-*.jpg"):
            shutil.copy(f, dst / f.name)
for tpl in sorted(HERE.glob("*.template.html")):
    name = tpl.name.replace(".template", "")
    html = tpl.read_text(encoding="utf-8").replace("__DATA__", blob)
    (OUT / name).write_text(html, encoding="utf-8")
    if TUMMY.exists():
        shutil.copy(OUT / name, TUMMY / f"tsn-{name}")
    print("built", name, len(html), "chars")
