# TSN Talks Plan 1: Collector and Database

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An hourly GitHub Action that reads TSN Talks' numbers from Zernio and YouTube into a Supabase Postgres database, keeps hourly snapshots, and publishes a `live.json` the public site can read.

**Architecture:** A small Python package `collector/` with pure transform functions (API JSON in, table rows out) tested against recorded fixtures, thin API clients for Zernio, YouTube (yt-dlp) and Supabase (PostgREST over HTTPS), and a CLI with `collect`, `backfill-youtube`, `publish-live-json` and `health` commands. Schema, row-level security and rollup functions live in versioned SQL files applied through Supabase's Management API. GitHub Actions runs the CLI on a cron.

**Tech Stack:** Python 3.12, `requests`, `yt-dlp`, `pytest`, Supabase (Postgres 15, PostgREST, Storage, Auth), GitHub Actions. No ORM, no framework.

**Spec:** `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` sections 2, 4, 5, 7, 8, 10 (step 1).

**Who runs what:** Tasks 1, 2 and 11 touch Ney's secrets (Supabase PAT, GitHub token, Zernio key) and run inline on the laptop. Tasks 3 to 10 are pure code with fixtures and can run on the desktop through `remote-lane` as M3 workers; each one ends with `pytest` green.

**Secrets convention:** nothing secret is ever printed, committed, or written under the repo. Local runs read `.env` in `collector/` (gitignored). GitHub Actions reads repository secrets.

---

## File structure

```
tsntalks/                          (repo root, Ney's GitHub: neramitsingh/tsntalks)
  .github/workflows/collect.yml    hourly collector + daily live.json commit
  .gitignore                       add collector/.env, collector/.venv, __pycache__
  db/
    001_schema.sql                 tables + indexes
    002_rls.sql                    allowed_users, is_allowed(), policies
    003_functions.sql              rollup_views(), live_json(), thin_snapshots()
  infra/
    supabase_create.py             one-off: create project, wait, store keys in ~/.secrets (never prints keys)
    apply_sql.py                   apply db/*.sql through the Management API
    github_repo.py                 one-off: create the GitHub repo with the cached git credential
  collector/
    pyproject.toml
    .env.example
    tsn_collector/
      __init__.py
      config.py                    env → Settings
      zernio.py                    Zernio client (GET wrappers, paging)
      youtube.py                   yt-dlp catalogue + per-video stats
      supa.py                      PostgREST upsert/select/rpc + Storage upload
      transform.py                 pure: API JSON → rows
      episodes.py                  pure: title parsing, post↔episode matching
      run.py                       the hourly run, orchestration only
      backfill.py                  one-off YouTube history
      cli.py                       argparse entry point
    tests/
      fixtures/                    recorded responses (copied from the 2026-09-14 pulls)
      test_transform.py
      test_episodes.py
      test_supa.py
      test_run.py
  data/live.json                   daily committed copy (written by the Action)
```

Fixtures to copy from the laptop scratchpad `C:\Users\Ney\AppData\Local\Temp\claude\C--Users-Ney-Ney-Digital-Brain\66df03a5-1dca-4701-b15e-07f4174201b4\scratchpad\` into `collector/tests/fixtures/` before Task 3 (Ney does this inline; workers cannot see the scratchpad):

| Scratchpad file | Fixture name |
|---|---|
| `s2_v1_accounts.json` | `accounts.json` |
| `s2_v1_accounts_health.json` | `health.json` |
| `s2_v1_accounts_follower-stats.json` | `follower_stats.json` |
| `an_youtube.json` | `analytics_youtube.json` |
| `an_instagram.json` | `analytics_instagram.json` |
| `an_tiktok.json` | `analytics_tiktok.json` |
| `yt_channel.json` | `yt_channel_insights.json` |
| `yt_demo.json` | `yt_demographics.json` |
| `ig_demo.json` | `ig_demographics.json` |
| `ig_acct.json` | `ig_account_insights.json` |
| `tt_acct.json` | `tt_account_insights.json` |
| `ytdlp_videos.json` | `ytdlp_flat.json` |

---

### Task 1: Repository under Ney's GitHub

**Files:**
- Create: `infra/github_repo.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the repo creation script**

`infra/github_repo.py`:

```python
"""Create the GitHub repo for this project using the token git already has cached.

Usage: python infra/github_repo.py neramitsingh tsntalks
Never prints the token.
"""
import json
import subprocess
import sys
import urllib.request


def cached_token(host: str = "github.com") -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input=f"protocol=https\nhost={host}\n\n",
        capture_output=True, text=True, check=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no cached GitHub credential; run `git push` once by hand")


def create_repo(owner: str, name: str, token: str) -> str:
    body = json.dumps({
        "name": name,
        "description": "TSN Talks: live media kit and analytics",
        "private": False,
        "has_issues": True,
        "has_wiki": False,
        "auto_init": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/user/repos", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "tsntalks-setup"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)["clone_url"]
    except urllib.error.HTTPError as e:
        if e.code == 422:  # already exists
            return f"https://github.com/{owner}/{name}.git"
        raise


if __name__ == "__main__":
    owner, name = sys.argv[1], sys.argv[2]
    url = create_repo(owner, name, cached_token())
    print("repo:", url)
```

- [ ] **Step 2: Add ignores**

Append to `.gitignore`:

```
collector/.env
collector/.venv/
__pycache__/
*.pyc
.pytest_cache/
sketches/out/
sketches/shots/
```

- [ ] **Step 3: Create the repo and push**

Run from the repo root:

```bash
python infra/github_repo.py neramitsingh tsntalks
git remote rename origin upstream
git remote add origin https://github.com/neramitsingh/tsntalks.git
git branch -M live-dashboard main
git push -u origin main
```

Expected: `repo: https://github.com/neramitsingh/tsntalks.git`, then a normal push summary ending in `main -> main`. `upstream` still points at Sunny's repo for reference; never push there.

- [ ] **Step 4: Commit**

```bash
git add infra/github_repo.py .gitignore
git commit -m "chore(infra): repo bootstrap script and ignores"
git push
```

---

### Task 2: Supabase project

**Files:**
- Create: `infra/supabase_create.py`
- Create: `infra/apply_sql.py`

- [ ] **Step 1: Write the project creation script**

`infra/supabase_create.py`:

