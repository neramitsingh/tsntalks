# The analytics data contract

Everything `/analytics` reads, where it reads it from, and the shape it is in by
the time a renderer sees it.

This document exists because the dashboard was built without access to the
database. The worktree it was written in has no `.env`, no anon key and no
network path to Supabase — deliberately, so that a headless agent never holds a
service-role key. So every screen was built against the synthetic fixtures in
`tests/analytics/fixtures/`, and every assumption about what the real data looks
like is written down **here** rather than buried in a renderer. A wrong
assumption in this file is a one-line fix. The same assumption inside
`episodes.js` is a wrong number on a sponsor's PDF.

If you are wiring this dashboard to the real database for the first time, this
file plus `db/004_analytics.sql` is the whole of what you need.

---

## 1. The rules

Five rules. Everything below is an application of them.

### 1.1 Timezone

> **Every period boundary is Asia/Bangkok.**

The RPCs take **UTC** `timestamptz` arguments and return **UTC** `timestamptz`
period starts, because that is what PostgREST speaks — Supabase's connection
timezone is UTC and it serialises `timestamptz` accordingly. The *truncation*
happens in Bangkok local time inside the SQL: `date_trunc(g, ts at time zone
'Asia/Bangkok')`, converted back to an instant on the way out. So the `period`
`2026-09-08T17:00:00+00:00` is the Bangkok day that began `2026-09-09 00:00`.

`site/js/analytics/data.js` is **the only place in the dashboard that converts
between UTC and Bangkok.** A tab that does its own date maths is a bug, not a
style preference — it is how two panels end up disagreeing about which day a
number belongs to. Tabs receive `Date` objects and a `periodLabel()` from
`format.js` and never construct a boundary themselves.

Thailand has observed **no daylight saving since 1952** and has no plans to. The
interval arithmetic in `db/004_analytics.sql` and the window maths in `data.js`
both rely on `+07:00` being constant. A test asserts it across a year so that
nobody "fixes" the missing DST handling later.

### 1.2 Empty data

> **Every renderer must handle zero rows without throwing, and show a named
> empty state.**

Not a blank panel, not a chart with no marks, not `NaN`. A sentence that says
which thing is missing: *"No posts published in this window."* *"Instagram does
not report watch time."* *"No comparable earlier window — the collector has been
running since 14 September 2026."*

Zero rows is the **normal** case in several places and always will be: the
collector started snapshotting on 2026-09-14, so any frame reaching further back
than that has real gaps, and `hour` granularity over a quiet night is empty by
construction.

There is a difference the panels must keep: **zero** and **not reported** are not
the same. TikTok does not expose watch time; that panel says so. A day on which
nobody watched is a zero. Never draw a zero line for a metric a platform does
not report — that is a fabricated number with a chart around it.

### 1.3 Freshness

The header carries the last collector run, read from `collector_runs`, with a
dot: solid when fresh, hollow and muted when stale.

**Stale after two hours.** The public pages use three (`STALE_AFTER_MS` in
`live-data.js`) because a visitor reading a media kit does not care about one
missed hour. The dashboard uses two because the collector runs hourly on
`0 * * * *`, so two hours without a finished run means a run was actually missed
and the Health tab has something to say. The difference is deliberate; the
constant lives in `data.js` next to this sentence.

A run with `status <> 'ok'` is shown as failed regardless of age.

### 1.4 Errors

Every function in `data.js` returns a **typed result**, never throws:

```js
{ ok: true,  current: <payload>, previous: <payload>|null, meta: {...} }
{ ok: false, reason: 'human-readable sentence' }
```

A failed call renders that panel's own error state. The rest of the tab still
draws. There is no path where one dead endpoint blanks the page, and no
`unhandledrejection` that leaves the shell showing a spinner forever.

`reason` is a sentence, not an exception message: *"Could not reach the
database."*, *"This account doesn't have access."*, *"Signed out."*

### 1.5 Units

The platforms do not agree with each other and the database stores what it was
given. Nothing normalises on the way in, so the contract has to say which is
which:

