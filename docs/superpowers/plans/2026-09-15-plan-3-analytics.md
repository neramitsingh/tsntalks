# TSN Talks Plan 3: Private Analytics

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/analytics` — a private, magic-link dashboard over the Supabase data the collector has been accruing since 2026-09-15, with real time-frame and granularity control, six tabs, and five named export artifacts. Ney and Sunny are the only two people who can sign in.

**Architecture:** Same shape as the public site — plain HTML, CSS and ES modules, no framework, no build step. `site/analytics/` is its own page with its own stylesheet layered on the tokens in `site/css/site.css`. One data module owns every call to Supabase and every derived series; the tabs are pure renderers over what it returns. Auth is Supabase's own magic link; the browser holds the anon key and RLS does the gatekeeping, exactly as `db/002_rls.sql` already sets up.

**Tech Stack:** HTML5, CSS custom properties + grid, vanilla ES2022 modules, `@supabase/supabase-js` v2 (UMD, pinned, from cdnjs), SheetJS `xlsx` (UMD, pinned, from cdnjs) for the spreadsheet exports, browser print-to-PDF for the paper artifacts, Playwright (Python) + pytest for tests.

**Spec:** `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` sections 2, 3.4, 4, 7, 8, 10 (step 3). Product brief: `PRODUCT.md`.

**Who runs what:** this plan is dispatched to **one Claude-lane remote worker** on the desktop (`dispatch-remote-worker.ps1 -Lane claude -Repo tsntalks`), running the tasks in order, one commit per task. Plan 2 was built inline because it was open design work; this one is not — the design system already exists, the data model is fixed, and every screen below is specified down to its columns. Nav reviews by diff and by rerunning the suite, never by exit code.

---

## The two constraints that shape every task

**1. The worker has no secrets and no network access to Supabase.** Worker worktrees get no `.env*` (remote-lane wave 3, deliberate — a headless model with skipped permissions should not hold service-role keys). So *nothing in this plan may be verified against the live database by the worker.* Every screen is built against committed fixtures, and every test stubs the Supabase REST and RPC endpoints through Playwright's `route`, the same way `tests/site/conftest.py` already stubs the Storage copy of `live.json`.

This is a feature, not a workaround: it means the dashboard has a written data contract, and a storage-down or auth-down path that is actually exercised.

**2. Nav applies the SQL, not the worker.** Task 1 writes `db/004_analytics.sql`. It does not run it — the worker cannot reach the project. Nav applies it against `tsntalks` (`xygppcxxfggydlwgoadw`) on review, then runs the live smoke in the verification section at the bottom. Until then the fixtures are the only thing the functions have been checked against, and the plan says so out loud rather than pretending otherwise.

**Corollary for the worker:** if you find yourself wanting to "just check what the real data looks like", stop and write the assumption into `docs/analytics-data-contract.md` instead. A wrong assumption written down is cheap to fix; a wrong assumption buried in a renderer is not.

---

## Register: this is a product, not a brochure

The public pages are brand — Bodoni display, big numbers, air. `/analytics` is the opposite register and the spec is explicit about it: *"Private register: Product. A dashboard. Familiar controls, dense where useful."*

Concretely, and these are not negotiable stylistic opinions, they are the rules the tests check:

- Hanken Grotesk throughout. Bodoni appears **only** in the print artifacts, where the brand is the point. No Bodoni in the dashboard chrome.
- Tabular figures (`font-variant-numeric: tabular-nums`) on every number in every table and every headline figure. Columns of digits must line up.
- Platform colours are fixed and never reassigned: YouTube `#E8621A`, TikTok `#2EA6A0`, Instagram `#7C6BF0`. Plan 2 validated these for dichromat separation on the dark ground; the same test must keep passing.
- **Every chart has a table twin.** A `<details>` below the chart containing the same numbers as a real `<table>`. This is the accessibility contract from the spec, and it doubles as the thing that makes the numbers copyable.
- No dual axes. Ever. If two series have different units they are two charts.
- Thin marks, 2px gaps between surfaces, hairline solid gridlines, selective direct labels, a legend only when there are two or more series.
- Deltas are rendered as position, not deficit: `+12.4%` and `−3.1%` with colour and an arrow, never a progress bar toward a target and never a countdown.

