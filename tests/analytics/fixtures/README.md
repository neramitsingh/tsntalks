# Analytics fixtures

Every file here is **hand-built and synthetic**. None of it came out of the live
Supabase project — the worktree that wrote the dashboard has no credentials and
no network path to the database, by design. Nothing real is ever pasted in here:
the guests are Testy McFixture, Placeholder Singh and Sample Kaur, the video ids
say `FIXTUREVID`, and the numbers are round enough that you can add them up in
your head, which is the point.

`tests/analytics/conftest.py` serves these through `page.route`, so the dashboard
under test talks to a stubbed PostgREST and never to a real one.

## The world these describe

Three accounts, one per platform. Three episodes, ten posts.

| Episode | Guest | YouTube video | Clips |
|---|---|---|---|
| S2 E10 | Testy McFixture | `FIXTUREVID01` | one YouTube Short, one Reel, one TikTok |
| S2 E9 | Placeholder Singh | `FIXTUREVID02` | one Reel, one TikTok |
| S1 E22 | Sample Kaur | `FIXTUREVID03` | one Reel, one TikTok |

## The window

The period fixtures cover **seven Bangkok days, 2026-09-09 to 2026-09-15**, at
`day` granularity — 21 rows each, one per day per platform.

`period` is written in **UTC**, as `2026-09-08T17:00:00+00:00`, because that is
what PostgREST actually emits: Supabase's connection timezone is UTC, and
`2026-09-09T00:00+07:00` and `2026-09-08T17:00Z` are the same instant. The
dashboard converts back to Bangkok in `data.js` and nowhere else. A fixture
written in `+07:00` would have quietly let a timezone bug through.

## What reconciles, and what does not

These numbers were chosen so the cross-checks a reviewer would want actually
hold, and `test_fixtures.py` asserts them:

- **Views reconcile.** `rollup_views` summed over the seven days equals
  `post_deltas.views_gained` summed over the same platform: 9,700 on YouTube,
  36,900 on Instagram, 23,300 on TikTok.
- **Episode totals reconcile.** `episode_rollup.total_reach` is the sum of
  `post_deltas.views_end` for the episode's long cut and its clips.

They deliberately do **not** reconcile everywhere, because the real functions do
not either:

- `rollup_engagement` returns likes/comments/shares **gained in the period**;
  `post_deltas` returns the post's **lifetime** figures at the end of the window.
  Different bases, different numbers, on purpose.

## The edge cases baked in

Each of these exists so a renderer that mishandles it fails a test rather than a
sponsor's PDF:

- `rollup_followers` day one has `gained: 0` and `lost: 0` for every platform.
  There is no earlier snapshot, so no change can be attributed — not "they all
  arrived today".
- Instagram loses followers on two of the seven days: `gained` and `lost` are
  both non-zero in the same window.
- `tt:FIXCLIP03` has **negative** `views_gained` (−50). TikTok recounted it.
  `post_deltas` does not clamp, and the Posts tab shows it.
- `ig:FIXCLIP01` and `tt:FIXCLIP01` were first seen inside the window, so
  `views_start` is 0 and `views_gained` is the whole view total.
- `yt:FIXSHORT01` gained nothing in the window — an older clip that stopped
  moving — and it is a **YouTube** clip, so `clip_views_youtube` is non-zero for
  episode 1 and the "clips are the non-YouTube posts" shortcut fails visibly.
- `demographics_compare` → `ig_city` has `prev_value: null` on every row: there
  is no comparable earlier window, and the Audience tab has to say so instead of
  drawing a rise from zero.
- `yt_country` moves the other way from the current data: India's share falls
  while Thailand's rises. That is the shape of the claim the old media kit got
  wrong, so it is the shape the fixtures test against.

## Units, which are not uniform

- `engagement_rate` is a **fraction**: `0.0625` means 6.25%. That is Zernio's
  `engagementRate`, stored as sent.
- `yt_age` and `yt_gender` values are **percentages** of channel views and sum to
  about 100.
- `yt_country`, `ig_age`, `ig_gender`, `ig_city` and `ig_country` values are
  **absolute counts** — views for YouTube, followers for Instagram.

`docs/analytics-data-contract.md` is the long form of all of this.