| Field | Unit |
|---|---|
| `post_snapshots.engagement_rate`, `rollup_engagement.engagement_rate`, `post_deltas.engagement_rate` | **Fraction.** `0.0625` is 6.25%. Zernio's `engagementRate`, stored as sent. `format.js` multiplies by 100 in exactly one place. |
| `demographics` where `kind` is `yt_age` or `yt_gender` | **Percentage** of channel views. The rows sum to ~100. |
| `demographics` where `kind` is `yt_country` | **Absolute view count.** |
| `demographics` where `kind` is `ig_age`, `ig_gender`, `ig_city`, `ig_country` | **Absolute follower count.** |
| `metric_daily.value` where `metric` is `yt_minutes` | Minutes. |
| `metric_daily.value` where `metric` is `yt_avg_duration` | **Seconds.** |
| every `views`, `followers`, `likes`, `comments`, `shares`, `reach` | Counts. |

`data.js` converts demographics to a **share of the rows it received** and hands
the renderer both `value` and `share`, so the Audience tab never has to know
which kinds are already percentages.

---

## 2. Transport

The browser holds the Supabase **URL** and **anon key** as literals in
`site/js/analytics/supa.js`. Both are public by design: `db/002_rls.sql` gives
`anon` nothing on any table, and `db/004_analytics.sql` revokes execute on every
function from `public` and `anon`. The **service-role key must never appear
anywhere under `site/`**; a test asserts that.

> **Not yet filled in.** The worktree that wrote this had no access to the anon
> key. `SUPABASE_ANON_KEY` in `supa.js` is an empty string with a `TODO(nav)`
> beside it. It is on Nav's machine in `~/.secrets/secrets.md`, under the TSN
> Talks section, as `anon key`. Until it is pasted in, the login gate shows a
> named "not configured" panel instead of a broken form.

Calls go through `@supabase/supabase-js` v2 (UMD, pinned, cdnjs). The underlying
HTTP is plain PostgREST, which is what `tests/analytics/conftest.py` stubs:

| supabase-js | HTTP |
|---|---|
| `sb.rpc('rollup_views', args)` | `POST {URL}/rest/v1/rpc/rollup_views` — args as a JSON object of named parameters |
| `sb.from('collector_runs').select(...)` | `GET {URL}/rest/v1/collector_runs?select=...` |
| `sb.from(t).select('*', {count:'exact', head:true})` | `HEAD {URL}/rest/v1/{t}?select=*` with `Prefer: count=exact`, answer in the `Content-Range` header |
| `sb.auth.signInWithOtp({email})` | `POST {URL}/auth/v1/otp` |
| `sb.auth.signOut()` | `POST {URL}/auth/v1/logout` |

Every request carries `apikey: <anon>` and `Authorization: Bearer <access_token>`
once signed in. RLS and the `is_allowed()` guard inside each function do the rest.

### Access, and what "no access" looks like

An address that is not in `allowed_users` **still receives a magic link and still
signs in**. Supabase will not tell an unauthenticated caller whether an address
is known, and it should not — that would make the login form an email-enumeration
oracle. So the gate's copy is *"if that address has access, the link is on its
way"*, and enforcement happens after login: the user is authenticated, every
query returns zero rows, and the dashboard shows an explicit **"this account
doesn't have access"** panel rather than an empty dashboard.

`data.js` distinguishes the two by probing `allowed_users` once after sign-in:

```
GET /rest/v1/allowed_users?select=email&limit=1
  → 1 row   : allowed
  → 0 rows  : authenticated, not allowed  → the no-access panel
  → error   : transport problem           → the error panel
```

---

## 3. What the database returns

### 3.1 `rollup_views(from_ts, to_ts, granularity, platform_filter)`

From `db/003_functions.sql`. One row per period per platform.

```json
[{ "period": "2026-09-08T17:00:00+00:00", "platform": "instagram",
   "views": 4000, "posts_published": 1 }]
```

`views` is a **flow**: the sum of per-post view deltas inside the period, clamped
at zero at the platform total. `posts_published` counts posts whose
`published_at` falls inside the period.