---

## File structure

```
tsntalks/
  db/
    004_analytics.sql            dashboard RPCs — WRITTEN by the worker, APPLIED by Nav   (NEW)
  docs/
    analytics-data-contract.md   the shape of everything the dashboard reads              (NEW)
  site/
    analytics/
      index.html                 the whole dashboard: login gate + shell + six tabs
      artifacts/
        episode-report.html      print-designed, one episode
        guest-card.html          print-designed + canvas PNG render
        monthly-review.html      print-designed, month vs month
        numbers-today.html       the live page's figures frozen at a date
    css/
      analytics.css              product register, layered on site.css tokens              (NEW)
      artifacts.css              print CSS: A4 portrait, page breaks, ink-safe palette      (NEW)
    js/
      analytics/
        supa.js                  client construction, auth, session, sign-out
        data.js                  EVERY query. Returns plain objects per the contract
        controls.js              frame / granularity / platform / compare, URL-synced
        charts.js                the five chart primitives + the table-twin helper
        format.js                re-exports live-data.js formatters, adds delta + period
        tabs/
          overview.js  growth.js  posts.js  episodes.js  audience.js  health.js
        artifacts/
          index.js               the artifact registry: name, recipient, builder
          csv.js                 CSV + XLSX via SheetJS
          png.js                 canvas render for the guest card
  tests/
    analytics/
      conftest.py                serves site/, stubs Supabase REST + RPC + auth
      fixtures/                  committed JSON, one file per endpoint
      test_auth.py  test_controls.py  test_tabs.py  test_artifacts.py  test_contrast.py
```

---

## Ground rules for the worker

- **One commit per task**, message in Conventional Commits with a `Nav-Agent: <worker name>` trailer. No `Co-Authored-By`.
- **Run the full suite before every commit**: `python -m pytest tests/ -q`. It must be green. If a pre-existing test fails for an environmental reason, say so in the commit body — do not edit the test to make it pass.
- **Do not touch** `site/index.html`, `site/live/`, `site/partner/`, `site/js/home.js`, `site/js/live.js`, or the collector. `site/css/site.css` may only be *appended* to, and only with new custom properties — never edit an existing token, several public-page contrast tests are pinned to them.
- **Pin every CDN dependency to an exact version** and load it from cdnjs. No `@latest`, no unpkg.
- **No secrets in the repo.** The Supabase URL and the **anon** key are public by design and belong in `site/js/analytics/supa.js` as literals — the anon key is safe precisely because `db/002_rls.sql` gives anonymous users nothing. The service-role key must never appear anywhere in `site/`.
- If a task turns out to be wrong or impossible as written, **do that task's neighbours and leave a note in the commit body**. Do not silently redesign. Half a plan executed faithfully is worth more than a whole one executed creatively.

---

## Task 1: The SQL the dashboard needs

`rollup_views()` already exists and covers views-over-time. The dashboard needs four more rollups that are unreasonable to do client-side over a year of snapshots.