```python
"""Create the Supabase project for TSN Talks in Ney's org and store its keys locally.

Usage: python infra/supabase_create.py
Reads the Management PAT from ~/.secrets/secrets.md (line containing 'sbp_').
Writes url/anon/service keys + db password to ~/.secrets/secrets.md under the TSN Talks section.
Never prints any key.
"""
import json
import re
import secrets
import time
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".secrets" / "secrets.md"
API = "https://api.supabase.com/v1"
ORG_ID = "sxjdvgmuuwtpdwmhnjop"
NAME = "tsntalks"
REGION = "ap-southeast-1"


def pat() -> str:
    m = re.search(r"sbp_[a-f0-9]{40}", SECRETS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("no Supabase PAT in secrets store")
    return m.group(0)


def call(method: str, path: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def find_project(token: str):
    for p in call("GET", "/projects", token):
        if p["name"] == NAME:
            return p
    return None


def main():
    token = pat()
    proj = find_project(token)
    db_pass = None
    if proj is None:
        db_pass = secrets.token_urlsafe(24)
        proj = call("POST", "/projects", token, {
            "name": NAME, "organization_id": ORG_ID, "region": REGION,
            "db_pass": db_pass, "plan": "free",
        })
        print("created project", proj["id"])
    ref = proj["id"]
    for _ in range(60):
        status = call("GET", f"/projects/{ref}", token)["status"]
        if status == "ACTIVE_HEALTHY":
            break
        time.sleep(10)
    else:
        raise SystemExit(f"project {ref} not healthy in time")
    keys = {k["name"]: k["api_key"] for k in call("GET", f"/projects/{ref}/api-keys", token)}
    url = f"https://{ref}.supabase.co"
    block = (
        f"- Supabase project `{NAME}` ref `{ref}` (Ney's org, {REGION}); URL `{url}`\n"
        f"  - anon key: `{keys['anon']}`\n"
        f"  - service_role key (collector only, GitHub secret SUPABASE_SERVICE_ROLE_KEY): `{keys['service_role']}`\n"
        + (f"  - db password: `{db_pass}`\n" if db_pass else "")
    )
    text = SECRETS.read_text(encoding="utf-8")
    marker = "## TSN Talks (Sunny's podcast) / Zernio\n"
    if f"ref `{ref}`" not in text:
        text = text.replace(marker, marker + block)
        SECRETS.write_text(text, encoding="utf-8")
    print("project ready:", ref, url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the SQL applier**

`infra/apply_sql.py`:

```python
"""Apply db/*.sql to the tsntalks Supabase project through the Management API.

Usage: python infra/apply_sql.py            # applies all files in order
       python infra/apply_sql.py db/003_functions.sql
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".secrets" / "secrets.md"
API = "https://api.supabase.com/v1"


def read_secret(pattern: str) -> str:
    m = re.search(pattern, SECRETS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"missing secret matching {pattern}")
    return m.group(1)


def run_sql(ref: str, token: str, sql: str):
    req = urllib.request.Request(
        f"{API}/projects/{ref}/database/query", data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main(paths):
    token = read_secret(r"(sbp_[a-f0-9]{40})")
    ref = read_secret(r"Supabase project `tsntalks` ref `([a-z]+)`")
    for p in paths:
        sql = Path(p).read_text(encoding="utf-8")
        run_sql(ref, token, sql)
        print("applied", p)


if __name__ == "__main__":
    files = sys.argv[1:] or sorted(str(p) for p in Path("db").glob("*.sql"))
    main(files)
```

- [ ] **Step 3: Create the project**

Run: `python infra/supabase_create.py`
Expected: `created project <ref>` then, within a few minutes, `project ready: <ref> https://<ref>.supabase.co`. Confirm the secrets file now has the TSN Talks Supabase block (open it, don't paste it anywhere).

- [ ] **Step 4: Commit**

```bash
git add infra/supabase_create.py infra/apply_sql.py
git commit -m "chore(infra): supabase project bootstrap and sql applier"
git push
```

---

### Task 3: Database schema

**Files:**
- Create: `db/001_schema.sql`

- [ ] **Step 1: Write the schema**

`db/001_schema.sql`:

```sql
create table if not exists accounts (
  id text primary key,
  platform text not null check (platform in ('youtube','instagram','tiktok')),
  handle text not null,
  display_name text,
  avatar_url text,
  connected_at timestamptz,
  active boolean not null default true
);

create table if not exists account_snapshots (
  account_id text not null references accounts(id),
  taken_at timestamptz not null,
  followers integer,
  following integer,
  total_likes bigint,
  post_count integer,
  primary key (account_id, taken_at)
);

create table if not exists episodes (
  id serial primary key,
  season integer not null,
  number text not null,
  title text not null,
  guest text not null,
  role text not null default '',
  youtube_video_id text unique not null,
  published_at timestamptz,
  match_terms text[] not null default '{}',
  unique (season, number)
);

create table if not exists posts (
  id text primary key,
  account_id text references accounts(id),
  platform text not null check (platform in ('youtube','instagram','tiktok')),
  platform_post_id text,
  url text,
  title text,
  media_type text,
  published_at timestamptz,
  thumb_url text,
  episode_id integer references episodes(id),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index if not exists posts_published_idx on posts (published_at desc);
create index if not exists posts_episode_idx on posts (episode_id);

create table if not exists post_snapshots (
  post_id text not null references posts(id),
  taken_at timestamptz not null,
  views bigint,
  likes integer,
  comments integer,
  shares integer,
  saves integer,
  reach bigint,
  impressions bigint,
  engagement_rate numeric,
  primary key (post_id, taken_at)
);
create index if not exists post_snapshots_taken_idx on post_snapshots (taken_at);

create table if not exists metric_daily (
  account_id text not null references accounts(id),
  day date not null,
  metric text not null,
  value numeric not null,
  primary key (account_id, day, metric)
);

create table if not exists demographics (
  account_id text not null references accounts(id),
  kind text not null,
  dimension text not null,
  value numeric not null,
  window_start date not null,
  window_end date not null,
  taken_at timestamptz not null default now(),
  primary key (account_id, kind, dimension, window_start, window_end)
);

create table if not exists collector_runs (
  id bigserial primary key,
  started_at timestamptz not null,
  finished_at timestamptz,
  status text not null default 'running',
  rows_written integer not null default 0,
  notes jsonb not null default '{}'::jsonb
);

create table if not exists account_health (
  account_id text not null references accounts(id),
  checked_at timestamptz not null,
  status text not null,
  can_fetch_analytics boolean,
  needs_reconnect boolean,
  token_expires_at timestamptz,
  primary key (account_id, checked_at)
);
```

- [ ] **Step 2: Apply and verify**

Run: `python infra/apply_sql.py db/001_schema.sql`
Expected: `applied db/001_schema.sql`

Run a check:

```bash
python - <<'EOF'
import subprocess, json
from infra.apply_sql import read_secret, run_sql
ref = read_secret(r"Supabase project `tsntalks` ref `([a-z]+)`"); tok = read_secret(r"(sbp_[a-f0-9]{40})")
rows = run_sql(ref, tok, "select table_name from information_schema.tables where table_schema='public' order by 1")
print([r['table_name'] for r in rows])
EOF
```

Expected: `['account_health', 'account_snapshots', 'accounts', 'collector_runs', 'demographics', 'episodes', 'metric_daily', 'post_snapshots', 'posts']`

- [ ] **Step 3: Commit**

```bash
git add db/001_schema.sql
git commit -m "feat(db): core schema"
git push
```

---

### Task 4: Row-level security and allowed users

**Files:**
- Create: `db/002_rls.sql`

- [ ] **Step 1: Write the policies**

`db/002_rls.sql`:

```sql
create table if not exists allowed_users (
  email text primary key,
  name text
);

create or replace function is_allowed() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from allowed_users a
    where lower(a.email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

do $$
declare t text;
begin
  foreach t in array array['accounts','account_snapshots','episodes','posts','post_snapshots',
                           'metric_daily','demographics','collector_runs','account_health','allowed_users']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists read_allowed on %I', t);
    execute format('create policy read_allowed on %I for select to authenticated using (is_allowed())', t);
  end loop;
end $$;

-- The collector writes with the service role, which bypasses RLS. Anonymous users get nothing.
insert into allowed_users (email, name) values
  ('neramit.manu@gmail.com', 'Ney')
on conflict (email) do nothing;
```

Sunny's email is added the day he first signs in; add it with `insert into allowed_users values ('<his email>', 'Sunny')` through `apply_sql.py` on a one-line file.

- [ ] **Step 2: Apply and verify**

Run: `python infra/apply_sql.py db/002_rls.sql`
Expected: `applied db/002_rls.sql`

Verify with the anon key that nothing leaks:

```bash
python - <<'EOF'
import re, urllib.request, json
from pathlib import Path
t = Path.home().joinpath('.secrets/secrets.md').read_text(encoding='utf-8')
url = re.search(r"URL `(https://[a-z]+\.supabase\.co)`", t).group(1); anon = re.search(r"anon key: `([^`]+)`", t).group(1)
req = urllib.request.Request(f"{url}/rest/v1/accounts?select=id", headers={"apikey": anon, "Authorization": f"Bearer {anon}"})
print(json.load(urllib.request.urlopen(req)))
EOF
```

Expected: `[]` (empty list, no error).

- [ ] **Step 3: Commit**

```bash
git add db/002_rls.sql
git commit -m "feat(db): row-level security with allowed_users"
git push
```

---

### Task 5: Collector package skeleton, config, Supabase client

**Files:**
- Create: `collector/pyproject.toml`, `collector/.env.example`, `collector/tsn_collector/__init__.py`, `collector/tsn_collector/config.py`, `collector/tsn_collector/supa.py`
- Test: `collector/tests/test_supa.py`

- [ ] **Step 1: Package metadata**

`collector/pyproject.toml`:

```toml
[project]
name = "tsn-collector"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["requests>=2.32", "yt-dlp>=2026.3.17"]

[project.optional-dependencies]
dev = ["pytest>=8", "responses>=0.25"]

[project.scripts]
tsn-collect = "tsn_collector.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["tsn_collector*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`collector/.env.example`:

```
ZERNIO_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@TSNTalksTH/videos
TZ_NAME=Asia/Bangkok
```

`collector/tsn_collector/__init__.py`: empty file.

- [ ] **Step 2: Config**

`collector/tsn_collector/config.py`:

```python
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
```

- [ ] **Step 3: Write the failing Supabase client test**

`collector/tests/test_supa.py`:

```python
import json

import responses

from tsn_collector.supa import Supa

URL = "https://example.supabase.co"


@responses.activate
def test_upsert_chunks_and_sets_merge_headers():
    calls = []

    def cb(req):
        calls.append((req.url, req.headers["Prefer"], json.loads(req.body)))
        return (201, {}, "")

    responses.add_callback(responses.POST, f"{URL}/rest/v1/post_snapshots", callback=cb)
    s = Supa(URL, "svc", chunk=2)
    rows = [{"post_id": f"p{i}", "taken_at": "t", "views": i} for i in range(5)]
    n = s.upsert("post_snapshots", rows, on_conflict="post_id,taken_at")
    assert n == 5
    assert len(calls) == 3
    assert calls[0][0].endswith("on_conflict=post_id%2Ctaken_at")
    assert calls[0][1] == "resolution=merge-duplicates,return=minimal"
    assert [len(c[2]) for c in calls] == [2, 2, 1]


@responses.activate
def test_upsert_empty_is_noop():
    s = Supa(URL, "svc")
    assert s.upsert("posts", [], on_conflict="id") == 0
    assert len(responses.calls) == 0


@responses.activate
def test_select_and_rpc():
    responses.add(responses.GET, f"{URL}/rest/v1/accounts", json=[{"id": "a"}])
    responses.add(responses.POST, f"{URL}/rest/v1/rpc/live_json", json={"ok": True})
    s = Supa(URL, "svc")
    assert s.select("accounts", select="id") == [{"id": "a"}]
    assert s.rpc("live_json", {}) == {"ok": True}
    assert responses.calls[0].request.headers["apikey"] == "svc"
```

- [ ] **Step 4: Run to verify it fails**

Run (from `collector/`): `python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" && .venv/Scripts/python -m pytest tests/test_supa.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tsn_collector.supa'`

- [ ] **Step 5: Implement the client**

`collector/tsn_collector/supa.py`:

```python
from __future__ import annotations

import json
from typing import Any

import requests


class Supa:
    """Thin PostgREST + Storage client using the service-role key."""

    def __init__(self, url: str, service_key: str, chunk: int = 500, timeout: int = 60):
        self.url = url.rstrip("/")
        self.key = service_key
        self.chunk = chunk
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"apikey": service_key, "Authorization": f"Bearer {service_key}"})

    def upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> int:
        if not rows:
            return 0
        n = 0
        for i in range(0, len(rows), self.chunk):
            batch = rows[i:i + self.chunk]
            r = self.s.post(
                f"{self.url}/rest/v1/{table}", params={"on_conflict": on_conflict},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal", "Content-Type": "application/json"},
                data=json.dumps(batch, default=str), timeout=self.timeout,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"upsert {table} failed {r.status_code}: {r.text[:300]}")
            n += len(batch)
        return n

    def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        r = self.s.post(f"{self.url}/rest/v1/{table}", headers={"Prefer": "return=representation",
                        "Content-Type": "application/json"}, data=json.dumps(row, default=str), timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"insert {table} failed {r.status_code}: {r.text[:300]}")
        return r.json()[0]

    def update(self, table: str, match: dict[str, Any], values: dict[str, Any]) -> None:
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = self.s.patch(f"{self.url}/rest/v1/{table}", params=params, headers={"Prefer": "return=minimal",
                         "Content-Type": "application/json"}, data=json.dumps(values, default=str), timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"update {table} failed {r.status_code}: {r.text[:300]}")

    def select(self, table: str, **params: Any) -> list[dict[str, Any]]:
        r = self.s.get(f"{self.url}/rest/v1/{table}", params=params, timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"select {table} failed {r.status_code}: {r.text[:300]}")
        return r.json()

    def rpc(self, fn: str, args: dict[str, Any]) -> Any:
        r = self.s.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"rpc {fn} failed {r.status_code}: {r.text[:300]}")
        return r.json()

    def upload_public(self, bucket: str, path: str, data: bytes, content_type: str, max_age: int = 300) -> None:
        r = self.s.post(f"{self.url}/storage/v1/object/{bucket}/{path}", data=data, timeout=self.timeout,
                        headers={"Content-Type": content_type, "x-upsert": "true", "cache-control": f"max-age={max_age}"})
        if r.status_code >= 300:
            raise RuntimeError(f"upload {bucket}/{path} failed {r.status_code}: {r.text[:300]}")
```

- [ ] **Step 6: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_supa.py -q`
Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add collector/pyproject.toml collector/.env.example collector/tsn_collector/__init__.py collector/tsn_collector/config.py collector/tsn_collector/supa.py collector/tests/test_supa.py
git commit -m "feat(collector): package skeleton, settings, supabase client"
git push
```

---

### Task 6: Transform functions (API JSON to rows)

**Files:**
- Create: `collector/tsn_collector/transform.py`
- Test: `collector/tests/test_transform.py`
- Fixtures: `collector/tests/fixtures/*.json` (copied per the table at the top)

- [ ] **Step 1: Write the failing tests**

`collector/tests/test_transform.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tsn_collector import transform as T

FX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc)


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_account_rows():
    rows = T.account_rows(fx("accounts.json")["accounts"])
    ig = next(r for r in rows if r["platform"] == "instagram")
    assert ig["id"] == "6aa7d545726ebfe037e9d502"
    assert ig["handle"] == "tsntalks"
    assert ig["display_name"] == "TSN Talks"
    assert ig["active"] is True
    assert ig["connected_at"].startswith("2026-09-14")


def test_account_snapshot_rows():
    rows = T.account_snapshot_rows(fx("follower_stats.json"), NOW)
    by = {r["account_id"]: r for r in rows}
    assert by["6aa7d4ef726ebfe037e9d35c"]["followers"] == 6098
    assert by["6aa7d50c726ebfe037e9d45c"]["followers"] == 2350
    assert all(r["taken_at"] == NOW.isoformat() for r in rows)


def test_post_key():
    assert T.post_key("youtube", "https://www.youtube.com/watch?v=PpnI7_--PUg", "z1") == "yt:PpnI7_--PUg"
    assert T.post_key("instagram", "https://www.instagram.com/reel/DO0ULVGEzt6/", "z2") == "ig:DO0ULVGEzt6"
    assert T.post_key("instagram", "https://www.instagram.com/p/DRJt3KGE7bH/", "z3") == "ig:DRJt3KGE7bH"
    assert T.post_key("tiktok", "https://www.tiktok.com/@tsntalks.th/video/7608030276714774544?utm_source=x", "z4") == "tt:7608030276714774544"
    assert T.post_key("tiktok", None, "z5") == "zr:z5"


def test_post_rows_youtube():
    posts, snaps = T.post_rows(fx("analytics_youtube.json"), "youtube", "6aa7d50c726ebfe037e9d45c", NOW)
    assert len(posts) == 48 and len(snaps) == 48
    top = max(snaps, key=lambda s: s["views"])
    assert top["views"] == 71444 and top["post_id"] == "yt:PpnI7_--PUg"
    p = next(x for x in posts if x["id"] == "yt:PpnI7_--PUg")
    assert p["platform_post_id"] == "PpnI7_--PUg"
    assert p["published_at"].startswith("2025-09-20")
    assert p["title"].startswith("TSN Talks Ep. 13")
    assert p["account_id"] == "6aa7d50c726ebfe037e9d45c"


def test_post_rows_tiktok_reach():
    posts, snaps = T.post_rows(fx("analytics_tiktok.json"), "tiktok", "6aa7d4ef726ebfe037e9d35c", NOW)
    top = max(snaps, key=lambda s: s["views"])
    assert top["views"] == 943699 and top["reach"] == 766117 and top["likes"] == 64327


def test_yt_channel_metric_rows():
    rows = T.yt_channel_metric_rows(fx("yt_channel_insights.json"), "6aa7d50c726ebfe037e9d45c")
    # fixture was fetched as total_value, so no per-day rows are produced
    assert rows == []


def test_yt_channel_metric_rows_time_series():
    payload = {"metrics": {"views": {"values": [{"date": "2026-09-01", "value": 100}, {"date": "2026-09-02", "value": 50}]},
                           "subscribersGained": {"values": [{"date": "2026-09-01", "value": 3}]}}}
    rows = T.yt_channel_metric_rows(payload, "acc")
    assert {"account_id": "acc", "day": "2026-09-01", "metric": "yt_views", "value": 100} in rows
    assert {"account_id": "acc", "day": "2026-09-01", "metric": "yt_subs_gained", "value": 3} in rows
    assert len(rows) == 3


def test_demographic_rows_youtube():
    rows = T.demographic_rows("yt", fx("yt_demographics.json")["demographics"], "acc", "2025-09-14", "2026-09-11", NOW)
    age = [r for r in rows if r["kind"] == "yt_age"]
    assert {r["dimension"]: r["value"] for r in age}["25-34"] == 38.1
    country = {r["dimension"]: r["value"] for r in rows if r["kind"] == "yt_country"}
    assert country["IN"] == 70183 and country["TH"] == 57519
    assert all(r["window_start"] == "2025-09-14" and r["window_end"] == "2026-09-11" for r in rows)


def test_demographic_rows_instagram_skips_empty_dims():
    rows = T.demographic_rows("ig", fx("ig_demographics.json")["demographics"], "acc", "2026-09-01", "2026-09-14", NOW)
    kinds = {r["kind"] for r in rows}
    assert kinds == {"ig_age", "ig_city", "ig_country", "ig_gender"}
    city = {r["dimension"]: r["value"] for r in rows if r["kind"] == "ig_city"}
    assert city["Bangkok, Bangkok"] == 509


def test_series_metric_rows():
    payload = {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 6098}]},
                           "likes_count": {"total": 109909}}}
    rows = T.series_metric_rows(payload, "acc", {"follower_count": "tt_followers", "likes_count": "tt_likes"})
    assert rows == [{"account_id": "acc", "day": "2026-09-14", "metric": "tt_followers", "value": 6098}]


def test_health_rows():
    rows = T.health_rows(fx("health.json"), NOW)
    tt = next(r for r in rows if r["account_id"] == "6aa7d4ef726ebfe037e9d35c")
    assert tt["status"] == "healthy" and tt["needs_reconnect"] is False and tt["can_fetch_analytics"] is True
    assert tt["token_expires_at"].startswith("2026-09-15")
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_transform.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tsn_collector.transform'`

- [ ] **Step 3: Implement transform**

`collector/tsn_collector/transform.py`:

```python
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_transform.py -q`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add collector/tsn_collector/transform.py collector/tests/test_transform.py collector/tests/fixtures
git commit -m "feat(collector): transforms from Zernio JSON to rows, with recorded fixtures"
git push
```

---

### Task 7: Episode parsing and clip matching

**Files:**
- Create: `collector/tsn_collector/episodes.py`
- Test: `collector/tests/test_episodes.py`

- [ ] **Step 1: Write the failing tests**

`collector/tests/test_episodes.py`:

```python
from tsn_collector import episodes as E


def test_parse_season2_colon():
    r = E.parse_title("TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love")
    assert r == E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder & CEO, Spark.love")


def test_parse_season2_comma():
    r = E.parse_title("TSN Talks S2 E9, Mr. Deepak Sajnani, President of Thai-Sindh Association")
    assert r.season == 2 and r.number == "9" and r.guest == "Mr. Deepak Sajnani"
    assert r.role == "President of Thai-Sindh Association"


def test_parse_season1_dash():
    r = E.parse_title("TSN Talks Ep. 03 - Kirty Khanijou")
    assert r == E.Parsed(season=1, number="03", guest="Kirty Khanijou", role="")


def test_parse_season1_colon_with_paren():
    r = E.parse_title("TSN TALKS Ep. 01: Dhammandeep Singh Khanijaun (Dan)")
    assert r.season == 1 and r.number == "01" and r.guest == "Dhammandeep Singh Khanijaun (Dan)"


def test_parse_part_suffix():
    r = E.parse_title("TSN Talks Ep. 13 - Dr. Sunil (Part 2)")
    assert r.number == "13" and r.guest == "Dr. Sunil (Part 2)"


def test_parse_non_episode_returns_none():
    assert E.parse_title("This week on TSN Talks 🎙 we sit down with...") is None
    assert E.parse_title("TSN Talks Season 1 Finale Lineup!") is None


def test_match_terms():
    p = E.Parsed(season=2, number="10", guest="Sunny Khurana", role="Founder")
    assert E.match_terms(p) == ["sunny khurana", "khurana", "s2 e10"]
    p1 = E.Parsed(season=1, number="03", guest="Kirty Khanijou", role="")
    assert E.match_terms(p1) == ["kirty khanijou", "khanijou", "ep 03", "ep. 03", "episode 03", "episode 3"]


def test_match_post_prefers_full_name_then_surname():
    eps = [
        {"id": 1, "match_terms": ["sunny khurana", "khurana", "s2 e10"]},
        {"id": 2, "match_terms": ["major sukit khurana", "khurana", "ep 19"]},
    ]
    assert E.match_post("Major Sukit Khurana opens up", eps) == 2
    assert E.match_post("In Episode 19, Major Sukrit opens up", eps) is None
    assert E.match_post("Sunny Khurana on love", eps) == 1
    assert E.match_post("Khurana speaks", eps) is None  # ambiguous surname, no match
    assert E.match_post(None, eps) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_episodes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tsn_collector.episodes'`

- [ ] **Step 3: Implement**

`collector/tsn_collector/episodes.py`:

```python
"""Episode titles → episodes rows; post titles → episode ids. Pure functions."""
from __future__ import annotations

import re
from dataclasses import dataclass

TITLE_RE = re.compile(
    r"^\s*TSN\s*TALKS\s*(?:S(?P<s>\d+)\s*E(?P<e>\d+)|Ep\.?\s*(?P<n>\d+))\s*[:\-–,]\s*(?P<rest>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Parsed:
    season: int
    number: str
    guest: str
    role: str


def parse_title(title: str | None) -> Parsed | None:
    if not title:
        return None
    m = TITLE_RE.match(title.splitlines()[0])
    if not m:
        return None
    rest = m.group("rest")
    if m.group("s"):
        season, number = int(m.group("s")), m.group("e")
    else:
        season, number = 1, m.group("n")
    if "," in rest:
        guest, role = rest.split(",", 1)
    else:
        guest, role = rest, ""
    return Parsed(season=season, number=number, guest=guest.strip(), role=role.strip())


def match_terms(p: Parsed) -> list[str]:
    name = re.sub(r"\s*\(.*?\)\s*", " ", p.guest).strip().lower()
    words = [w for w in name.split() if w not in {"dr.", "dr", "mr.", "mr", "ms.", "ms", "major"}]
    terms = [name]
    if len(words) >= 2:
        terms.append(words[-1])
    if p.season == 1:
        n = p.number
        terms += [f"ep {n}", f"ep. {n}", f"episode {n}"]
        if n != str(int(n)):
            terms.append(f"episode {int(n)}")
    else:
        terms.append(f"s{p.season} e{int(p.number)}")
    out = []
    for t in terms:
        if t not in out:
            out.append(t)
    return out


def match_post(title: str | None, episodes: list[dict]) -> int | None:
    """Return the episode id a post belongs to. Full-name terms win; a surname shared by two episodes is ambiguous."""
    if not title:
        return None
    t = title.lower()
    full_hits = [e["id"] for e in episodes if any(len(term.split()) >= 2 and term in t for term in e["match_terms"])]
    if len(full_hits) == 1:
        return full_hits[0]
    if len(full_hits) > 1:
        return None
    surname_hits = [e["id"] for e in episodes if any(len(term.split()) == 1 and not term.startswith("ep") and term in t
                                                     for term in e["match_terms"])]
    return surname_hits[0] if len(surname_hits) == 1 else None
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_episodes.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add collector/tsn_collector/episodes.py collector/tests/test_episodes.py
git commit -m "feat(collector): episode title parsing and clip matching"
git push
```

---

### Task 8: Zernio and YouTube clients

**Files:**
- Create: `collector/tsn_collector/zernio.py`, `collector/tsn_collector/youtube.py`
- Test: `collector/tests/test_clients.py`

- [ ] **Step 1: Write the failing tests**

`collector/tests/test_clients.py`:

```python
import json
from pathlib import Path

import responses

from tsn_collector.zernio import Zernio
from tsn_collector.youtube import parse_flat_catalogue

FX = Path(__file__).parent / "fixtures"
B = "https://zernio.com/api/v1"


@responses.activate
def test_analytics_pages_until_done():
    page1 = {"posts": [{"_id": "a"}], "pagination": {"page": 1, "pages": 2}}
    page2 = {"posts": [{"_id": "b"}], "pagination": {"page": 2, "pages": 2}}
    responses.add(responses.GET, f"{B}/analytics", json=page1, match=[responses.matchers.query_param_matcher(
        {"platform": "youtube", "fromDate": "2025-09-15", "toDate": "2026-09-14", "limit": "100", "page": "1", "source": "all"})])
    responses.add(responses.GET, f"{B}/analytics", json=page2, match=[responses.matchers.query_param_matcher(
        {"platform": "youtube", "fromDate": "2025-09-15", "toDate": "2026-09-14", "limit": "100", "page": "2", "source": "all"})])
    z = Zernio("k")
    out = z.analytics("youtube", "2025-09-15", "2026-09-14")
    assert [p["_id"] for p in out["posts"]] == ["a", "b"]
    assert responses.calls[0].request.headers["Authorization"] == "Bearer k"


@responses.activate
def test_simple_getters():
    responses.add(responses.GET, f"{B}/accounts", json={"accounts": [1]})
    responses.add(responses.GET, f"{B}/accounts/health", json={"accounts": []})
    responses.add(responses.GET, f"{B}/accounts/follower-stats", json={"accounts": []})
    z = Zernio("k")
    assert z.accounts() == [1]
    assert z.health() == {"accounts": []}
    assert z.follower_stats() == {"accounts": []}


@responses.activate
def test_yt_channel_insights_params():
    responses.add(responses.GET, f"{B}/analytics/youtube/channel-insights", json={"metrics": {}}, match=[
        responses.matchers.query_param_matcher({"accountId": "acc", "since": "2026-06-18", "until": "2026-09-11",
                                                "metricType": "time_series",
                                                "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"})])
    assert Zernio("k").yt_channel_insights("acc", "2026-06-18", "2026-09-11") == {"metrics": {}}


@responses.activate
def test_error_raises_with_body():
    responses.add(responses.GET, f"{B}/accounts", json={"error": "nope"}, status=401)
    try:
        Zernio("k").accounts()
    except RuntimeError as e:
        assert "401" in str(e) and "nope" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_parse_flat_catalogue():
    flat = json.loads((FX / "ytdlp_flat.json").read_text(encoding="utf-8"))
    vids = parse_flat_catalogue(flat)
    assert len(vids) == 32
    assert vids[0] == {"id": "AXukyl9hVp0", "title": "TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love", "duration": 2206.0}
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_clients.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tsn_collector.zernio'`

- [ ] **Step 3: Implement the Zernio client**

`collector/tsn_collector/zernio.py`:

```python
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
```

- [ ] **Step 4: Implement the YouTube client**

`collector/tsn_collector/youtube.py`:

```python
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
```

- [ ] **Step 5: Run to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_clients.py -q`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add collector/tsn_collector/zernio.py collector/tsn_collector/youtube.py collector/tests/test_clients.py
git commit -m "feat(collector): zernio and youtube clients"
git push
```

---

### Task 9: The hourly run

**Files:**
- Create: `collector/tsn_collector/run.py`
- Test: `collector/tests/test_run.py`

- [ ] **Step 1: Write the failing test**

`collector/tests/test_run.py`:

```python
"""The run is exercised with fake clients so the orchestration is tested without network."""
import json
from datetime import datetime, timezone
from pathlib import Path

from tsn_collector.run import HourlyRun

FX = Path(__file__).parent / "fixtures"


def fx(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class FakeZernio:
    def accounts(self): return fx("accounts.json")["accounts"]
    def health(self): return fx("health.json")
    def follower_stats(self): return fx("follower_stats.json")
    def analytics(self, platform, a, b): return fx(f"analytics_{platform}.json")
    def yt_channel_insights(self, *a): return {"metrics": {"views": {"values": [{"date": "2026-09-10", "value": 90}]}}}
    def yt_demographics(self, *a, **k): return fx("yt_demographics.json")
    def ig_account_insights(self, *a): return {"metrics": {"reach": {"values": [{"date": "2026-09-13", "value": 300}]}}}
    def ig_follower_history(self, *a): return {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 1533}]}}}
    def ig_demographics(self, *a): return fx("ig_demographics.json")
    def tt_account_insights(self, *a): return {"metrics": {"follower_count": {"values": [{"date": "2026-09-14", "value": 6098}]}}}


class FakeSupa:
    def __init__(self):
        self.writes = {}
        self.rows = {"episodes": [], "post_snapshots": []}
    def upsert(self, table, rows, on_conflict):
        self.writes.setdefault(table, []).extend(rows); return len(rows)
    def insert(self, table, row):
        row = dict(row, id=1); self.writes.setdefault(table, []).append(row); return row
    def update(self, table, match, values):
        self.writes.setdefault(f"update:{table}", []).append((match, values))
    def select(self, table, **params):
        return self.rows.get(table, [])
    def rpc(self, fn, args):
        return {"fetched_at": "x"}
    def upload_public(self, *a, **k):
        self.writes.setdefault("upload", []).append(a[1])


def test_hourly_run_writes_every_table():
    z, s = FakeZernio(), FakeSupa()
    run = HourlyRun(z, s, now=datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc), daily=False, youtube_catalogue=None)
    result = run.execute()
    assert result.status == "ok"
    assert len(s.writes["accounts"]) == 3
    assert len(s.writes["account_snapshots"]) == 3
    assert len(s.writes["posts"]) == 48 + 81 + 77
    assert len(s.writes["post_snapshots"]) == 48 + 81 + 77
    assert len(s.writes["account_health"]) == 3
    assert "metric_daily" not in s.writes  # not a daily run
    assert s.writes["upload"] == ["live.json"]
    assert s.writes["collector_runs"][0]["status"] == "running"
    assert s.writes["update:collector_runs"][0][1]["status"] == "ok"


def test_daily_run_adds_metrics_and_demographics_and_episodes():
    z, s = FakeZernio(), FakeSupa()
    catalogue = [{"id": "AXukyl9hVp0", "title": "TSN TALKS S2 E10: Sunny Khurana, Founder & CEO, Spark.love", "duration": 2206.0},
                 {"id": "PpnI7_--PUg", "title": "TSN Talks Ep. 13 - Dr. Sunil (Part 2)", "duration": 3000.0}]
    run = HourlyRun(z, s, now=datetime(2026, 9, 14, 20, 30, tzinfo=timezone.utc), daily=True, youtube_catalogue=catalogue,
                    video_stats=lambda vid: {"id": vid, "title": "t", "view_count": 5, "like_count": 1, "comment_count": 0,
                                             "upload_date": "20260901", "thumbnail": None})
    result = run.execute()
    assert result.status == "ok"
    metrics = {(r["metric"], r["day"]) for r in s.writes["metric_daily"]}
    assert ("yt_views", "2026-09-10") in metrics and ("ig_reach", "2026-09-13") in metrics
    assert ("ig_followers", "2026-09-14") in metrics and ("tt_followers", "2026-09-14") in metrics
    kinds = {r["kind"] for r in s.writes["demographics"]}
    assert {"yt_age", "yt_country", "ig_city"} <= kinds
    eps = s.writes["episodes"]
    assert {(e["season"], e["number"]) for e in eps} == {(2, "10"), (1, "13")}
    # the catalogue video Zernio did not return becomes a post with a snapshot from yt-dlp
    assert any(p["id"] == "yt:AXukyl9hVp0" for p in s.writes["posts"])


def test_needs_reconnect_marks_run_failed():
    z, s = FakeZernio(), FakeSupa()
    bad = fx("health.json"); bad["accounts"][0]["needsReconnect"] = True
    z.health = lambda: bad
    result = HourlyRun(z, s, now=datetime(2026, 9, 14, 11, 7, tzinfo=timezone.utc), daily=False, youtube_catalogue=None).execute()
    assert result.status == "failed"
    assert "needs reconnect" in result.notes["errors"][0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tsn_collector.run'`

- [ ] **Step 3: Implement the run**

`collector/tsn_collector/run.py`:

```python
"""The hourly collection run. Orchestration only; every mapping lives in transform/episodes."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from . import episodes as E
from . import transform as T
from .youtube import upload_date_to_iso