Arguments: `granularity` is one of `hour`, `day`, `week`, `month`;
`platform_filter` is one of `all`, `youtube`, `instagram`, `tiktok`. Anything
else raises a named error (`22023`) rather than failing obscurely.

### 3.2 `rollup_followers(from_ts, to_ts, granularity, platform_filter)`

```json
[{ "period": "2026-09-08T17:00:00+00:00", "platform": "youtube",
   "followers": 4000, "gained": 0, "lost": 0 }]
```

`followers` is a **stock**: the last snapshot at or before the period's end,
summed across the platform's accounts, **carried forward** — a period with no
snapshot repeats the previous value rather than dropping to zero.

`gained` and `lost` are the positive and negative halves of the change, split
**per account and then summed**, so one account growing while another shrinks
shows as both rather than cancelling.

**An account with no snapshot before the period start contributes 0 to both.**
The first period of any `all` frame therefore reads `gained: 0, lost: 0`. We do
not know those followers arrived then; we know only that it is the first time we
looked. Do not present that as a flat start — it is an absence.

### 3.3 `rollup_engagement(from_ts, to_ts, granularity, platform_filter)`

```json
[{ "period": "2026-09-08T17:00:00+00:00", "platform": "youtube",
   "likes": 60, "comments": 10, "shares": 5, "engagement_rate": 0.0625 }]
```

`likes`/`comments`/`shares` are **gains inside the period**, clamped at zero at
the platform total (platforms revise counters down when a comment is deleted).

`engagement_rate` is `(likes + comments + shares) / views` over the same period
and posts — **one ratio of two sums, not the mean of per-post rates.** Those are
different numbers: a mean of rates gives a post with 40 views the same weight as
one with 400,000, which is the standard way a dashboard reports a rate nobody can
find in the data. It is identical to a view-weighted mean of the per-post rates,
which is how the plan phrased it.

`engagement_rate` is **null** when the period had no views, so the chart breaks
the line instead of drawing a floor at zero.

### 3.4 `post_deltas(from_ts, to_ts, platform_filter)`

One row per post that existed at `to_ts`. The Posts tab's whole data source, and
through it the posts-table artifact.

```json
[{ "post_id": "ig:FIXCLIP01", "platform": "instagram",
   "title": "Testy McFixture on starting over at forty — clip 1",
   "url": "https://www.instagram.com/reel/FIXCLIP01/",
   "published_at": "2026-09-10T04:00:00+00:00",
   "views_start": 0, "views_end": 18000, "views_gained": 18000,
   "likes": 1200, "comments": 90, "shares": 300, "engagement_rate": 0.088333 }]
```

- `views_end` / `views_start`: the last snapshot **at or before** `to_ts` /
  `from_ts`. Note `<=` here against the `<` the period rollups use: those bound a
  half-open period, these read a counter at an instant.
- `views_gained = views_end - views_start`, **not clamped**. A post first seen
  inside the window has `views_start: 0` and counts its whole total, which is why
  `views_gained` can exceed an older post's lifetime figure. A **negative**
  `views_gained` means the platform revised the count down; the tab shows it
  rather than rounding it away.
- `likes`/`comments`/`shares`/`engagement_rate` are **lifetime** values read from
  the `views_end` snapshot, not deltas. The column headers say so.
- Posts with no snapshot at or before `to_ts` are omitted entirely.

**Two columns are added to this function in later tasks** and are already
described here because they are part of the contract the tabs are written
against:

| Column | Added in | Why |
|---|---|---|
| `reach` bigint | Task 7 | §3.4 of the spec lists **reach** as a Posts-tab column. Lifetime `post_snapshots.reach` from the `views_end` snapshot. Instagram reports it; YouTube and TikTok do not, so it is `null` there and the cell reads "not reported", never 0. |
| `episode_id` integer | Task 9 | The episode report needs the **list** of an episode's clips, not just the totals `episode_rollup` gives. Reading `v_post_latest` over PostgREST would work but see §7.2 before you rely on it. |

### 3.5 `episode_rollup()`

No arguments — an episode's totals are lifetime, not windowed.

