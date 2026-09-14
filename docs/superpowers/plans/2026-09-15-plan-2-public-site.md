# TSN Talks Plan 2: Public Site

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three public pages — home `/`, `/live`, `/partner` — built in the D1 "Marquee" design system, every number read from `live.json`, deployed to GitHub Pages under Ney's account.

**Architecture:** Plain HTML, CSS and JavaScript, no framework and no build step for the pages themselves. One `site/css/site.css` holds the tokens, type scale and components all three pages share. One `site/js/live-data.js` loads the numbers — same-origin baked copy first so the page never renders empty, then the hourly copy from Supabase Storage, applied in place — and exposes the formatters and freshness logic. Each page has its own small render script. A GitHub Actions workflow copies `data/live.json` into the artifact and publishes `site/` to Pages.

**Tech Stack:** HTML5, CSS custom properties + grid, vanilla ES2022 modules, Google Fonts (Bodoni Moda, Hanken Grotesk), GitHub Pages via `actions/deploy-pages`, Playwright (Python) for screenshot and overflow tests, Python 3.12 for the collector patches.

**Spec:** `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` sections 3.1, 3.2, 3.3, 6, 7, 8, 10 (step 2). Product brief: `PRODUCT.md`.

**Design reference:** `sketches/home-D1-marquee.template.html` is the approved home design and `sketches/live-B-one-number.template.html` the approved live shape. They are throwaway probes: port the visual decisions, do not copy the file. Every deviation from them is named explicitly in the tasks below.

**Who runs what:** every task runs inline on the laptop. This is design work — the delegation default in `CLAUDE.md` sends well-specified mechanical work to M3 workers, and a three-page design system held together by judgment is the named exception. Task 11 (test harness) may be dispatched to a worker if the session is long.

---

## Why this plan starts with the data, not the CSS

The home page's hero is "the latest episode". Right now `live.json` cannot answer which episode that is:

- `episodes[].published_at` is `null` for all 32 rows. `live_json()` reads `e.published_at` from the `episodes` table, and the collector never writes it — it only ever writes `season`, `number`, `title`, `guest`, `role`, `youtube_video_id`, `match_terms`.
- The episode list is ordered `season desc, number desc` where `number` is `text`, so season two reads 9, 8, 7, 6, 5, 4, 3, 2, 10, 0.
- Several `role` values are title fragments the parser could not split, not roles: `"Thai Founders Think Too Small? Hear from"`, `"He Closed $1.5M and Beat 6,000 People fr"`, `"How AI Can Secretly Manipulate You"`. Fourteen season-one roles are empty.

Sunny's original media kit has hand-typed roles for 29 of the 32 episodes and they are correct, because he wrote them. Those are the truth; the parser is the fallback. Tasks 1 to 3 make `live.json` honest before a single line of the page is written.

---

## File structure

```
tsntalks/
  data/
    episodes.json                curated episode truth, committed, human-edited  (NEW)
    live.json                    daily committed copy (already written by the Action)
  db/
    003_functions.sql            live_json(): published_at from the post, real ordering, thumb + url  (MODIFY)
  collector/
    tsn_collector/
      run.py                     step_episode_overrides after step_youtube_catalogue  (MODIFY)
      cli.py                     `apply-episodes` command for a manual re-apply  (MODIFY)
      supa.py                    fix the storage cache-control header  (MODIFY)
    tests/
      test_run.py                override step tests  (MODIFY)
      fixtures/episodes_override.json                                             (NEW)
  site/                          everything GitHub Pages serves                   (NEW)
    index.html                   home
    live/index.html              /live
    partner/index.html           /partner
    css/site.css                 tokens, type scale, primitives, shared components
    js/live-data.js              load + format + freshness, exported
    js/home.js                   home render
    js/live.js                   live render
    img/
      tsn-logo.jpg               Thai Sikh News mark
      tsn-prasert.jpg            founder portrait
      episodes/                  optional per-video still overrides, `<video_id>.jpg`
      episodes/README.md         how the override works
    data/live.json               copied in by the Pages workflow at deploy time
    robots.txt
  tests/site/
    conftest.py                  serve site/ on a local port, one browser per session
    test_pages.py                overflow, fonts, numbers, reduced motion, contrast
    shots/                       gitignored output
  infra/
    github_pages.py              enable Pages with build_type=workflow            (NEW)
  .github/workflows/
    pages.yml                    build + deploy site/                             (NEW)
  .gitignore                     add tests/site/shots/                            (MODIFY)
```

**What stays where it is:** the repo-root `index.html` and `tsn-talks-sponsorship.html` are Sunny's originals, kept for reference and for the partner copy. They are not deployed and not deleted in this plan.

---

## Design contract

Everything in this section is shared by all three pages and is implemented once, in Task 4. Tasks 6 to 8 consume it and add nothing global.

**Tokens** (from the spec, section 2; unchanged from the sketch except `--muted`):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0D0706` | page ground |
| `--bg2` `--bg3` `--bg4` | `#150B09` `#1E1008` `#291508` | panels, poster placeholders, hover |
| `--saffron` | `#E8621A` | primary accent, buttons, live dot |
| `--saffron2` | `#F0852A` | accent text on dark (AA at 14px) |
| `--gold` `--gold2` | `#C8901E` `#E0B040` | eyebrows, italic display accents |
| `--cream` | `#F2E4CC` | body text |
| `--cream-dim` | `#C4A880` | secondary text |
| `--muted` | `#A08468` | labels, table headers. **Not** the old `#7A6050` |
| `--rule` | `rgba(242,228,204,.14)` | hairlines |
| `--rule-hi` | `rgba(232,98,26,.45)` | emphasised hairlines |
| `--yt` `--tt` `--ig` | `#E8621A` `#2EA6A0` `#7C6BF0` | platform colours, never reassigned |

**Type:** `--display: 'Bodoni Moda', Georgia, serif` and `--text: 'Hanken Grotesk', system-ui, sans-serif`. Display is used for headings, guest names and hero figures. Everything else is the sans. Tabular numerals (`font-variant-numeric: tabular-nums`) on every figure that sits in a column.

**Motion:** three animations only — the live dot pulse, poster image scale on hover, one reveal on the hero name. All three are disabled under `prefers-reduced-motion: reduce`.

**Accessibility:** WCAG AA on every text colour over its actual ground. Every chart has a table twin. Every number is present as text. Focus rings on every link and control: `outline: 2px solid var(--saffron2); outline-offset: 3px`.

**Data contract** — the shape `live.json` provides, verified against the live file on 2026-09-15:

```
fetched_at        ISO timestamp, UTC
total_views       int
total_followers   int
platforms.{youtube|instagram|tiktok}
  followers int, views int, posts int
  top { title, views, url, thumb, date }
months[]          { m: "YYYY-MM", platform, views }
episodes[]        { id, season, number, guest, role, youtube_video_id,
                    published_at, views, likes, comments, clips, clip_views,
                    thumb, url }        <- thumb and url added in Task 2
demographics
  yt_age[]        { dimension: "25-34", value: 44.7 }   percent
  yt_gender[]     { dimension: "male",  value: 54.2 }   percent
  yt_country[]    { dimension: "TH",    value: 6641 }   views
  ig_age[]        { dimension, value }                  follower counts
  ig_gender[]     { dimension, value }                  follower counts
  ig_city[]       { dimension: "Bangkok, Bangkok", value }
  ig_country[]    { dimension: "TH", value }
yt_90d            { views, minutes, subs_gained, subs_lost }
```

`demographics.*` arrays arrive sorted by value descending. `episodes` arrives sorted newest first after Task 2.

---

### Task 1: Curated episode truth

The parser keeps its job — it discovers new episodes the moment they publish. This task adds a committed overlay that wins over the parse for the fields a human wrote better.

**Files:**
- Create: `data/episodes.json`
- Create: `collector/tests/fixtures/episodes_override.json`
- Modify: `collector/tsn_collector/run.py`
- Modify: `collector/tsn_collector/cli.py`
- Test: `collector/tests/test_run.py`

- [ ] **Step 1: Write the curated file**

`data/episodes.json`. Keys are YouTube video ids. Every field is optional; a field that is absent leaves the parsed value alone. The 29 guest/role pairs come from Sunny's original `index.html` (extracted into `sketches/episodes.json` on 2026-09-14); the three that only the parser found keep the parser's guest and get a role written from the video title.