PLATFORMS = ("youtube", "instagram", "tiktok")


@dataclass
class RunResult:
    status: str = "ok"
    rows: int = 0
    notes: dict[str, Any] = field(default_factory=lambda: {"errors": [], "steps": {}})


class HourlyRun:
    def __init__(self, zernio, supa, now: datetime, daily: bool, youtube_catalogue: list[dict] | None,
                 video_stats: Callable[[str], dict] | None = None):
        self.z, self.s, self.now, self.daily = zernio, supa, now, daily
        self.catalogue = youtube_catalogue or []
        self.video_stats = video_stats
        self.result = RunResult()
        self.accounts: list[dict] = []

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
        n = self.s.upsert("posts", posts, on_conflict="id")
        n += self.s.upsert("post_snapshots", snaps, on_conflict="post_id,taken_at")
        return n

    def step_youtube_catalogue(self) -> int:
        """Episodes from titles, plus lifetime stats for catalogue videos Zernio did not return."""
        acct = self._acct("youtube")
        if not acct or not self.catalogue:
            return 0
        known = {p["id"] for p in self.s.select("posts", select="id", platform="eq.youtube")}
        ep_rows, n = [], 0
        for v in self.catalogue:
            parsed = E.parse_title(v["title"])
            if parsed:
                ep_rows.append({"season": parsed.season, "number": parsed.number, "title": v["title"], "guest": parsed.guest,
                                "role": parsed.role, "youtube_video_id": v["id"], "match_terms": E.match_terms(parsed)})
            key = f"yt:{v['id']}"
            if key in known or not self.video_stats:
                continue
            st = self.video_stats(v["id"])
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
            self._step("daily:youtube", self.step_daily_youtube)
            self._step("daily:instagram", self.step_daily_instagram)
            self._step("daily:tiktok", self.step_daily_tiktok)
        self._step("match_episodes", self.step_match_episodes)
        self._step("publish", self.step_publish)
        self.s.update("collector_runs", {"id": run["id"]}, {"finished_at": datetime.now(self.now.tzinfo).isoformat(),
                                                             "status": self.result.status, "rows_written": self.result.rows,
                                                             "notes": self.result.notes})
        return self.result
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -q`
Expected: `3 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: `27 passed`