- [ ] `db/004_analytics.sql`, each function `language sql stable security definer set search_path = public`, and each one `revoke execute ... from anon` then `grant execute ... to authenticated`, so the RLS posture matches the tables.
- [ ] `rollup_followers(from_ts, to_ts, granularity, platform_filter)` → `(period, platform, followers, gained, lost)`. Followers is the last snapshot in the period; gained/lost are the positive and negative parts of the period-over-period change.
- [ ] `rollup_engagement(from_ts, to_ts, granularity, platform_filter)` → `(period, platform, likes, comments, shares, engagement_rate)`. Rate is weighted by views, not a mean of rates — a mean of rates over-weights small posts and is the classic way to make a dashboard lie.
- [ ] `post_deltas(from_ts, to_ts, platform_filter)` → `(post_id, platform, title, url, published_at, views_start, views_end, views_gained, likes, comments, shares, engagement_rate)`. `views_gained` is the difference between the last snapshot at or before `to_ts` and the last at or before `from_ts`; a post first seen inside the window counts its whole view total. This is the Posts tab's whole data source.
- [ ] `episode_rollup()` → one row per episode: `(episode_id, season, number, title, guest, role, published_at, youtube_video_id, yt_views, clip_count, clip_views_youtube, clip_views_instagram, clip_views_tiktok, total_reach)`. `total_reach` is the sum of latest views across the YouTube episode and every matched clip. Name it a sum of views, not "reach" in the marketing sense, in a comment — the artifacts inherit this number and a sponsor will ask.
- [ ] `demographics_compare(kind, window_days)` → the latest window and the one before it side by side, so the Audience tab can show change without two round trips.
- [ ] Header comment in the file: which functions the dashboard calls, that Nav applies this by hand, and the `psql`/SQL-editor one-liner to do it.

**Fixtures:** every function above gets a fixture file under `tests/analytics/fixtures/` with a hand-written, plausible, *clearly synthetic* response — round numbers, obviously-fake guest names. Never paste real Supabase output into a fixture.

**Commit:** `feat(db): analytics rollups for the dashboard`

---

## Task 2: The data contract

Before any UI. This is the document the rest of the plan is written against, and the artefact that survives if the worker runs out of budget halfway.

- [ ] `docs/analytics-data-contract.md`: for each of the six tabs and five artifacts, the exact list of calls it makes (RPC name or PostgREST path), the shape it gets back, and the shape `data.js` hands the renderer.
- [ ] State the timezone rule once, in bold: **every period boundary is Asia/Bangkok**, the RPCs take UTC timestamps, and `data.js` is the only place that converts. A tab that does its own date maths is a bug.
- [ ] State the empty-data rule: every renderer must handle zero rows without throwing, and show a named empty state ("no posts in this window"), not a blank panel.
- [ ] State the freshness rule: the header carries the last collector run, read from `collector_runs`, with the same stale-dot logic the public pages use once it passes two hours.

**Commit:** `docs(analytics): the data contract every tab is written against`

---

## Task 3: Auth, shell and the controls row

- [ ] `site/analytics/index.html`: a login gate and, behind it, the shell — header (title, last-run freshness, signed-in email, sign out), the controls row, the tab strip, and one `<main>` the tabs render into.
- [ ] `supa.js`: create the client with the anon key, `signInWithOtp` for the magic link, `onAuthStateChange` to swap the gate for the shell, `signOut`. On a sign-in attempt for an email not in `allowed_users` the flow still *appears* to work — Supabase will not tell you the address is unknown, and it shouldn't — so the gate's copy must say "if that address has access, the link is on its way", and the post-login state is what actually enforces it: an authenticated user who reads zero rows gets an explicit "this account doesn't have access" panel rather than an empty dashboard.
- [ ] `controls.js`: frame (7d, 30d, 90d, 12m, all, custom from/to), granularity (hour only when frame ≤ 7d, day, week, month, defaulting 7d→day, 30d→day, 90d→week, 12m→month, all→month), platform (all, YouTube, Instagram, TikTok), compare (off, previous period). State is serialised to the URL query string so a view can be linked, and restored on load.
- [ ] Changing a control re-renders the active tab only. Switching tabs does not refetch what the controls have not changed — a small in-memory cache keyed by (call, params) is enough.
- [ ] `analytics.css`: the product register from the section above.

**Tests:** the gate is shown when signed out; the shell when signed in; an allowed user with zero rows gets the no-access panel; control state survives a reload through the URL; granularity options narrow correctly when the frame changes.

**Commit:** `feat(analytics): auth gate, shell and the controls row`

---

## Task 4: The data layer