```json
{
  "_README": "Curated episode truth. Wins over the collector's title parse. Keys are YouTube video ids; every field is optional. Edit by hand, commit, and the next daily collector run applies it.",
  "puiF1eGZ2LY": { "season": 2, "number": "7",  "guest": "Surasit (Sid) Sachdev",      "role": "Founder & CEO, HungryHub" },
  "Ibofx3nd3Ds": { "season": 2, "number": "6",  "guest": "Sakol Sachdev",              "role": "Founder & CEO, Micro Greentech" },
  "Q_IY5BALpgY": { "season": 2, "number": "5",  "guest": "Gagan Ajmani",               "role": "Corporate, VC & Founder, WOWS Global" },
  "6Dnssyxg-8w": { "season": 2, "number": "4",  "guest": "Sukhdev Sethi",              "role": "Founder, Thai Alpha Innovations" },
  "OwqzzlZ0PGw": { "season": 2, "number": "3",  "guest": "Sunny Chawla",               "role": "Founder, Sunnylogy" },
  "J71XCFlxwts": { "season": 2, "number": "2",  "guest": "Sunny Chawla",               "role": "Founder, Sunnylogy" },
  "0AFpRgf6w5o": { "season": 2, "number": "0",  "guest": "Nikorn Sachdev",             "role": "Season two kickoff, returning guest" },
  "Mv6jWK2EnYc": { "season": 1, "number": "22", "guest": "Nathapol Sirinarang",        "role": "President, BNI The One Chapter" },
  "4gBuXFNt5DY": { "season": 1, "number": "21", "guest": "Dr. Ravee Phol",             "role": "Medical leader and community figure" },
  "6H9biyqCDZY": { "season": 1, "number": "20", "guest": "Harprem Doowa",              "role": "Founder & CEO, Eazy Digital" },
  "lyyPtfjVnXQ": { "season": 1, "number": "19", "guest": "Major Sukit Khurana",        "role": "Military leader and community voice" },
  "YpGM5SEsSRg": { "season": 1, "number": "18", "guest": "Dr. Nivit Kalra",            "role": "Cardiologist & Co-founder, Prime Care Clinic" },
  "bNHbXNSR1uc": { "season": 1, "number": "17", "guest": "Anchit Sachdev",             "role": "Co-founder & MD, GetFresh" },
  "LpOf84axqEQ": { "season": 1, "number": "16", "guest": "Chuan Thakur & Preecha Champi", "role": "Diwali special" },
  "KPGopByI8r4": { "season": 1, "number": "15", "guest": "Manish Sethi",               "role": "Business leader" },
  "lZ9PvA5R7TQ": { "season": 1, "number": "14", "guest": "Mahima Natarajan",           "role": "Co-founder & CMO, Yindii" },
  "PpnI7_--PUg": { "season": 1, "number": "13", "guest": "Dr. Sunil Phol",             "role": "Part two" },
  "9AxuohprUbU": { "season": 1, "number": "12", "guest": "Narin Khurana",              "role": "CEO, SchoolBright" },
  "YdxkrDzVDjQ": { "season": 1, "number": "11", "guest": "Dr. Sunil Phol",             "role": "Part one" },
  "vynsVCwQjqk": { "season": 1, "number": "10", "guest": "Raju Vishwas",               "role": "CEO, Rethink Labs" },
  "jQBfoqCtxZ8": { "season": 1, "number": "9",  "guest": "Krishna Kamthorn",           "role": "Business leader" },
  "MS36EM8jaOM": { "season": 1, "number": "8",  "guest": "Neena Sehgal",               "role": "Entrepreneur and community leader" },
  "KIvulJvZfZ8": { "season": 1, "number": "7",  "guest": "Sajan Kumar",                "role": "Singh Production" },
  "En9wEJNj2u4": { "season": 1, "number": "6",  "guest": "India Pakdee",               "role": "Creative entrepreneur" },
  "1xpQ3bnKqqA": { "season": 1, "number": "5",  "guest": "Mana Khanijou",              "role": "Community and business leader" },
  "K6-2pMqEMM4": { "season": 1, "number": "4",  "guest": "Davinder Singh (Tony)",      "role": "Business leader and community voice" },
  "Gf4Bsu0bRaI": { "season": 1, "number": "3",  "guest": "Kirty Khanijou",             "role": "Creative entrepreneur" },
  "tlWQLS5MrhI": { "season": 1, "number": "2",  "guest": "Nikorn Sachdev",             "role": "Advisor to the Minister of Tourism & Sports, Thailand" },
  "0qgsjhonhwc": { "season": 1, "number": "1",  "guest": "Dhammandeep Singh Khanijaun (Dan)", "role": "Honorary Consul to the Commonwealth of the Bahamas" }
}
```

Three episodes the parser found that are not in Sunny's kit — `Y1hustM4MM4` (S2 E9, Deepak Sajnani), the S2 E8 video (Angad Pasricha) and `Sunny Khurana` S2 E10 — are **deliberately absent**: their parsed guest and role are already correct. Add them here only if Sunny corrects them.

- [ ] **Step 2: Write the fixture**

`collector/tests/fixtures/episodes_override.json`:

```json
{
  "_README": "test fixture",
  "vid1": { "guest": "Curated Name", "role": "Curated Role" },
  "vid2": { "season": 2, "number": "11" },
  "missing_vid": { "guest": "Nobody" }
}
```

- [ ] **Step 3: Write the failing tests**

Append to `collector/tests/test_run.py`:

```python
import json
from pathlib import Path

from tsn_collector.run import load_episode_overrides, override_rows

FIX = Path(__file__).parent / "fixtures" / "episodes_override.json"


def test_load_episode_overrides_drops_readme_key():
    ov = load_episode_overrides(FIX)
    assert "_README" not in ov
    assert ov["vid1"]["guest"] == "Curated Name"


def test_load_episode_overrides_missing_file_is_empty():
    assert load_episode_overrides(Path("does-not-exist.json")) == {}


def test_override_rows_only_touches_known_videos():
    existing = [
        {"youtube_video_id": "vid1", "guest": "Parsed Name", "role": "Parsed Role", "season": 1, "number": "3"},
        {"youtube_video_id": "vid2", "guest": "Other", "role": "Other Role", "season": 1, "number": "4"},
        {"youtube_video_id": "vid3", "guest": "Untouched", "role": "Untouched Role", "season": 1, "number": "5"},
    ]
    rows = override_rows(existing, load_episode_overrides(FIX))
    by_id = {r["youtube_video_id"]: r for r in rows}
    assert set(by_id) == {"vid1", "vid2"}                      # vid3 unchanged, missing_vid not invented
    assert by_id["vid1"] == {"youtube_video_id": "vid1", "guest": "Curated Name", "role": "Curated Role"}
    assert by_id["vid2"] == {"youtube_video_id": "vid2", "season": 2, "number": "11"}


def test_override_rows_skips_rows_already_correct():
    existing = [{"youtube_video_id": "vid1", "guest": "Curated Name", "role": "Curated Role", "season": 1, "number": "3"}]
    assert override_rows(existing, load_episode_overrides(FIX)) == []
```

- [ ] **Step 4: Run them and watch them fail**

Run: `python -m pytest collector/tests/test_run.py -q -k override`
Expected: `ImportError: cannot import name 'load_episode_overrides'`, 4 errors.

- [ ] **Step 5: Implement**

Add to `collector/tsn_collector/run.py`, above `class HourlyRun`:

```python
from pathlib import Path

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
    """Upsert rows for the episodes whose curated values differ from what is stored. Never invents an episode."""
    rows = []
    for e in existing:
        vid = e.get("youtube_video_id")
        ov = overrides.get(vid)
        if not ov:
            continue
        diff = {f: ov[f] for f in OVERRIDE_FIELDS if f in ov and ov[f] != e.get(f)}
        if diff:
            rows.append({"youtube_video_id": vid, **diff})
    return rows
```

Add the step method to `HourlyRun`, directly after `step_youtube_catalogue`:

```python
    def step_episode_overrides(self) -> int:
        """Curated guest and role from data/episodes.json win over the title parse."""
        overrides = load_episode_overrides()
        if not overrides:
            return 0
        existing = self.s.select("episodes", select="youtube_video_id,season,number,guest,role")
        rows = override_rows(existing, overrides)
        return self.s.upsert("episodes", rows, on_conflict="youtube_video_id")
```

And wire it into `execute()`, immediately after the `youtube_catalogue` line inside the `if self.daily:` block:

```python
            self._step("youtube_catalogue", self.step_youtube_catalogue)
            self._step("episode_overrides", self.step_episode_overrides)
```

- [ ] **Step 6: Run the tests**