```json
[{ "episode_id": 1, "season": 2, "number": "10",
   "title": "TSN Talks S2 E10: Testy McFixture, Founder & CEO, Example Co",
   "guest": "Testy McFixture", "role": "Founder & CEO, Example Co",
   "published_at": "2026-08-20T05:00:00+00:00", "youtube_video_id": "FIXTUREVID01",
   "yt_views": 12000, "clip_count": 3,
   "clip_views_youtube": 3000, "clip_views_instagram": 18000,
   "clip_views_tiktok": 14000, "total_reach": 47000 }]
```

> **`total_reach` is a sum of view counts, not people.** One person who watches
> the episode on YouTube and then sees two clips on Instagram is three in this
> number. It is called `total_reach` because that is what the spec's table and
> the episode-report artifact call the column — and because a sponsor will ask,
> the artifact carries that sentence on the page, not just in this file.

The long cut is the post `'yt:' || youtube_video_id`. It also matches its own
episode's title, so it has `episode_id` set; it is excluded from the clip figures
**by id, not by platform**, because YouTube Shorts clips are youtube posts too
and do belong in `clip_views_youtube`.

An episode whose long cut has never been snapshotted still returns a row with
`yt_views: 0`.

### 3.6 `demographics_compare(kind, window_days)`

```json
[{ "dimension": "TH", "value": 45000, "prev_value": 30000, "delta": 15000,
   "window_start": "2026-06-18", "window_end": "2026-09-15",
   "prev_window_start": "2026-03-20", "prev_window_end": "2026-06-17" }]
```

`kind` is one of `yt_age`, `yt_gender`, `yt_country`, `ig_age`, `ig_gender`,
`ig_city`, `ig_country`.

> **`window_days` is how far back the comparison sits, not a filter on window
> length.** The collector writes YouTube's 90-day rolling demographics *every
> day*, so consecutive rows overlap by 89 days and comparing them shows nothing
> but noise. With `window_days: 90` the comparison window is the most recent one
> ending at least 90 days before the current one ends — the two do not overlap,
> and a shift between them is a real shift.

The dashboard calls it with **90** for the `yt_*` kinds (90-day rolling windows)
and **30** for the `ig_*` kinds (30-day). If there is no window that old,
`prev_value`, `delta`, `prev_window_start` and `prev_window_end` are all `null`
and the panel says *"no comparable earlier window"*.

Values are summed across accounts. There is exactly one account per platform
today, so that sum is a pass-through. **If a second YouTube account is ever
connected, the percentage kinds need weighting before they are summed** —
summing two percentages is meaningless.

### 3.7 Tables read straight through PostgREST

RLS does the work; no function wrapper.

| Path | Used by | Shape |
|---|---|---|
| `accounts?select=id,platform,handle,display_name,active&order=platform` | Health, Growth | one row per connected account |
| `collector_runs?select=id,started_at,finished_at,status,rows_written,notes&order=started_at.desc&limit=N` | header, Health | `status` is `ok`, `partial` or `failed`; `notes` is jsonb naming the steps that failed |
| `account_health?select=account_id,checked_at,status,can_fetch_analytics,needs_reconnect,token_expires_at&order=checked_at.desc&limit=60` | Health | latest-per-account is picked client-side; the table is append-only |
| `metric_daily?select=account_id,day,metric,value&day=gte.D&day=lte.D&metric=in.(...)` | Growth | `day` is a **date**, already Bangkok-dated by the collector; see §7.1 |
| `episodes?select=id,season,number,title,guest,role,youtube_video_id,published_at&order=season.desc` | Episodes fallback | only if `episode_rollup()` fails |
| `allowed_users?select=email&limit=1` | the access probe in §2 | 1 row = allowed, 0 rows = not |
| `HEAD {table}?select=*` with `Prefer: count=exact` | Health | row counts, read from `Content-Range` |

---

## 4. What `data.js` hands the renderer

One exported function per contract entry. No DOM, no formatting, no colour.
Every one is `async` and every one returns the envelope from §1.4.

Shared parameter object, produced by `controls.js` and resolved by
`resolveWindow()`:

```js
{ from: Date,            // inclusive, a Bangkok period boundary
  to: Date,              // exclusive
  granularity: 'hour'|'day'|'week'|'month',
  platform: 'all'|'youtube'|'instagram'|'tiktok',
  compare: boolean }
```

When `compare` is true, `previous` carries the same payload for the window of
**identical length immediately before** `from` — `previous.to === from`, exactly,
with no gap and no overlap. When `compare` is false, `previous` is `null`.

| `data.js` export | Calls | `current` payload |
|---|---|---|
| `views(p)` | `rollup_views` | `{ series: [{ period: Date, platform, views, postsPublished }], byPlatform: { youtube: n, ... }, total: n, postsPublished: n }` |
| `followers(p)` | `rollup_followers` | `{ series: [{ period: Date, platform, followers, gained, lost }], latest: { youtube: n, ... }, total: n, gained: n, lost: n }` |
| `engagement(p)` | `rollup_engagement` | `{ series: [{ period: Date, platform, likes, comments, shares, rate }], likes: n, comments: n, shares: n, rate: n\|null }` |
| `posts(p)` | `post_deltas` | `{ rows: [{ postId, platform, title, url, publishedAt: Date, viewsStart, viewsEnd, viewsGained, likes, comments, shares, reach, rate, episodeId }] }` |
| `postHistory(postId, p)` | `rollup_views`-style per-post read | `{ series: [{ period: Date, views }] }` — the inline growth curve on a Posts row |
| `episodes()` | `episode_rollup` | `{ rows: [{ episodeId, season, number, title, guest, role, publishedAt: Date, youtubeVideoId, ytViews, clipCount, clipViews: { youtube, instagram, tiktok }, totalReach }] }` |
| `episodeClips(episodeId, p)` | `post_deltas` filtered on `episodeId` | `{ rows: [...same as posts()] }` |
| `audience(kind, windowDays)` | `demographics_compare` | `{ rows: [{ dimension, label, value, share, prevValue, prevShare, delta, shareDelta }], window: { start: Date, end: Date }, prevWindow: { start, end }\|null }` |
| `dailyMetrics(p, metrics)` | `metric_daily` | `{ series: [{ day: Date, metric, value, accountId, platform }], byMetric: { yt_minutes: [...], ... }, missing: ['tt_watch_time'] }` |
| `accounts()` | `accounts` | `{ rows: [{ id, platform, handle, displayName, active }] }` |
| `lastRun()` | `collector_runs` limit 1 | `{ run: {...}\|null, ageMs, stale, failed }` |
| `runs(limit)` | `collector_runs` | `{ rows: [...] }` |
| `accountHealth()` | `account_health` | `{ rows: [{ accountId, platform, checkedAt: Date, status, canFetchAnalytics, needsReconnect, tokenExpiresAt: Date\|null, ageMs }] }` |
| `rowCounts()` | `HEAD` per table | `{ counts: { posts: n, post_snapshots: n, ... } }` |
| `headline(p)` | derived from `views`, `followers`, `engagement` | `{ views, followers, postsPublished, rate }` — the Overview's four figures |
| `access()` | `allowed_users` | `{ allowed: boolean }` |

Notes that are easy to get wrong:

- **`period` and `publishedAt` are `Date` objects, not strings.** The conversion
  from PostgREST's UTC string happens once, here.
- `share` in `audience()` is the row's value over the sum of the returned rows,
  computed *after* the rows come back, so it is right for percentage kinds
  (already ~100) and count kinds alike. `shareDelta` is `share - prevShare` in
  **percentage points**, which is the honest way to state a demographic shift; a
  relative change in a percentage is nearly always misread.
- `missing` in `dailyMetrics()` names the metrics a platform does not report, so
  the Growth tab can say so instead of drawing zeros (§1.2).
- `rate` is `null`, never `0`, when there were no views.
- `label` in `audience()` is the human name: country codes through
  `COUNTRY` from `live-data.js`, age bands through `ageBand()`, so the dashboard
  and the public pages never spell a country two ways.

### Caching