- [ ] `data.js` implements every call in the contract from Task 2 and nothing else. One exported function per contract entry. No DOM, no formatting, no colour.
- [ ] Bangkok-time period boundaries computed here, once.
- [ ] Compare mode: when on, each function returns `{ current, previous }` with the previous window the same length immediately before.
- [ ] Errors surface as a typed result the renderers can show — `{ ok: false, reason }` — never a thrown exception that blanks the page. A failed call renders that panel's own error state; the rest of the tab still draws.
- [ ] `format.js`: re-export the `live-data.js` formatters so no two pages round a figure differently, and add `delta(a, b)`, `periodLabel(ts, granularity)` and `signed(n)`.

**Tests:** every function against its fixture; the Bangkok boundary maths across a month edge and a DST-free year (Thailand has no DST — assert that assumption in a comment so nobody "fixes" it later); compare windows land exactly adjacent with no gap and no overlap.

**Commit:** `feat(analytics): the data layer and formatters`

---

## Task 5: Charts

- [ ] `charts.js`: five primitives, inline SVG, no chart library — `lineSeries`, `barSeries`, `stackedBars`, `horizontalBars`, `sparkline`. Each takes data plus an accessible name and returns an element.
- [ ] `tableTwin(data, columns)` renders the `<details>` + `<table>` that must accompany every chart, and `chart()` composes the two so a tab physically cannot draw one without the other.
- [ ] Tooltips on hover and on keyboard focus. Every chart is reachable by tab and its values readable without a mouse.
- [ ] Responsive by `viewBox`, not by re-measuring on resize.

**Tests:** a chart and its twin carry identical numbers; a chart with one series has no legend and two do; focus moves through the points; the dichromat simulation from `tests/site/test_contrast.py` extended to the dashboard's series colours.

**Commit:** `feat(analytics): chart primitives with mandatory table twins`

---

## Task 6–11: The six tabs

One commit each, in this order. Each is a pure renderer over `data.js`; if a tab needs a number the contract doesn't have, the contract and `data.js` get amended in that tab's commit and the change is named in the commit body.

- [ ] **Task 6 — Overview.** Headline figures with deltas (views, followers, posts published, engagement rate), views over time by platform, follower growth by platform, top posts in the frame. This is the tab that has to answer "how are we doing" in five seconds; nothing below the fold is allowed to be load-bearing.
- [ ] **Task 7 — Posts.** The table: platform, published, title (linked), views, likes, comments, shares, reach, engagement rate, views gained in the frame. Sortable on every column, filterable by platform and by title substring. Clicking a row expands its own view-growth curve inline. This table is also what the posts-table artifact exports, so it keeps its current sort and filters when exported.
- [ ] **Task 8 — Growth.** Followers per platform as lines; gained and lost per period as diverging bars; YouTube subscribers gained and lost; watch time and average view duration per period where `metric_daily` has them. Where a platform doesn't report a metric, say so in the panel — never draw a zero line for missing data.
- [ ] **Task 9 — Episodes.** One row per episode from `episode_rollup()`: YouTube views, clip count, clip views by platform, total views across all cuts. From a row, the two buttons that produce the episode report and the guest card.
- [ ] **Task 10 — Audience.** YouTube age, gender, country; Instagram age, city, country. Bars with their table twins, change against the previous window. **Every panel names its window in its own subtitle** — this is the exact thing that made the old media kit claim India 54% when the 90-day window was 97% Thailand, and the site must never be able to make that mistake again. A test asserts each audience panel renders a window label.
- [ ] **Task 11 — Health.** Last collector run and its status from `collector_runs`, per-account status from `account_health` (token validity, reconnect needed), row counts per table, freshness per platform. Green/amber/red by age, with the thresholds written on screen rather than implied by colour alone.

**Commits:** `feat(analytics): overview tab` … `feat(analytics): health tab`

---

## Task 12: The artifact framework