Run: `python -m pytest collector -q`
Expected: all green, 39 passed (35 before, 4 new).

- [ ] **Step 7: Add a manual re-apply command**

In `collector/tsn_collector/cli.py`, add above `def main`:

```python
def cmd_apply_episodes(args) -> int:
    from .run import load_episode_overrides, override_rows
    st = settings_from_env()
    s = Supa(st.supabase_url, st.supabase_service_key)
    existing = s.select("episodes", select="youtube_video_id,season,number,guest,role")
    rows = override_rows(existing, load_episode_overrides())
    n = s.upsert("episodes", rows, on_conflict="youtube_video_id")
    print(f"applied {n} episode overrides")
    return 0
```

and register it inside `main`, after the `backfill-youtube` parser:

```python
    a = sub.add_parser("apply-episodes"); a.set_defaults(fn=cmd_apply_episodes)
```

- [ ] **Step 8: Commit**

```bash
git add data/episodes.json collector/tsn_collector/run.py collector/tsn_collector/cli.py collector/tests/test_run.py collector/tests/fixtures/episodes_override.json
git commit -m "feat(collector): curated episode overrides win over the title parse"
```

---

### Task 2: `live_json()` tells the truth about dates and order

**Files:**
- Modify: `db/003_functions.sql`

- [ ] **Step 1: Replace the `eps` CTE**

In `db/003_functions.sql`, inside `live_json()`, replace the `eps` CTE with:

```sql
  eps as (
    select e.id, e.season, e.number, e.guest, e.role, e.youtube_video_id,
           coalesce(pl.published_at, e.published_at) as published_at,
           pl.views, pl.likes, pl.comments,
           'https://www.youtube.com/watch?v=' || e.youtube_video_id as url,
           'https://i.ytimg.com/vi/' || e.youtube_video_id || '/maxresdefault.jpg' as thumb,
           (select coalesce(sum(c.views), 0) from v_post_latest c where c.episode_id = e.id and c.platform <> 'youtube') as clip_views,
           (select count(*) from v_post_latest c where c.episode_id = e.id and c.platform <> 'youtube') as clips
    from episodes e left join v_post_latest pl on pl.post_id = 'yt:' || e.youtube_video_id
  ),
```

`published_at` now comes from the YouTube post, which the collector does write, and falls back to the episodes table. `url` and `thumb` are derived so the page never has to build a YouTube URL by hand.

- [ ] **Step 2: Fix the ordering**

In the same function, replace the `'episodes'` line of the final `jsonb_build_object`:

```sql
    'episodes', (select jsonb_agg(to_jsonb(eps) order by published_at desc nulls last, season desc, (number)::int desc) from eps),
```

`(number)::int` is safe: the collector writes `number` as `str(int(...))` in every branch of `parse_title`, and `data/episodes.json` follows the same convention.

- [ ] **Step 3: Apply it**

Run: `python infra/apply_sql.py db/003_functions.sql`
Expected: the script prints success. `create or replace function` is idempotent.

- [ ] **Step 4: Verify the order and the dates**

Run:

```bash
python -m tsn_collector.cli apply-episodes
python -m tsn_collector.cli publish-live-json --out data/live.json
PYTHONIOENCODING=utf-8 python -c "
import json; d=json.load(open('data/live.json',encoding='utf-8'))
for e in d['episodes'][:5]:
    print(e['season'], e['number'], str(e['published_at'])[:10], e['guest'], '|', e['role'])
print('nulls:', sum(1 for e in d['episodes'] if not e['published_at']))
"
```

Expected: five rows newest first with real dates, `nulls: 0`, and the roles from `data/episodes.json`, not the title fragments. **Do not proceed to Task 4 until `nulls: 0`.** If any episode still has no date, its YouTube post row is missing `published_at` — check `posts` for `yt:<video_id>` before going further.

- [ ] **Step 5: Commit**

```bash
git add db/003_functions.sql data/live.json
git commit -m "fix(db): live_json episode dates from the post, real ordering, url and thumb"
```

---

### Task 3: Storage copy is cacheable

`https://xygppcxxfggydlwgoadw.supabase.co/storage/v1/object/public/public/live.json` currently answers `Cache-Control: no-cache` even though `upload_public` sends `cache-control: max-age=300`. Supabase's storage API reads the value from a `cacheControl` form field on a multipart upload, not from the raw header on a binary body.

**Files:**
- Modify: `collector/tsn_collector/supa.py`
- Test: `collector/tests/test_supa.py`

- [ ] **Step 1: Write the failing test**

Append to `collector/tests/test_supa.py`:

```python
def test_upload_public_sends_cache_control_as_a_form_field(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        text = ""

    def fake_post(url, **kw):
        captured.update(url=url, **kw)
        return FakeResp()

    s = Supa("https://x.supabase.co", "key")
    monkeypatch.setattr(s.s, "post", fake_post)
    s.upload_public("public", "live.json", b"{}", "application/json", max_age=300)

    assert captured["files"]["cacheControl"] == (None, "300")
    assert captured["files"][""][0] == "live.json"
    assert captured["headers"]["x-upsert"] == "true"
    assert "Content-Type" not in captured["headers"]      # requests sets the multipart boundary
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest collector/tests/test_supa.py -q -k cache_control`
Expected: `KeyError: 'files'`.

- [ ] **Step 3: Implement**

Replace `upload_public` in `collector/tsn_collector/supa.py`:

```python
    def upload_public(self, bucket: str, path: str, data: bytes, content_type: str, max_age: int = 300) -> None:
        """Storage reads cacheControl from a multipart field; a raw cache-control header is ignored."""
        r = self.s.post(
            f"{self.url}/storage/v1/object/{bucket}/{path}",
            files={"": (path, data, content_type), "cacheControl": (None, str(max_age))},
            headers={"x-upsert": "true"}, timeout=self.timeout,
        )
        if r.status_code >= 300:
            raise RuntimeError(f"upload {bucket}/{path} failed {r.status_code}: {r.text[:300]}")
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest collector -q`
Expected: all green, 40 passed.

- [ ] **Step 5: Verify against the real bucket**

```bash
python -m tsn_collector.cli publish-live-json --out data/live.json
curl -sI "https://xygppcxxfggydlwgoadw.supabase.co/storage/v1/object/public/public/live.json" | grep -i -E "cache-control|content-type"
```

Expected: `Cache-Control: max-age=300` and `Content-Type: application/json`.

If Storage still answers `no-cache`, stop and leave the original header version in place — this is a nicety, not a blocker, and the page's own `cache: 'no-store'` fetch keeps it correct either way. Record the outcome in the task log and move on.

- [ ] **Step 6: Commit**

```bash
git add collector/tsn_collector/supa.py collector/tests/test_supa.py
git commit -m "fix(collector): storage uploads carry a real cache-control"
```

---

### Task 4: The design system, `site/css/site.css`

One stylesheet, three pages. It is written once here and never forked per page.

**Files:**
- Create: `site/css/site.css`
- Create: `site/robots.txt`
- Create: `site/img/episodes/README.md`
- Copy: `sketches/img/tsn-logo.jpg` → `site/img/tsn-logo.jpg`, `sketches/img/tsn-prasert.jpg` → `site/img/tsn-prasert.jpg`

- [ ] **Step 1: Copy the two images that are real assets**

```bash
mkdir -p site/css site/js site/img/episodes site/live site/partner site/data
cp sketches/img/tsn-logo.jpg site/img/tsn-logo.jpg
cp sketches/img/tsn-prasert.jpg site/img/tsn-prasert.jpg
```

These are the only images in the repo that belong to the brand rather than to YouTube. Episode stills come from YouTube at runtime.

- [ ] **Step 2: Write `site/img/episodes/README.md`**

```markdown
# Episode still overrides

Drop a file here named `<youtube_video_id>.jpg` and the site uses it instead of
the YouTube thumbnail for that episode — on the hero and on the poster wall.

Example: `site/img/episodes/puiF1eGZ2LY.jpg` overrides the still for S2 E7.

Why: YouTube thumbnails have the guest's name and "TSN TALKS" baked into the
image, so they fight the page's own typography. Clean studio stills from Sunny
replace them one at a time, with no code change.

Sizing: 1920x1080 or larger, JPEG, under 400 KB. The hero crops to
`object-position: 70% 30%`, so keep the guest right of centre and high in frame.
```

- [ ] **Step 3: Write `site/robots.txt`**

```
User-agent: *
Allow: /
```

- [ ] **Step 4: Write `site/css/site.css`**