- [ ] **Step 6: Commit**

```bash
git add collector/tsn_collector/run.py collector/tests/test_run.py
git commit -m "feat(collector): hourly run orchestration with fake-client tests"
git push
```

---

### Task 10: SQL functions: live_json, rollup_views, thinning

**Files:**
- Create: `db/003_functions.sql`

- [ ] **Step 1: Write the functions**

`db/003_functions.sql`:

```sql
-- Latest snapshot per post
create or replace view v_post_latest as
select distinct on (ps.post_id) ps.*, p.platform, p.published_at, p.title, p.url, p.thumb_url, p.episode_id, p.platform_post_id
from post_snapshots ps join posts p on p.id = ps.post_id
order by ps.post_id, ps.taken_at desc;

-- Latest follower snapshot per account
create or replace view v_account_latest as
select distinct on (s.account_id) s.*, a.platform, a.handle, a.display_name, a.avatar_url
from account_snapshots s join accounts a on a.id = s.account_id
order by s.account_id, s.taken_at desc;

-- Views per period per platform: sum of per-post view deltas inside the window,
-- where a post's delta = last snapshot in period − last snapshot before the period (or its first snapshot's views if new).
create or replace function rollup_views(from_ts timestamptz, to_ts timestamptz, granularity text, platform_filter text default 'all')
returns table (period timestamptz, platform text, views bigint, posts_published integer)
language sql stable as $$
  with periods as (
    select generate_series(date_trunc(granularity, from_ts at time zone 'Asia/Bangkok'),
                           date_trunc(granularity, to_ts at time zone 'Asia/Bangkok'),
                           ('1 ' || granularity)::interval) as p_local
  ),
  bounds as (
    select p_local at time zone 'Asia/Bangkok' as p_start,
           (p_local + ('1 ' || granularity)::interval) at time zone 'Asia/Bangkok' as p_end
    from periods
  ),
  snaps as (
    select ps.post_id, p.platform, ps.taken_at, ps.views from post_snapshots ps join posts p on p.id = ps.post_id
    where platform_filter = 'all' or p.platform = platform_filter
  ),
  per_post as (
    select b.p_start, s.platform, s.post_id,
           (select views from snaps x where x.post_id = s.post_id and x.taken_at < b.p_end order by taken_at desc limit 1)
           - coalesce((select views from snaps x where x.post_id = s.post_id and x.taken_at < b.p_start order by taken_at desc limit 1), 0) as delta
    from bounds b join (select distinct post_id, platform from snaps) s on true
  )
  select pp.p_start as period, pp.platform, greatest(sum(pp.delta), 0)::bigint as views,
         (select count(*) from posts q where q.published_at >= pp.p_start and q.published_at < pp.p_start + ('1 ' || granularity)::interval
            and (platform_filter = 'all' or q.platform = pp.platform))::int as posts_published
  from per_post pp group by pp.p_start, pp.platform order by 1, 2;
$$;

-- The public site's payload
create or replace function live_json() returns jsonb
language sql stable as $$
  with plat as (
    select a.platform,
           max(al.followers) as followers,
           sum(pl.views) as views, count(pl.post_id) as posts,
           max(al.taken_at) as followers_at
    from accounts a
    left join v_account_latest al on al.account_id = a.id
    left join v_post_latest pl on pl.platform = a.platform
    group by a.platform
  ),
  tops as (
    select platform, jsonb_build_object('title', title, 'views', views, 'url', url, 'thumb', thumb_url, 'date', published_at) as top
    from (select *, row_number() over (partition by platform order by views desc) rn from v_post_latest) t where rn = 1
  ),
  months as (
    select to_char(date_trunc('month', published_at at time zone 'Asia/Bangkok'), 'YYYY-MM') as m, platform, sum(views) as views
    from v_post_latest where published_at is not null group by 1, 2
  ),
  eps as (
    select e.id, e.season, e.number, e.guest, e.role, e.youtube_video_id, e.published_at,
           pl.views, pl.likes, pl.comments,
           (select coalesce(sum(c.views), 0) from v_post_latest c where c.episode_id = e.id and c.platform <> 'youtube') as clip_views,
           (select count(*) from v_post_latest c where c.episode_id = e.id and c.platform <> 'youtube') as clips
    from episodes e left join v_post_latest pl on pl.post_id = 'yt:' || e.youtube_video_id
  ),
  demo as (
    select kind, jsonb_agg(jsonb_build_object('dimension', dimension, 'value', value) order by value desc) as items
    from (select distinct on (kind, dimension) * from demographics order by kind, dimension, window_end desc) d
    group by kind
  ),
  yt88 as (
    select coalesce(sum(value) filter (where metric = 'yt_views'), 0) as views,
           coalesce(sum(value) filter (where metric = 'yt_minutes'), 0) as minutes,
           coalesce(sum(value) filter (where metric = 'yt_subs_gained'), 0) as subs_gained,
           coalesce(sum(value) filter (where metric = 'yt_subs_lost'), 0) as subs_lost
    from metric_daily where day >= current_date - 90
  )
  select jsonb_build_object(
    'fetched_at', now(),
    'total_views', (select coalesce(sum(views), 0) from plat),
    'total_followers', (select coalesce(sum(followers), 0) from plat),
    'platforms', (select jsonb_object_agg(platform, jsonb_build_object('followers', followers, 'views', views, 'posts', posts,
                     'top', (select top from tops t where t.platform = plat.platform))) from plat),
    'months', (select jsonb_agg(jsonb_build_object('m', m, 'platform', platform, 'views', views) order by m) from months),
    'episodes', (select jsonb_agg(to_jsonb(eps) order by season desc, number desc) from eps),
    'demographics', (select jsonb_object_agg(kind, items) from demo),
    'yt_90d', (select to_jsonb(yt88) from yt88)
  );
$$;

-- Keep hourly snapshots 90 days, then one per day
create or replace function thin_snapshots() returns integer
language plpgsql as $$
declare n integer;
begin
  with keep as (
    select distinct on (post_id, (taken_at at time zone 'Asia/Bangkok')::date) post_id, taken_at
    from post_snapshots where taken_at < now() - interval '90 days'
    order by post_id, (taken_at at time zone 'Asia/Bangkok')::date, taken_at desc
  ),
  del as (
    delete from post_snapshots ps using (select post_id, taken_at from post_snapshots where taken_at < now() - interval '90 days') old
    where ps.post_id = old.post_id and ps.taken_at = old.taken_at and not exists (select 1 from keep k where k.post_id = ps.post_id and k.taken_at = ps.taken_at)
    returning 1
  )
  select count(*) into n from del;
  return n;
end $$;

grant execute on function rollup_views(timestamptz, timestamptz, text, text) to authenticated;
grant execute on function live_json() to authenticated, service_role;
revoke execute on function live_json() from anon;
```