- [ ] `artifacts/index.js`: a registry. Each artifact declares `{ id, name, recipient, why, formats, build(params) }`. The recipient and the reason are rendered in the UI next to the button — the spec's whole point is that there is no generic "export this view", and the UI should make that visible rather than just true.
- [ ] `artifacts.css`: A4 portrait, `@page` margins, `break-inside: avoid` on every card, and an ink-safe variant of the palette — the dark ground does not print. Bodoni returns here.
- [ ] `csv.js`: CSV natively; XLSX through SheetJS pinned from cdnjs.
- [ ] Filenames carry artifact, subject and date: `tsn-episode-report-s2e10-2026-09-15.pdf`.
- [ ] Every artifact carries a source note: which platforms, which window, the collector run it was built from.

**Commit:** `feat(analytics): artifact registry, print CSS and spreadsheet writers`

---

## Task 13–17: The five artifacts

In the spec's order — the first two are the ones that get used weekly.

- [ ] **Task 13 — Episode report** (PDF, A4). To the episode's sponsor, after it airs. Still, guest, date; YouTube views lifetime and at 7 and 30 days; every clip with platform and views; total across all cuts; audience where YouTube exposes it; source note.
- [ ] **Task 14 — Posts table** (CSV + XLSX). The Posts tab's current rows, sort and filters.
- [ ] **Task 15 — Monthly review** (PDF + XLSX). To Sunny and Thai Sikh News. Month against previous month by platform: views, followers gained, posts published, top five posts, audience shift. One page of charts, each with its table, and the XLSX carries the underlying tables.
- [ ] **Task 16 — Guest card** (PDF + PNG). To the guest, a week after. One page: "your episode reached N people", top clip, platform split, a share link. The PNG is a canvas render sized for both LINE and Instagram.
- [ ] **Task 17 — Numbers as of today** (PDF). To a sponsor who wants a deck. The live page's figures frozen at a date, in the public layout.

**Tests:** each artifact renders from fixtures without throwing; the print stylesheet applies at `@media print`; the CSV round-trips; the XLSX opens as a valid workbook with the expected sheet names; the guest-card PNG comes out at the declared dimensions.

**Commits:** `feat(analytics): episode report artifact` … `feat(analytics): numbers-as-of-today artifact`

---

## Verification — Nav, on review, with the laptop and desktop both up

The worker cannot do any of this. It is Nav's list, not the worker's.

1. `git fetch` the worker branch, read `git diff HEAD...worker/<name>` task by task. Judge by the diff, never by exit code.
2. `python -m pytest tests/ -q` on the laptop **and** through `run-remote` on the desktop — Windows writes it, Linux runs it, and this repo's suite has to pass on both boxes.
3. Apply `db/004_analytics.sql` to `tsntalks` by hand. Read it first. It is `security definer`; check the `search_path` pin and the `revoke from anon` on every function before running it.
4. Add Sunny to `allowed_users` — his email, and confirm with him which one he wants to sign in with.
5. **The live smoke the worker could not do:** sign in as Ney, walk all six tabs at 7d / 30d / 90d / 12m / all, with compare on and off, and confirm each figure against the same number read straight from the table. Any figure that disagrees is a contract bug, not a rounding one.
6. Produce all five artifacts against a real episode and read them as their recipient would. The episode report goes to a sponsor: if a number on it needs a caveat, the caveat belongs on the page.
7. Click through at 1440 and 390 on the deployed page, as Plan 2 did.
8. Only then: tell Sunny it exists.

---

## What this plan deliberately leaves out

- **Writes of any kind.** The dashboard is read-only. There is no editing of episode metadata from the UI; `data/episodes.json` stays the curated truth and stays hand-edited.
- **A sixth artifact.** The five are decided. A sixth is an edit to a working dashboard, after Sunny has seen the five, and it needs a named recipient before it needs a design.
- **The domain.** Still a DNS change on top of a live site, still not a blocker, still not in this plan.
- **Hand-over.** Spec section 9, after Plan 3 lands.