Port the styles from `sketches/home-D1-marquee.template.html`, restructured into the sections below. The sketch's values are the approved design; the changes from it are named after the listing.

The file is organised in this order, with a comment banner per section:

1. `@font-face`-free font loading note, `:root` tokens (the table in the Design contract above, verbatim).
2. Reset: `*{box-sizing:border-box;margin:0;padding:0}`, `html` ground and base type, `a{color:inherit;text-decoration:none}`, `img{display:block;max-width:100%}`, `:focus-visible{outline:2px solid var(--saffron2);outline-offset:3px}`.
3. Layout primitives: `.wrap` (page gutter `clamp(20px,4vw,56px)`), `section` vertical rhythm, `.head` (h2 + lede, two-column at desktop, stacked under 900px).
4. Type: `h1`–`h3`, `.display`, `.bignum`, `.eyebrow`, `.lede`, `.fine`.
5. Navigation: `.mark`, `nav`, `nav ul`, `.cta`.
6. Hero: `.hero`, `.hero img`, `.hero::after` gradient, `.hero-in`, `.ep-line`, `.guest`, `.role`, `.watch`.
7. Strap: `.strap`, `.strap span`, `.strap b`, `.strap .live` and its `::before` dot.
8. Poster wall: `.wall`, `.po` and the `.big` / `.mid` / `.sm` size classes.
9. Index list: `.index`, `.index ol`, `.index li`.
10. Data primitives, shared by home and live: `.prop` proportion bar and `.prop-leg`, `table.rep` with `.bar` cells, `.legend`, `.facts`.
11. Columns chart, used only by `/live` but living here so the two pages cannot drift: `.cols`, `.col-stack`, `.col-seg`, `.col-lab`, `.cols-scroll`.
12. Founder block: `.founder`, `.quote`, `.byline`.
13. Partner blocks: `.tiers`, `.tier`, `.bundles`, `.bundle`, `.btn`, `.btn.ghost`, `.cta-row`.
14. Footer.
15. Motion: `@keyframes pulse`, `@keyframes rise`, then `@media (prefers-reduced-motion:reduce)` switching all three animations off.
16. Responsive: one `@media (max-width:900px)` block and one `@media (max-width:560px)` block, both at the end.

**Changes from the sketch, all deliberate:**

| # | Change | Why |
|---|---|---|
| 1 | `.strap` gets `.strap.stale` — `--cream-dim` text, no dot | Spec 7: data older than 3 hours drops the live dot |
| 2 | `.po` gets a `background: var(--bg3)` and `aspect-ratio` on the image, plus a `.po img[data-fallback]` rule | `maxresdefault.jpg` 404s on older uploads; the fallback swap must not reflow |
| 3 | `.guest` gets `animation: rise .7s` | The one hero reveal the spec allows |
| 4 | `.live::before` gets `animation: pulse 2.4s infinite` | The live dot, off under reduced motion |
| 5 | Navigation items are visible below 900px as a horizontally scrolling row, not `display:none` | The sketch hid every nav item but "Partner" on phones; sponsors arrive on phones and need `/live` |
| 6 | `table.rep td.bar i` uses `background: var(--plat, var(--saffron))` | The same table serves YouTube and Instagram on `/live` |
| 7 | `.cols` added | `/live` needs the monthly stacked columns; the home sketch had no chart |
| 8 | `.bundles` / `.bundle` added | `/partner` needs the five bundles; the home sketch had only the five tiers |
| 9 | `--muted` is `#A08468` | Spec 6: the old `#7A6050` fails AA |
| 10 | `.skip` skip-to-content link, visually hidden until focused | Keyboard access on a long page |

- [ ] **Step 5: Check the contrast of every text token**

Write `tests/site/test_contrast.py`:

```python
"""Every text colour must clear WCAG AA on the ground it is actually used on."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "site" / "css" / "site.css"


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg):
    a, b = sorted((_lum(_rgb(fg)), _lum(_rgb(bg))), reverse=True)
    return (a + 0.05) / (b + 0.05)


def token(name):
    m = re.search(rf"--{name}\s*:\s*(#[0-9A-Fa-f]{{6}})", CSS.read_text(encoding="utf-8"))
    assert m, f"token --{name} not found in site.css"
    return m.group(1)


def test_body_and_secondary_text_clear_aa_on_every_ground():
    for ground in ("bg", "bg2", "bg3"):
        for fg, floor in (("cream", 4.5), ("cream-dim", 4.5), ("muted", 4.5)):
            r = ratio(token(fg), token(ground))
            assert r >= floor, f"--{fg} on --{ground} is {r:.2f}:1, needs {floor}"


def test_accent_text_clears_aa_on_the_ground():
    for fg in ("saffron2", "gold2"):
        r = ratio(token(fg), token("bg"))
        assert r >= 4.5, f"--{fg} on --bg is {r:.2f}:1"


def test_button_label_clears_aa_on_saffron():
    r = ratio(token("bg"), token("saffron"))
    assert r >= 4.5, f"--bg on --saffron is {r:.2f}:1"
```

- [ ] **Step 6: Run it**

Run: `python -m pytest tests/site/test_contrast.py -q`
Expected: 3 passed. If `--muted` on `--bg3` fails, lighten `--muted` until it passes and update the token table in this plan's Design contract — do not lower the floor, and do not use `--muted` on `--bg3` as a workaround, because the poster wall does exactly that.

- [ ] **Step 7: Commit**

```bash
git add site/css/site.css site/robots.txt site/img tests/site/test_contrast.py
git commit -m "feat(site): D1 design system, contrast-checked tokens"
```

---

### Task 5: `site/js/live-data.js` — one loader, shared by every page

**Files:**
- Create: `site/js/live-data.js`

- [ ] **Step 1: Write it**

```js
/* The numbers. Baked copy first so the page never renders empty, then the hourly
   copy from Supabase Storage applied in place. Everything else imports from here. */

const STORAGE_URL =
  'https://xygppcxxfggydlwgoadw.supabase.co/storage/v1/object/public/public/live.json';
const BAKED_URL = new URL('../data/live.json', import.meta.url).href;
const STALE_AFTER_MS = 3 * 60 * 60 * 1000;

export const PLATFORMS = ['youtube', 'instagram', 'tiktok'];
export const PLATFORM_NAME = { youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok' };
export const PLATFORM_COLOR = { youtube: 'var(--yt)', instagram: 'var(--ig)', tiktok: 'var(--tt)' };
export const PLATFORM_HANDLE = {
  youtube: '@TSNTalksTH',
  instagram: '@tsntalks',
  tiktok: '@tsntalks.th',
};
export const PLATFORM_URL = {
  youtube: 'https://www.youtube.com/@TSNTalksTH',
  instagram: 'https://www.instagram.com/tsntalks',
  tiktok: 'https://www.tiktok.com/@tsntalks.th',
};

/* Formatters. `full` is the number a sponsor can quote; `compact` is for tight spaces.
   Every compact figure on the page must have its full value available in a title or a table. */
export const full = (n) => Number(n || 0).toLocaleString('en-US');
export const compact = (n) => {
  n = Number(n || 0);
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'M';
  if (n >= 1e4) return Math.round(n / 1e3) + 'K';
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
};
export const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

export const bkk = (iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) =>
  iso ? new Date(iso).toLocaleDateString('en-GB', { ...opts, timeZone: 'Asia/Bangkok' }) : '';

export const bkkStamp = (iso) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok',
  });

/* Freshness. The strap says "Live" only when the data really is. */
export function freshness(fetchedAt) {
  const age = Date.now() - new Date(fetchedAt).getTime();
  return {
    stale: !(age >= 0 && age < STALE_AFTER_MS),
    stamp: bkkStamp(fetchedAt),
    hours: Math.floor(age / 3.6e6),
  };
}

/* Episode still: a committed override wins, then the YouTube maxres image,
   then hqdefault, which always exists. Returns the two URLs the caller needs. */
export function stills(videoId, { baseUrl }) {
  return {
    src: new URL(`../img/episodes/${videoId}.jpg`, baseUrl).href,
    yt: `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
    ytFallback: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
  };
}

/* <img> that walks the still chain without reflow. */
export function stillImage(videoId, alt, baseUrl) {
  const s = stills(videoId, { baseUrl });
  const img = new Image();
  img.alt = alt;
  img.loading = 'lazy';
  img.decoding = 'async';
  let step = 0;
  const chain = [s.src, s.yt, s.ytFallback];
  img.addEventListener('error', () => {
    step += 1;
    if (step < chain.length) img.src = chain[step];
  });
  img.src = chain[0];
  return img;
}