A small in-memory cache keyed by `(call, JSON.stringify(params))`, cleared on
sign-out. Switching tabs does not refetch what the controls have not changed;
changing a control invalidates only the entries whose params changed. There is no
persistence — a reload refetches, which is what you want from a dashboard.

### `format.js`

Re-exports `full`, `compact`, `pct`, `ageBand`, `bkk`, `bkkStamp`, `COUNTRY`,
`PLATFORMS`, `STACK`, `PLATFORM_NAME`, `PLATFORM_COLOR` from
`site/js/live-data.js` — **unchanged**, so no two pages round the same figure
differently — and adds:

| | |
|---|---|
| `delta(a, b)` | `{ abs, pct, dir: 'up'\|'down'\|'flat' }`. `pct` is `null` when `b` is 0 or null: a rise from nothing has no percentage, and `Infinity%` on a sponsor's PDF is worse than a dash. |
| `signed(n)` | `+12,400` / `−3,100` / `0`, with a real minus sign (U+2212), not a hyphen |
| `periodLabel(date, granularity)` | `14:00` / `9 Sep` / `w/c 7 Sep` / `Sep 2026`, always Bangkok |
| `rangeLabel(from, to)` | `9–15 Sep 2026` — the string every panel subtitle uses to name its window |
| `rate(n)` | a fraction to `6.3%`; the **only** place the ×100 happens |
| `duration(seconds)` | `4m 12s`, for `yt_avg_duration` |

---

## 5. What each tab calls

Every tab is a pure renderer over the table in §4. None of them fetch.

| Tab | Calls | Notes |
|---|---|---|
| **Overview** | `headline(p)`, `views(p)`, `followers(p)`, `posts(p)` | Four headline figures with deltas; views over time by platform; follower growth by platform; top posts in the frame (`posts()` sorted by `viewsGained`, top 10). Nothing below the fold is load-bearing. |
| **Growth** | `followers(p)`, `dailyMetrics(p, ['yt_subs_gained','yt_subs_lost','yt_minutes','yt_avg_duration','ig_follows','ig_unfollows','tt_followers_gained','tt_followers_lost'])` | Followers per platform as lines; gained/lost as diverging bars; YouTube subscribers gained/lost; watch time and average view duration. Metrics no platform reports are named in a panel, never drawn as zero. |
| **Posts** | `posts(p)`, `postHistory(postId, p)` on row expand | Sortable on every column, filterable by platform and title substring. The current sort and filters are what the posts-table artifact exports. |
| **Episodes** | `episodes()`, `episodeClips(id, p)` on expand | Lifetime figures — the controls' time frame does **not** apply to the episode totals, and the panel says so. Per-row buttons produce the episode report and the guest card. |
| **Audience** | `audience(kind, 90)` for `yt_age`, `yt_gender`, `yt_country`; `audience(kind, 30)` for `ig_age`, `ig_city`, `ig_country` | **Every panel names its own window in its subtitle**, from `meta.window`. This is not decoration: it is the exact thing that let the old media kit claim India 54% when the 90-day window was 97% Thailand. A test asserts each panel renders a window label. |
| **Health** | `lastRun()`, `runs(20)`, `accountHealth()`, `rowCounts()`, `accounts()` | Green/amber/red by age with the **thresholds written on screen** — "green under 2h, amber under 6h, red beyond" — rather than implied by colour alone. |

---

## 6. What each artifact calls

No generic "export this view". Five artifacts, each with a named recipient, each
declaring `{ id, name, recipient, why, formats, build(params) }` in
`site/js/analytics/artifacts/index.js`. The recipient and the reason are rendered
next to the button.

| Artifact | Recipient | Calls | Formats |
|---|---|---|---|
| **Episode report** | the episode's sponsor, after it airs | `episodes()` for the row; `episodeClips(id)` for every clip; `postHistory('yt:'+videoId)` for the 7- and 30-day figures; `audience('yt_age', 90)` and `audience('yt_country', 90)` | PDF (A4 portrait, print-to-PDF) |
| **Posts table** | whoever wants a spreadsheet | `posts(p)` — the tab's **current** rows, sort and filters, not a fresh query | CSV, XLSX |
| **Monthly review** | Sunny and Thai Sikh News | `views`, `followers`, `engagement`, `posts` for the month with `compare: true`; `audience(kind)` for the shift | PDF, XLSX (the underlying tables, one sheet each) |
| **Guest card** | the guest, a week after their episode | `episodes()` for the row; `episodeClips(id)` for the top clip and the platform split | PDF, PNG (canvas) |
| **Numbers as of today** | a sponsor who asks for a deck | `views`, `followers`, `posts` and `audience` at `to = the chosen date`, laid out as the public `/live` page | PDF |