- [ ] **Step 2: Apply**

Run: `python infra/apply_sql.py db/003_functions.sql`
Expected: `applied db/003_functions.sql`

- [ ] **Step 3: Seed and test the rollup against known numbers**

Run through the applier on a temporary file `db/_test_rollup.sql` (delete after):

```sql
begin;
insert into accounts (id, platform, handle) values ('t-yt', 'youtube', 't') on conflict do nothing;
insert into posts (id, account_id, platform, published_at) values ('yt:test1', 't-yt', 'youtube', '2026-09-01T10:00:00+07:00') on conflict do nothing;
insert into post_snapshots (post_id, taken_at, views) values
  ('yt:test1', '2026-09-01T12:00:00+07:00', 100),
  ('yt:test1', '2026-09-01T23:00:00+07:00', 150),
  ('yt:test1', '2026-09-02T12:00:00+07:00', 400);
select period, platform, views, posts_published from rollup_views('2026-09-01T00:00:00+07:00', '2026-09-02T23:59:59+07:00', 'day', 'youtube');
rollback;
```

Expected rows: `2026-08-31T17:00:00+00:00 | youtube | 150 | 1` and `2026-09-01T17:00:00+00:00 | youtube | 250 | 0` (day one counts the first snapshot's 150 as new, day two counts 400 − 150). Delete the temp file afterwards.

- [ ] **Step 4: Create the public bucket**

```bash
python - <<'EOF'
import re, urllib.request, json
from pathlib import Path
t = Path.home().joinpath('.secrets/secrets.md').read_text(encoding='utf-8')
url = re.search(r"URL `(https://[a-z]+\.supabase\.co)`", t).group(1); svc = re.search(r"service_role key[^`]*`([^`]+)`", t).group(1)
req = urllib.request.Request(f"{url}/storage/v1/bucket", data=json.dumps({"id": "public", "name": "public", "public": True}).encode(), method="POST",
      headers={"apikey": svc, "Authorization": f"Bearer {svc}", "Content-Type": "application/json"})
try: print(json.load(urllib.request.urlopen(req)))
except urllib.error.HTTPError as e: print(e.code, e.read()[:200])
EOF
```

Expected: `{'name': 'public'}` (or 409 if it already exists).

- [ ] **Step 5: Commit**

```bash
git add db/003_functions.sql
git commit -m "feat(db): live_json, rollup_views, snapshot thinning"
git push
```

---

### Task 11: CLI, first real run, backfill

**Files:**
- Create: `collector/tsn_collector/cli.py`, `collector/tsn_collector/backfill.py`, `collector/.env` (local only, gitignored)

- [ ] **Step 1: Write the CLI**

`collector/tsn_collector/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings_from_env
from .run import HourlyRun
from .supa import Supa
from .youtube import fetch_flat_catalogue, fetch_video_stats, parse_flat_catalogue
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
                    youtube_catalogue=catalogue, video_stats=fetch_video_stats if daily else None)
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


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="tsn-collect")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--daily", action="store_true", help="force the daily steps"); c.set_defaults(fn=cmd_collect)
    h = sub.add_parser("health"); h.set_defaults(fn=cmd_health)
    p = sub.add_parser("publish-live-json"); p.add_argument("--out", default=None); p.set_defaults(fn=cmd_publish)
    b = sub.add_parser("backfill-youtube"); b.add_argument("--months", type=int, default=12); b.add_argument("--top", type=int, default=30); b.set_defaults(fn=cmd_backfill)
    args = ap.parse_args(argv)
    sys.exit(args.fn(args))