async function fetchJson(url, init) {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

/**
 * Render immediately from the committed copy, then again from Storage if it is newer.
 * @param {(data:object, meta:{source:'baked'|'live'}) => void} render
 */
export async function load(render) {
  let baked = null;
  try {
    baked = await fetchJson(BAKED_URL, { cache: 'force-cache' });
    render(baked, { source: 'baked' });
  } catch (err) {
    console.warn('baked live.json unavailable', err);
  }
  try {
    const live = await fetchJson(STORAGE_URL, { cache: 'no-store' });
    if (!baked || new Date(live.fetched_at) >= new Date(baked.fetched_at)) {
      render(live, { source: 'live' });
    }
    return live;
  } catch (err) {
    console.warn('storage live.json unavailable', err);
    if (!baked) document.documentElement.classList.add('data-failed');
    return baked;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add site/js/live-data.js
git commit -m "feat(site): live.json loader, formatters and freshness"
```

---

### Task 6: Home `/`

Spec 3.1. Seven blocks in this order: hero, season two poster wall, season one index, who is listening, founder, partner, footer.

**Files:**
- Create: `site/index.html`
- Create: `site/js/home.js`

- [ ] **Step 1: Write `site/index.html`**

Static markup only — every number is an empty element the script fills. Structure:

```
<head>
  charset, viewport, title "TSN Talks — Thai-Indian stories, told at length"
  <meta name="description"> one sentence naming the show, the audience size and the sponsorship offer
  Open Graph: og:title, og:description, og:image (the latest episode's YouTube still, baked as a
    static URL and refreshed by hand when a season ends — crawlers do not run the script)
  preconnect to fonts.googleapis.com and fonts.gstatic.com
  the Bodoni Moda + Hanken Grotesk stylesheet link from the sketch, unchanged
  <link rel="stylesheet" href="css/site.css">
  <script type="module" src="js/home.js"></script>
</head>
<body>
  <a class="skip" href="#main">Skip to content</a>
  <nav>  mark, links: Guests / Audience / Live numbers (-> live/) / Partner (cta -> partner/)  </nav>
  <header class="hero">
    <img id="heroimg" alt="">          filled by the script
    <div class="hero-in">
      <div class="ep-line"><i></i><span id="epline"></span></div>
      <h1 class="guest" id="guest"></h1>
      <p class="role" id="role"></p>
      <a class="watch" id="watch" target="_blank" rel="noopener"><b></b>Watch the episode</a>
    </div>
    <div class="strap" id="strap"></div>
  </header>
  <main id="main">
    <section id="guests" class="wrap">  head + <div class="wall" id="wall">  + index for season one  </section>
    <section id="audience" class="wrap"> head + .aud: #bignum, #audp, #prop, #propleg, table#agetab, table#ctytab </section>
    <section class="wrap"> founder block, fully static markup </section>
    <section id="partner" class="wrap"> head + .tiers (static, five tiers) + .cta-row </section>
  </main>
  <footer> ... </footer>
</body>
```

**Deviations from the sketch, all required:**

| # | Sketch | Home page | Why |
|---|---|---|---|
| 1 | `epline` hardcoded `"Season 2 · Episode 7 · Latest"` | derived from `episodes[0]` | The sketch was pinned to a moment; episode 10 has shipped since |
| 2 | Tier copy hardcoded in JS | static HTML in the page | Prices are editorial, not data. They must be readable with JS off and greppable by Sunny |
| 3 | `"See bundle pricing"` → `#` | → `partner/` | The page exists now |
| 4 | Founder quote attributed to Prasert | unchanged, but the byline reads `Founder, Thai Sikh News · Host, TSN Talks` | Confirmed from the original kit |
| 5 | Episode count `D.episodes.length` | same, but the strap says "episodes" only when > 1 | Cheap correctness |
| 6 | `img.youtube.com` | `i.ytimg.com` with the override chain from `stillImage()` | Task 5's fallback ladder |
| 7 | No `<main>`, no skip link | both added | Accessibility |

- [ ] **Step 2: Write `site/js/home.js`**

```js
import {
  load, full, compact, pct, bkk, freshness, stillImage,
  PLATFORM_NAME, PLATFORM_COLOR,
} from './live-data.js';

const $ = (id) => document.getElementById(id);
const BASE = import.meta.url;
const STACK = ['tiktok', 'instagram', 'youtube'];   // largest first, so the bar reads left to right
const COUNTRY = { IN: 'India', TH: 'Thailand', US: 'United States', AU: 'Australia', GB: 'United Kingdom', CA: 'Canada' };

function renderHero(d) {
  const e = d.episodes[0];
  const img = stillImage(e.youtube_video_id, `${e.guest} on TSN Talks`, BASE);
  img.id = 'heroimg';
  img.loading = 'eager';
  $('heroimg').replaceWith(img);
  const num = e.number === '0' ? 'Season kickoff' : `Episode ${e.number}`;
  $('epline').textContent = `Season ${e.season} · ${num} · ${bkk(e.published_at)}`;
  $('guest').textContent = e.guest;
  $('role').textContent = e.role || '';
  $('watch').href = e.url;
  $('watch').setAttribute('aria-label', `Watch ${e.guest} on YouTube`);
}

function renderStrap(d) {
  const f = freshness(d.fetched_at);
  const strap = $('strap');
  strap.classList.toggle('stale', f.stale);
  const live = f.stale ? '' : '<span class="live">Live</span>';
  const when = f.stale ? `Updated ${f.stamp}` : `Updated ${f.stamp} Bangkok`;
  strap.innerHTML = `${live}
    <span><b>${full(d.total_views)}</b> views across YouTube, Instagram and TikTok</span>
    <span><b>${full(d.total_followers)}</b> followers</span>
    <span><b>${d.episodes.length}</b> episodes</span>
    <span>${when}</span>`;
}

function renderWall(d) {
  const s2 = d.episodes.filter((e) => e.season === 2);
  const ranked = [...s2].sort((a, b) => (b.views || 0) - (a.views || 0));
  const size = new Map(ranked.map((e, i) => [e.id, i === 0 ? 'big' : i <= 2 ? 'mid' : 'sm']));
  const wall = $('wall');
  wall.replaceChildren(...s2.map((e) => {
    const a = document.createElement('a');
    a.className = `po ${size.get(e.id)}`;
    a.href = e.url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.appendChild(stillImage(e.youtube_video_id, '', BASE));
    const t = document.createElement('div');
    t.className = 't';
    const label = e.number === '0' ? 'Kickoff' : `S${e.season} · E${e.number}`;
    const views = e.views == null ? e.role : `${full(e.views)} views on YouTube`;
    t.innerHTML = `<div class="n">${label}</div><div class="g"></div><div class="v"></div>`;
    t.querySelector('.g').textContent = e.guest;
    t.querySelector('.v').textContent = views;
    a.appendChild(t);
    return a;
  }));
}

function renderIndex(d) {
  const s1 = d.episodes.filter((e) => e.season === 1);
  $('s1').replaceChildren(...s1.map((e) => {
    const li = document.createElement('li');
    li.innerHTML = '<b></b><div><a></a><small></small></div>';
    li.querySelector('b').textContent = String(e.number).padStart(2, '0');
    const a = li.querySelector('a');
    a.textContent = e.guest;
    a.href = e.url;
    a.target = '_blank';
    a.rel = 'noopener';
    li.querySelector('small').textContent = e.role || '';
    return li;
  }));
  document.getElementById('s1count').textContent = `${s1.length} episodes`;
}

function renderAudience(d) {
  const male = d.demographics.yt_gender.find((g) => g.dimension === 'male')?.value ?? 0;
  const top = d.demographics.yt_age[0];
  const cty = d.demographics.yt_country;
  const ctot = cty.reduce((a, c) => a + c.value, 0);
  const inShare = pct(cty.find((c) => c.dimension === 'IN')?.value ?? 0, ctot);
  const thShare = pct(cty.find((c) => c.dimension === 'TH')?.value ?? 0, ctot);
  const posts = Object.values(d.platforms).reduce((a, p) => a + p.posts, 0);

  $('bignum').innerHTML = `${(d.total_views / 1e6).toFixed(2)}<i>M</i>`;
  $('audp').innerHTML =
    `views on ${full(posts)} episodes and clips. <b>${male.toFixed(0)}%</b> of YouTube viewers ` +
    `are men and <b>${top.value.toFixed(0)}%</b> are ${top.dimension}. ` +
    `<b>${inShare}%</b> of YouTube views come from India and <b>${thShare}%</b> from Thailand. ` +
    `On Instagram the audience is Bangkok first.`;

  $('prop').replaceChildren(...STACK.map((k) => {
    const i = document.createElement('i');
    i.style.width = `${(d.platforms[k].views / d.total_views) * 100}%`;
    i.style.background = PLATFORM_COLOR[k];
    i.title = `${PLATFORM_NAME[k]}: ${full(d.platforms[k].views)} views`;
    return i;
  }));
  $('propleg').innerHTML = STACK.map((k) =>
    `<span><i style="background:${PLATFORM_COLOR[k]}"></i>${PLATFORM_NAME[k]} ` +
    `${pct(d.platforms[k].views, d.total_views)}% · ${compact(d.platforms[k].views)}</span>`).join('');

  const age = d.demographics.yt_age;
  const amax = Math.max(...age.map((a) => a.value));
  $('agetab').innerHTML =
    '<caption>YouTube viewers by age</caption>' +
    '<tr><th scope="col">Age</th><th scope="col"><span class="vh">Share</span></th><th scope="col" class="r">Share of views</th></tr>' +
    age.map((a) => `<tr><th scope="row">${a.dimension}</th>` +
      `<td class="bar"><i style="width:${(a.value / amax) * 100}%"></i></td>` +
      `<td class="r">${a.value.toFixed(1)}%</td></tr>`).join('');

  $('ctytab').innerHTML =
    '<caption>YouTube views by country</caption>' +
    '<tr><th scope="col">Country</th><th scope="col" class="r">Views</th><th scope="col" class="r">Share</th></tr>' +
    cty.slice(0, 5).map((c) => `<tr><th scope="row">${COUNTRY[c.dimension] || c.dimension}</th>` +
      `<td class="r">${full(c.value)}</td><td class="r">${pct(c.value, ctot)}%</td></tr>`).join('');
}

load((d) => {
  renderHero(d);
  renderStrap(d);
  renderWall(d);
  renderIndex(d);
  renderAudience(d);
});
```

- [ ] **Step 3: Look at it**

```bash
python -m http.server 8765 --directory site
```

Open `http://localhost:8765/`. Check, by eye and by click:

- The hero is the newest episode by date, not by episode number.
- The strap says "Live" with a pulsing dot and a Bangkok timestamp.
- The poster wall has exactly one big tile and two mid tiles, and no two tiles are the same size in the top row.
- Season one lists every episode with a role, none blank, `01` through `22`.
- The two tables are readable and the bars agree with the percentages.
- "See bundle pricing" goes to `/partner/`.

- [ ] **Step 4: Commit**

```bash
git add site/index.html site/js/home.js
git commit -m "feat(site): home page in the D1 system, numbers from live.json"
```

---

### Task 7: `/live`

Spec 3.2. Shape from `sketches/live-B-one-number.template.html`, restyled in the D1 system. Five blocks: one number, when the hits happened, who is watching, now playing, source footer.

**Files:**
- Create: `site/live/index.html`
- Create: `site/js/live.js`

- [ ] **Step 1: Write `site/live/index.html`**

Same head as the home page, with `<link rel="stylesheet" href="../css/site.css">` and `<script type="module" src="../js/live.js">`, title "TSN Talks — the numbers, live". Body:

```
nav (same as home, "Live numbers" marked aria-current="page")
<main id="main" class="wrap">
  <section class="one">
    h1 "The numbers, <em>live.</em>"  +  p.lede naming the three platforms and the refresh cadence
    <div class="bignum" id="total"></div>
    <div class="prop" id="prop"></div>
    <div class="legend" id="legend"></div>          per platform: colour, name, handle, views, followers, posts
  </section>
  <section>
    head "When the hits <em>happened.</em>" + lede
    <div class="cols-scroll"><div class="cols" id="cols"></div></div>
    <div class="prop-leg" id="colsleg"></div>
    <details class="twin"><summary>The same figures as a table</summary><table class="rep" id="monthstab"></table></details>
  </section>
  <section>
    head "Who is <em>watching.</em>" + lede
    <table class="rep" id="ctytab"></table>
    <table class="rep" id="agetab"></table>
    <ul class="facts" id="facts"></ul>
  </section>
  <section>
    head "Now <em>playing.</em>"
    <div class="wall" id="top"></div>          latest episode big, then the three platform top posts
  </section>
</main>
<footer id="srcfoot"></footer>
```

- [ ] **Step 2: Write `site/js/live.js`**

The blocks that are not simply a re-use of home's helpers:

```js
import {
  load, full, compact, pct, bkk, freshness,
  PLATFORMS, PLATFORM_NAME, PLATFORM_COLOR, PLATFORM_HANDLE, PLATFORM_URL, stillImage,
} from '../js/live-data.js';

const $ = (id) => document.getElementById(id);
const BASE = import.meta.url;
const STACK = ['tiktok', 'instagram', 'youtube'];
const MONTH = (m) => new Date(`${m}-01T00:00:00Z`)
  .toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' });

/* Stacked columns of views by publish month, three series, zero-filled so the axis has no gaps.
   Direct label on the tallest month only; everything else lives in the table twin. */
function renderColumns(d) {
  const keys = [...new Set(d.months.map((r) => r.m))].sort();
  const byMonth = new Map(keys.map((m) => [m, { m, total: 0, youtube: 0, instagram: 0, tiktok: 0 }]));
  for (const r of d.months) {
    const row = byMonth.get(r.m);
    row[r.platform] = r.views;
    row.total += r.views;
  }
  const rows = keys.map((m) => byMonth.get(m));
  const max = Math.max(...rows.map((r) => r.total)) || 1;
  const peak = rows.reduce((a, r) => (r.total > a.total ? r : a), rows[0]);

  $('cols').replaceChildren(...rows.map((r) => {
    const col = document.createElement('div');
    col.className = 'col';
    const stack = document.createElement('div');
    stack.className = 'col-stack';
    stack.style.height = `${(r.total / max) * 100}%`;
    stack.title = `${MONTH(r.m)}: ${full(r.total)} views`;
    for (const k of STACK) {
      if (!r[k]) continue;
      const seg = document.createElement('i');
      seg.className = 'col-seg';
      seg.style.flex = String(r[k]);
      seg.style.background = PLATFORM_COLOR[k];
      stack.appendChild(seg);
    }
    if (r === peak) {
      const lab = document.createElement('b');
      lab.className = 'col-peak';
      lab.textContent = compact(r.total);
      col.appendChild(lab);
    }
    col.appendChild(stack);
    const lab = document.createElement('span');
    lab.className = 'col-lab';
    lab.textContent = MONTH(r.m);
    col.appendChild(lab);
    return col;
  }));

  $('colsleg').innerHTML = STACK.map((k) =>
    `<span><i style="background:${PLATFORM_COLOR[k]}"></i>${PLATFORM_NAME[k]}</span>`).join('');

  $('monthstab').innerHTML =
    '<caption class="vh">Views by publish month and platform</caption>' +
    `<tr><th scope="col">Month</th>${STACK.map((k) => `<th scope="col" class="r">${PLATFORM_NAME[k]}</th>`).join('')}<th scope="col" class="r">Total</th></tr>` +
    rows.map((r) => `<tr><th scope="row">${MONTH(r.m)}</th>` +
      STACK.map((k) => `<td class="r">${full(r[k])}</td>`).join('') +
      `<td class="r"><b>${full(r.total)}</b></td></tr>`).join('');
}

/* Four plain facts, each one a sentence with its own window and source. */
function renderFacts(d) {
  const y = d.yt_90d;
  const net = y.subs_gained - y.subs_lost;
  const hours = Math.round(y.minutes / 60);
  const city = d.demographics.ig_city[0];
  const igTotal = d.demographics.ig_city.reduce((a, c) => a + c.value, 0);
  $('facts').innerHTML = [
    `<b>${full(y.views)}</b> YouTube views in the last 90 days.`,
    `<b>${full(hours)}</b> hours watched on YouTube in the same window.`,
    `<b>${net >= 0 ? '+' : ''}${full(net)}</b> net YouTube subscribers in 90 days (${full(y.subs_gained)} gained, ${full(y.subs_lost)} lost).`,
    `<b>${pct(city.value, igTotal)}%</b> of Instagram followers are in ${city.dimension.split(',')[0]}.`,
  ].map((t) => `<li>${t}</li>`).join('');
}
```

`renderTotal`, `renderLegend`, `renderCountry`, `renderAge` and `renderTop` follow the same shape as their home counterparts and use the same `table.rep` markup — build them by calling the shared helpers, do not write a second formatter.

The footer, which is the point of the whole page:

```js
function renderFooter(d) {
  const f = freshness(d.fetched_at);
  $('srcfoot').innerHTML =
    `<div>Views, followers and post counts come from YouTube, Instagram and TikTok through Zernio. ` +
    `Audience breakdowns are YouTube's and Instagram's own, over a rolling 90-day and 30-day window. ` +
    `Collected hourly; platforms report with their own delay of up to 48 hours.</div>` +
    `<div class="fine">Updated ${f.stamp} Bangkok${f.stale ? ` · ${f.hours} hours ago` : ''}</div>`;
}
```

- [ ] **Step 3: Look at it**

With the local server still running, open `http://localhost:8765/live/`. Check:

- The column chart's tallest month carries a label and the rest do not.
- The table twin inside `<details>` matches the columns, month for month.
- Narrowing to 390px scrolls the chart horizontally and nothing else.
- The facts read as sentences with their windows named.
- The footer states source, window and delay.

- [ ] **Step 4: Commit**

```bash
git add site/live/index.html site/js/live.js
git commit -m "feat(site): live page, one number then the detail"
```

---

### Task 8: `/partner`

Spec 3.3. Pure content, no `live.json`, no script beyond the shared nav behaviour. The copy comes from `tsn-talks-sponsorship.html` and the prices are unchanged.

**Files:**
- Create: `site/partner/index.html`

- [ ] **Step 1: Write it**

Two sections. The five options as `.tier` rows, numbered I to V with the bullet lists from the original:

| # | Name | Price | Line |
|---|---|---|---|
| I | "Brought to you by" + on-screen branding | ฿25,000 | per episode |
| II | Content integration and product placement | ฿20,000 | per episode |
| III | Host-read mentions | ฿15,000 | per episode |
| IV | Signature segment | ฿70,000 | per month, 4 episodes |
| V | Guest feature episode | ฿20,000 basic / ฿45,000 standard | per episode |

Then the five bundles as `.bundle` cards, each with its term, its inclusions, its regular price struck through, its package price and its guaranteed-reach line:

| Bundle | Term | Regular | Price | Reach |
|---|---|---|---|---|
| Starter — Brand Intro | 1 week | ฿40,000 | ฿29,000 | 100,000 |
| Growth — Visibility Boost | 2 weeks | ฿55,000 | ฿39,000 | 200,000 |
| Bundle A — Brand Visibility | 1 month | ฿105,000 | ฿69,000 | 350,000 |
| Bundle B — Premium (most popular) | 1 month | ฿150,000 | ฿109,000 | 500,000 |
| Bundle C — Signature Sponsor (flagship) | 2 months | ฿355,000 | ฿185,000 | 1,000,000 |

**The footnote the spec requires**, placed directly under the bundle grid, in `.fine`:

> Guaranteed reach figures are commitments we make for a campaign, combining TSN Talks and Thai Sikh News placements. They are targets we underwrite, not measurements. Everything on the [live numbers](../live/) page is measured.

Close with the same `.cta-row` as the home page: "Talk to us" (`mailto:thaisikhnews@gmail.com`) and "See the live numbers" (`../live/`).

- [ ] **Step 2: Check it**

Open `http://localhost:8765/partner/`. Every price matches the table above. The footnote is present. No number on this page comes from `live.json`, by design — confirm with `grep -c live-data.js site/partner/index.html` returning `0`.

- [ ] **Step 3: Commit**

```bash
git add site/partner/index.html
git commit -m "feat(site): partner page, prices unchanged, guaranteed reach footnoted"
```

---

### Task 9: Deploy to GitHub Pages

**Files:**
- Create: `.github/workflows/pages.yml`
- Create: `infra/github_pages.py`

- [ ] **Step 1: Write the workflow**

`.github/workflows/pages.yml`:

```yaml
name: pages

on:
  push:
    branches: [main]
    paths: ["site/**", "data/live.json", ".github/workflows/pages.yml"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - name: bake the daily live.json into the artifact
        run: |
          mkdir -p site/data
          cp data/live.json site/data/live.json
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - id: deploy
        uses: actions/deploy-pages@v4
```

The collector's daily commit of `data/live.json` therefore redeploys the site once a day with fresh baked numbers, while the hourly Storage copy keeps the live view current between deploys.

- [ ] **Step 2: Keep the baked copy out of git**

Add to `.gitignore`:

```
site/data/live.json
tests/site/shots/
```

`site/data/live.json` only ever exists inside the Actions runner and in local previews. Create the local one by hand when previewing:

```bash
cp data/live.json site/data/live.json
```

- [ ] **Step 3: Write `infra/github_pages.py`**

```python
"""Enable GitHub Pages with the Actions build type. Idempotent. Never prints the token.

Usage: python infra/github_pages.py neramitsingh tsntalks
"""
import json
import sys
import urllib.error
import urllib.request

from github_repo import cached_token


def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "tsntalks-setup"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main(owner: str, repo: str) -> None:
    token = cached_token()
    status, body = api("POST", f"/repos/{owner}/{repo}/pages", token, {"build_type": "workflow"})
    if status == 409:
        status, body = api("PUT", f"/repos/{owner}/{repo}/pages", token, {"build_type": "workflow"})
    if status >= 300 and status != 204:
        raise SystemExit(f"pages setup failed {status}: {body[:300]}")
    status, body = api("GET", f"/repos/{owner}/{repo}/pages", token)
    print(json.dumps({k: json.loads(body).get(k) for k in ("url", "status", "build_type", "html_url")}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
```

- [ ] **Step 4: Enable Pages and deploy**

```bash
python infra/github_pages.py neramitsingh tsntalks
git add .github/workflows/pages.yml infra/github_pages.py .gitignore
git commit -m "ci: publish site/ to GitHub Pages"
git push
```

Expected: the script prints `"build_type": "workflow"` and an `html_url` of `https://neramitsingh.github.io/tsntalks/`.

- [ ] **Step 5: Verify the deploy landed**

```bash
python - <<'PY'
import json, urllib.request
from pathlib import Path
import sys
sys.path.insert(0, "infra")
from github_repo import cached_token
t = cached_token()
req = urllib.request.Request("https://api.github.com/repos/neramitsingh/tsntalks/actions/workflows/pages.yml/runs?per_page=3",
                             headers={"Authorization": f"Bearer {t}", "Accept": "application/vnd.github+json", "User-Agent": "tsn"})
for r in json.load(urllib.request.urlopen(req))["workflow_runs"]:
    print(r["created_at"], r["status"], r["conclusion"], r["html_url"])
PY
curl -s -o /dev/null -w "%{http_code}\n" https://neramitsingh.github.io/tsntalks/
curl -s -o /dev/null -w "%{http_code}\n" https://neramitsingh.github.io/tsntalks/live/
curl -s -o /dev/null -w "%{http_code}\n" https://neramitsingh.github.io/tsntalks/partner/
curl -s -o /dev/null -w "%{http_code}\n" https://neramitsingh.github.io/tsntalks/data/live.json
```

Expected: `completed success` and four `200`s. A `404` on `data/live.json` means the bake step did not run — check the workflow log before continuing.

---

### Task 10: The pages hold up under test

**Files:**
- Create: `tests/site/conftest.py`
- Create: `tests/site/test_pages.py`

- [ ] **Step 1: Write `tests/site/conftest.py`**

```python
"""Serve site/ on a free port and hand every test a page. Storage is stubbed so the
   tests never depend on the network or on today's numbers."""
import json
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
STORAGE = "**/storage/v1/object/public/public/live.json"


@pytest.fixture(scope="session")
def base_url():
    (SITE / "data").mkdir(exist_ok=True)
    (SITE / "data" / "live.json").write_bytes((ROOT / "data" / "live.json").read_bytes())
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(SimpleHTTPRequestHandler, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def live_data():
    return json.loads((ROOT / "data" / "live.json").read_text(encoding="utf-8"))


@pytest.fixture(params=[(1440, 900), (390, 844)], ids=["desktop", "phone"])
def page(request, browser, base_url):
    w, h = request.param
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
    pg = ctx.new_page()
    # The storage copy is the same bytes as the baked copy: deterministic, no network.
    pg.route(STORAGE, lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=(ROOT / "data" / "live.json").read_text(encoding="utf-8")))
    pg.goto(base_url, wait_until="networkidle")
    yield pg
    ctx.close()
```

- [ ] **Step 2: Write `tests/site/test_pages.py`**

```python
import pytest

PAGES = ["/", "/live/", "/partner/"]
SHOTS = __import__("pathlib").Path(__file__).parent / "shots"


@pytest.mark.parametrize("path", PAGES)
def test_no_horizontal_overflow(page, base_url, path):
    page.goto(base_url + path, wait_until="networkidle")
    over = page.evaluate("""() => {
      const w = document.documentElement.clientWidth;
      return [...document.querySelectorAll('body *')]
        .filter(el => el.getBoundingClientRect().right > w + 1
                   && getComputedStyle(el.parentElement).overflowX !== 'auto')
        .map(el => el.tagName + '.' + el.className).slice(0, 5);
    }""")
    assert over == [], f"{path} overflows: {over}"
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


@pytest.mark.parametrize("path", PAGES)
def test_display_and_text_fonts_load(page, base_url, path):
    page.goto(base_url + path, wait_until="networkidle")
    assert page.evaluate("document.fonts.check('600 48px \"Bodoni Moda\"')")
    assert page.evaluate("document.fonts.check('500 16px \"Hanken Grotesk\"')")


def test_home_hero_is_the_newest_episode(page, base_url, live_data):
    page.goto(base_url + "/", wait_until="networkidle")
    newest = max(live_data["episodes"], key=lambda e: e["published_at"])
    assert page.inner_text("#guest").strip() == newest["guest"]


def test_home_strap_carries_the_real_totals(page, base_url, live_data):
    page.goto(base_url + "/", wait_until="networkidle")
    strap = page.inner_text("#strap")
    assert f"{live_data['total_views']:,}" in strap
    assert f"{live_data['total_followers']:,}" in strap
    assert f"{len(live_data['episodes'])} episodes" in strap


def test_every_season_one_episode_has_a_role(page, base_url, live_data):
    page.goto(base_url + "/", wait_until="networkidle")
    roles = page.eval_on_selector_all("#s1 li small", "els => els.map(e => e.textContent.trim())")
    assert len(roles) == sum(1 for e in live_data["episodes"] if e["season"] == 1)
    assert all(roles), "a season-one episode rendered with an empty role"


def test_poster_wall_has_one_big_and_two_mid(page, base_url):
    page.goto(base_url + "/", wait_until="networkidle")
    assert page.locator("#wall .po.big").count() == 1
    assert page.locator("#wall .po.mid").count() == 2


def test_live_chart_has_a_table_twin_with_the_same_months(page, base_url, live_data):
    page.goto(base_url + "/live/", wait_until="networkidle")
    cols = page.locator("#cols .col").count()
    rows = page.locator("#monthstab tr").count() - 1          # minus the header row
    assert cols == rows == len({r["m"] for r in live_data["months"]})


def test_partner_carries_no_live_numbers(page, base_url):
    page.goto(base_url + "/partner/", wait_until="networkidle")
    assert page.locator("script[src*='live-data']").count() == 0
    for price in ["฿25,000", "฿15,000", "฿185,000", "฿109,000"]:
        assert price in page.content()


def test_reduced_motion_stops_every_animation(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(base_url + "/", wait_until="networkidle")
    running = pg.evaluate("""() => [...document.querySelectorAll('*')]
        .flatMap(el => el.getAnimations({subtree: false}))
        .filter(a => a.playState === 'running').length""")
    assert running == 0
    ctx.close()


@pytest.mark.parametrize("path,name", list(zip(PAGES, ["home", "live", "partner"])))
def test_screenshot(page, base_url, path, name):
    SHOTS.mkdir(exist_ok=True)
    page.goto(base_url + path, wait_until="networkidle")
    page.wait_for_timeout(600)                                 # let the fonts settle
    w = page.viewport_size["width"]
    page.screenshot(path=str(SHOTS / f"{name}-{'desk' if w > 800 else 'mobile'}.png"), full_page=True)
```

- [ ] **Step 3: Run the suite**

```bash
python -m pip install pytest playwright
python -m playwright install chromium
python -m pytest tests/site -q
```

Expected: all pass. The screenshots land in `tests/site/shots/`.

- [ ] **Step 4: Look at the six screenshots**

Open every file in `tests/site/shots/`. A green suite is not the ship bar — the ship bar is Ney's eye on the page. Specifically check: the hero crop puts the guest's face in frame, the poster wall has no awkward gap in its last row, the `/live` columns are readable at 390px, and no text is clipped.

- [ ] **Step 5: Commit**

```bash
git add tests/site/conftest.py tests/site/test_pages.py
git commit -m "test(site): overflow, fonts, numbers, reduced motion, screenshots"
```

---

### Task 11: Reconcile against Zernio, then ship

The spec's launch gate: every number on the home page is checked against Zernio's own dashboard before the site is called done.

- [ ] **Step 1: Print what the site claims**

```bash
PYTHONIOENCODING=utf-8 python -c "
import json; d=json.load(open('data/live.json',encoding='utf-8'))
print('total views     ', f\"{d['total_views']:,}\")
print('total followers ', f\"{d['total_followers']:,}\")
for k,v in sorted(d['platforms'].items()):
    print(f'  {k:<10} {v[\"followers\"]:>7,} followers  {v[\"views\"]:>10,} views  {v[\"posts\"]:>4} posts')
print('episodes        ', len(d['episodes']))
print('fetched at      ', d['fetched_at'])
"
```

- [ ] **Step 2: Compare each line against Zernio**

Open Zernio in Sunny's account and read the same six figures. Note any gap over 1%. Expected gaps and their explanations, so a small difference is not chased:

- **YouTube views**: the site counts every video Zernio has synced plus the catalogue backfill; Zernio's dashboard counts only what it imported. The site's figure should be the larger one.
- **Any platform's views**: platforms report with up to 48 hours of delay, and the two systems read at different times.
- **Follower counts** should agree exactly. A mismatch here is a bug — stop and find it before launching.

- [ ] **Step 3: Click through the deployed site**

On the desktop at `https://neramitsingh.github.io/tsntalks/`, and again on the phone:

- [ ] Home: hero image loads, "Watch the episode" opens the right YouTube video
- [ ] Home: every poster tile opens its own episode
- [ ] Home: nav "Live numbers" and "Partner" both land
- [ ] Live: column chart scrolls on the phone, table twin opens
- [ ] Live: every platform link in the legend opens the right account
- [ ] Partner: "Talk to us" opens a mail composer to `thaisikhnews@gmail.com`
- [ ] All three: the strap or footer shows a timestamp within the last hour

- [ ] **Step 4: Record the result**

Update `04 Projects/TSN Talks/TSN Talks.md` and `11 AI/Tasks/TASK-D271.md` in the vault: Plan 2 live, the URL, what reconciled and what did not, and the remaining open items (clean stills, founder portrait, domain). Commit the vault.

- [ ] **Step 5: Send Sunny the link**

Not automatic. Draft the message for Ney and let him send it — the client relationship is his.

---

## Self-review

**Spec coverage.** 3.1 home → Task 6 (all seven blocks). 3.2 live → Task 7 (all five blocks). 3.3 partner → Task 8 (five options, five bundles, footnote, prices unchanged). 6 site build → Tasks 4, 5, 9 (one `site.css`, no build step, pinned fonts, still overrides, three animations, AA contrast). 7 failure handling → Task 5 `load()` and `freshness()`, Task 6 `.stale` strap. 8 testing → Task 10 (screenshots at 1440 and 390, no overflow, fonts) and Task 11 (reconciliation, click-through). 10 step 2 → the whole plan.

Not covered, deliberately: `analytics.css` and the dashboard are Plan 3; the domain is Plan 4; the YouTube Data API key stays open (yt-dlp covers the catalogue and nothing on these three pages needs the Data API).

**Named gaps carried forward.** Clean episode stills and a founder portrait from Sunny — the override folder and its README exist so a file drop is the whole change. The Open Graph image is a static URL refreshed by hand; making it dynamic needs a build step the spec rules out.

**Type consistency.** `full`, `compact`, `pct`, `bkk`, `bkkStamp`, `freshness`, `stills`, `stillImage`, `load`, `PLATFORMS`, `PLATFORM_NAME`, `PLATFORM_COLOR`, `PLATFORM_HANDLE`, `PLATFORM_URL` are defined once in Task 5 and used under those exact names in Tasks 6 and 7. `load_episode_overrides` and `override_rows` are defined in Task 1 and re-used by the CLI command in the same task. The `episodes[]` fields consumed by the pages — `url`, `thumb`, `published_at` — are the ones Task 2 adds to `live_json()`.