Every artifact carries a **source note**: which platforms, which window, and the
`collector_runs` row it was built from. Filenames carry artifact, subject and
date: `tsn-episode-report-s2e10-2026-09-15.pdf`.

"Numbers as of today" is built from the windowed functions above rather than from
`live_json()`, because `live_json()` is always *now* and the artifact's whole
purpose is a date other than now.

---

## 7. Assumptions, and the things to check first

Written down because none of them could be verified without the database. Each
one is cheap to confirm and would be expensive to discover from a wrong PDF.

### 7.1 `metric_daily.day` is already a Bangkok date

The collector writes `v["date"][:10]` straight from the platform APIs.
YouTube Analytics reports in the channel's own timezone; Instagram and TikTok
report in theirs. The dashboard treats `day` as a **Bangkok calendar date and
does not convert it**, because converting a bare date through a timezone is how
you lose a day. If a platform turns out to report in UTC, its daily series is
offset by seven hours and the fix belongs in the collector, not here.

**Check:** compare one day's `yt_views` in `metric_daily` against the same day in
YouTube Studio.

### 7.2 `v_post_latest` may be readable by `anon`

`db/003_functions.sql` creates `v_post_latest` and `v_account_latest` without
`security_invoker`, so they run with their **owner's** privileges and read past
RLS. Supabase's default privileges grant `anon` and `authenticated` SELECT on new
objects in `public`. If both of those hold, those two views are an anonymous read
of every post and every follower count.

The dashboard **does not use them** — everything goes through the
`security definer` functions in `004`, which carry an `is_allowed()` guard. This
note is here because it is worth five minutes before launch:

```sql
select has_table_privilege('anon', 'v_post_latest', 'select');
-- if true:  revoke select on v_post_latest, v_account_latest from anon, public;
```

### 7.3 `posts.title` carries the platform caption, not a clean title

For Instagram and TikTok, `title` is the first 500 characters of the caption —
emoji, hashtags, line breaks and all. The Posts tab and every export clip it on a
word boundary the way `live.js` does, never mid-word, and the full string stays
in the `title` attribute and in the CSV.

### 7.4 One account per platform

`accounts` has three rows today. Every "per platform" figure in this contract
sums across a platform's accounts, so a second account is safe everywhere
**except** the percentage demographic kinds — see §3.6.

### 7.5 `collector_runs.status` values

Assumed to be `ok`, `partial`, `failed`, with `running` while in flight (the
schema defaults to `'running'`). The Health tab renders an unknown status as
amber with the literal string shown, so a fourth value surfaces rather than
silently reading as green.

### 7.6 Frames

| Frame | `from` |
|---|---|
| `7d`, `30d`, `90d` | `to` minus that many Bangkok days |
| `12m` | `to` minus 12 Bangkok months |
| `all` | **the earliest `post_snapshots.taken_at`**, fetched once per session and cached |
| `custom` | the two dates in the URL, snapped to Bangkok period boundaries |

`all` means *since we started measuring*, not *since the show started*. The
snapshot-delta method cannot produce views for a period before the first
snapshot, so an earlier bound would draw a long flat run of zeros and invite
exactly the wrong reading. The Overview says which date `all` resolved to.

Fallback if that query fails: `2026-09-14T00:00:00+07:00`, the date the spec
gives for the first Zernio snapshot.

### 7.7 Snapshot thinning

`thin_snapshots()` keeps hourly resolution for 90 days, then one snapshot per
Bangkok day. So `hour` granularity is only meaningful inside the last 90 days,
which is why `controls.js` offers it only for frames of 7 days or less.