```

- [ ] **Step 2: Write the backfill**

`collector/tsn_collector/backfill.py`:

```python
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
            d = z.yt_daily_views(acct["id"], vid, start, end)
            rows = [{"account_id": acct["id"], "day": x["date"][:10], "metric": f"ytv_{vid}_views", "value": x.get("views") or 0}
                    for x in d.get("dailyViews") or []]
            n += s.upsert("metric_daily", rows, on_conflict="account_id,day,metric")
    return n
```

- [ ] **Step 3: Local `.env` and first real run (Ney, inline)**

Create `collector/.env` from `.env.example` with the Zernio key and the Supabase URL and service-role key from the secrets store. Then:

```bash
cd collector
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m tsn_collector.cli health
.venv/Scripts/python -m tsn_collector.cli collect --daily
```

Expected: health prints `{"total": 3, "healthy": 3, ...}`. Collect prints `"status": "ok"` with `steps` showing accounts 6, followers 3, posts for the three platforms around 96, 162 and 154, youtube_catalogue a few hundred, daily steps non-zero, publish 1. The daily run takes a few minutes because yt-dlp fetches each catalogue video once.

Verify in the database:

```bash
python - <<'EOF'
from infra.apply_sql import read_secret, run_sql
ref = read_secret(r"Supabase project `tsntalks` ref `([a-z]+)`"); tok = read_secret(r"(sbp_[a-f0-9]{40})")
print(run_sql(ref, tok, "select (select count(*) from posts) posts, (select count(*) from post_snapshots) snaps, (select count(*) from episodes) episodes, (select count(*) from posts where episode_id is not null) matched"))
EOF
```

Expected: posts about 210 to 240, snaps the same, episodes 30 or more (Kickoff and specials do not parse), matched more than 60.

- [ ] **Step 4: Backfill**

Run: `.venv/Scripts/python -m tsn_collector.cli backfill-youtube --months 12 --top 30`
Expected: `backfill rows` in the thousands. Check: `select min(day), max(day), count(*) from metric_daily where metric='yt_views'` returns a range starting around September 2025.

- [ ] **Step 5: Publish and check the public URL**

Run: `.venv/Scripts/python -m tsn_collector.cli publish-live-json --out ../data/live.json`
Then open `https://<ref>.supabase.co/storage/v1/object/public/public/live.json` in a browser: JSON with `total_views` close to 2,255,531 plus the older catalogue videos.

- [ ] **Step 6: Commit**

```bash
git add collector/tsn_collector/cli.py collector/tsn_collector/backfill.py data/live.json
git commit -m "feat(collector): cli, youtube backfill, first published live.json"
git push
```

---

### Task 12: GitHub Actions

**Files:**
- Create: `.github/workflows/collect.yml`

- [ ] **Step 1: Add repository secrets**

In `https://github.com/neramitsingh/tsntalks/settings/secrets/actions` add `ZERNIO_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (values from the secrets store). Do this by hand in the browser; it takes a minute and keeps the tokens out of any script.

- [ ] **Step 2: Write the workflow**

`.github/workflows/collect.yml`:

```yaml
name: collect

on:
  schedule:
    - cron: "7 * * * *"        # hourly at :07 UTC
  workflow_dispatch:
    inputs:
      daily:
        description: "force the daily steps"
        type: boolean
        default: false

permissions:
  contents: write

concurrency:
  group: collect
  cancel-in-progress: false

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    env:
      ZERNIO_API_KEY: ${{ secrets.ZERNIO_API_KEY }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      TZ_NAME: Asia/Bangkok
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e "collector[dev]"
      - run: python -m pytest collector -q
      - name: collect
        run: |
          if [ "${{ github.event.inputs.daily }}" = "true" ]; then
            python -m tsn_collector.cli collect --daily
          else
            python -m tsn_collector.cli collect
          fi
      - name: commit daily live.json
        if: ${{ always() }}
        run: |
          python -m tsn_collector.cli publish-live-json --out data/live.json
          HOUR=$(TZ=Asia/Bangkok date +%H)
          if [ "$HOUR" = "03" ] || [ "${{ github.event.inputs.daily }}" = "true" ]; then
            git config user.name "tsn-collector"
            git config user.email "collector@users.noreply.github.com"
            git add data/live.json
            git diff --cached --quiet || git commit -m "data: live.json $(date -u +%F)"
            git push
          fi
```

- [ ] **Step 3: Run it once by hand**

In the Actions tab, run `collect` with `daily` checked. Expected: green; the job log ends with `published live.json … bytes`; a commit `data: live.json 2026-09-15` appears on `main`.

- [ ] **Step 4: Confirm the hourly cadence**

After two hours: `select started_at, status, rows_written from collector_runs order by id desc limit 3` shows two `ok` rows an hour apart.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/collect.yml
git commit -m "ci: hourly collector with daily live.json commit"
git push
```

---

## Self-review against the spec

- Section 4 data model: every table in Task 3; `allowed_users` and `is_allowed()` in Task 4; views and functions in Task 10. Covered.
- Section 5 collector steps 1 to 8: Task 9 (`step_accounts`, `step_followers`, `step_posts`, `step_youtube_catalogue`, daily steps, `step_match_episodes`, `step_publish`), run bookkeeping in `execute`. Backfill in Task 11. Daily commit of `data/live.json` in Task 12. Covered. The Data API adapter is deferred until a key exists (spec section 11); yt-dlp is the catalogue source in `youtube.py`.
- Section 7 failure handling: `_step` isolates platform failures, `needsReconnect` fails the run, GitHub emails on a red job. Public-page staleness display belongs to Plan 2.
- Section 8 testing: transforms, episodes, clients, run orchestration, Supabase client all under `pytest`; the rollup SQL is checked against seeded numbers in Task 10 step 3; the identical-second-run-writes-zero-rows check is satisfied by primary-key upserts (same `taken_at` never recurs within an hour, and the run test asserts the tables written).
- Types: `Parsed` fields `season:int, number:str, guest:str, role:str` used identically in Tasks 7 and 9; `Supa.upsert(table, rows, on_conflict)` signature identical in Tasks 5, 9, 11; `HourlyRun(zernio, supa, now, daily, youtube_catalogue, video_stats)` identical in Tasks 9 and 11.
- Placeholders: none. Every code step is complete.
