-- ============================================================================
-- 004_analytics.sql — the rollups /analytics calls.
--
-- APPLIED BY HAND, BY NAV, ON REVIEW. Nothing in this file has run against
-- the live project. The worker that wrote it has no network path to Supabase
-- and no credentials; every function below has only ever been checked against
-- the synthetic fixtures in tests/analytics/fixtures/. Read it before you run
-- it — it is `security definer`, which means it reads past row-level security.
--
-- To apply:
--
--   psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f db/004_analytics.sql
--
-- or paste the whole file into the Supabase SQL editor for project `tsntalks`
-- (xygppcxxfggydlwgoadw) and run it once. It is idempotent: every object is
-- `create or replace`, and the grants are re-stated each time.
--
-- ---------------------------------------------------------------------------
-- What the dashboard calls
-- ---------------------------------------------------------------------------
--
--   from 003_functions.sql (already applied)
--     rollup_views(from_ts, to_ts, granularity, platform_filter)
--
--   from this file
--     rollup_followers(from_ts, to_ts, granularity, platform_filter)
--     rollup_engagement(from_ts, to_ts, granularity, platform_filter)
--     post_deltas(from_ts, to_ts, platform_filter)
--     episode_rollup()
--     demographics_compare(kind, window_days)
--
--   and, straight through PostgREST with RLS doing the work
--     accounts, collector_runs, account_health, metric_daily, episodes
--
-- docs/analytics-data-contract.md is the long form of all of that, including
-- the JSON each one comes back as.
--
-- ---------------------------------------------------------------------------
-- Two things to check before you run this, because they are the whole security
-- posture of the dashboard
-- ---------------------------------------------------------------------------
--
-- 1. `security definer` + the default PUBLIC execute grant is a data leak.
--    Postgres grants EXECUTE on a new function to PUBLIC automatically, and in
--    Supabase `anon` inherits PUBLIC. A `security definer` function reads past
--    RLS, so a function that is merely `grant execute ... to authenticated`
--    is still callable by an anonymous browser with the anon key — and it
--    would answer. Every function below is therefore
--
--        revoke execute ... from public, anon;
--        grant  execute ... to authenticated;
--
--    The `from public` half is not decoration. Do not drop it.
--
--    The same applies to 003: `rollup_views` was never revoked from PUBLIC and
--    `live_json` was revoked from `anon` but not from PUBLIC. Both are
--    `security invoker`, so RLS still protects them and neither is currently
--    leaking — but the grants are re-stated at the bottom of this file so the
--    two files agree about who may call what.
--
-- 2. `grant ... to authenticated` is not the same as "Ney and Sunny".
--    `authenticated` is every signed-in Supabase user, and RLS on the tables
--    narrows that to `allowed_users` via `is_allowed()`. A `security definer`
--    function skips that check unless it makes it itself, so each function
--    below carries `and is_allowed()` on its outermost query. A signed-in user
--    who is not in `allowed_users` gets zero rows, exactly as the tables give
--    them zero rows. The dashboard reads that empty result as "this account
--    doesn't have access" rather than as "no data".
--
--    This guard is not in the plan's wording for Task 1, which asked only for
--    the revoke/grant pair. It is here because the revoke/grant pair alone does
--    not produce the posture the plan asked for.
--
-- ---------------------------------------------------------------------------
-- Conventions shared with 003
-- ---------------------------------------------------------------------------
--
--   * Period boundaries are Asia/Bangkok. Arguments are timestamptz (UTC over
--     the wire); the truncation happens in local time and the returned `period`
--     is the timestamptz of the local period start. Thailand has no daylight
--     saving and never has — the interval arithmetic below relies on that.
--   * A period runs [p_start, p_end): a snapshot taken exactly on a boundary
--     belongs to the period that is starting, not the one that is ending.
--   * Stock figures (followers) carry forward: "the value in this period" means
--     the last snapshot at or before the period's end, even if that snapshot
--     was taken before the period began.
--   * Flow figures (views, likes, ...) are differences of the cumulative
--     counters the platforms report, not independent counts.
-- ============================================================================


-- --- argument validation ----------------------------------------------------
-- `granularity` and `platform_filter` reach these functions from the browser.
-- Neither is ever concatenated into executable SQL — `date_trunc(g, ts)` and
-- `('1 ' || g)::interval` both take their argument as a value, so there is no
-- injection to defend against. What there is, is a confusing error message at
-- the bottom of a CTE stack when someone passes 'daily' or 'Youtube'. These two
-- helpers turn that into one sentence naming the bad argument.

create or replace function analytics_granularity(g text) returns text
language plpgsql immutable as $$
begin
  if lower(coalesce(g, '')) not in ('hour', 'day', 'week', 'month') then
    raise exception 'unsupported granularity %; expected one of hour, day, week, month', g
      using errcode = '22023';
  end if;
  return lower(g);
end $$;

create or replace function analytics_platform(p text) returns text
language plpgsql immutable as $$
begin
  if lower(coalesce(p, 'all')) not in ('all', 'youtube', 'instagram', 'tiktok') then
    raise exception 'unsupported platform %; expected one of all, youtube, instagram, tiktok', p
      using errcode = '22023';
  end if;
  return lower(coalesce(p, 'all'));
end $$;


-- --- rollup_followers -------------------------------------------------------
-- Followers per period per platform, with the gained and lost halves of the
-- change split out so the Growth tab can draw them as diverging bars.
--
--   followers  the last snapshot at or before the end of the period, summed
--              over the platform's accounts. Carried forward: a period with no
--              snapshot in it repeats the previous value rather than dropping
--              to zero, because followers are a stock and nobody lost them.
--   gained     sum over accounts of max(change, 0)
--   lost       sum over accounts of max(-change, 0)
--
-- Split per account and then summed, not computed from the platform total, so
-- that one account growing while another shrinks shows as both a gain and a
-- loss rather than cancelling to nothing.
--
-- An account with no snapshot before the period start contributes 0 to both
-- gained and lost, not its whole follower count. We do not know that those
-- followers arrived in this period; we know only that this is the first time
-- we looked. `greatest()` ignores NULLs in Postgres, which is what makes that
-- fall out of the expression below rather than needing a special case.
create or replace function rollup_followers(
  from_ts timestamptz,
  to_ts timestamptz,
  granularity text,
  platform_filter text default 'all')
returns table (period timestamptz, platform text, followers bigint, gained bigint, lost bigint)
language sql stable security definer set search_path = public as $$
  with args as (
    select analytics_granularity(granularity) as gran,
           analytics_platform(platform_filter) as plat
  ),
  bounds as (
    select p_local at time zone 'Asia/Bangkok' as p_start,
           (p_local + ('1 ' || a.gran)::interval) at time zone 'Asia/Bangkok' as p_end
    from args a,
         generate_series(date_trunc(a.gran, from_ts at time zone 'Asia/Bangkok'),
                         date_trunc(a.gran, to_ts   at time zone 'Asia/Bangkok'),
                         ('1 ' || a.gran)::interval) as p_local
  ),
  acct as (
    select ac.id, ac.platform
    from accounts ac, args a
    where a.plat = 'all' or ac.platform = a.plat
  ),
  per_account as (
    select b.p_start, ac.platform, e.followers as at_end, s.followers as at_start
    from bounds b
    cross join acct ac
    left join lateral (
      select sn.followers from account_snapshots sn
      where sn.account_id = ac.id and sn.taken_at < b.p_end
      order by sn.taken_at desc limit 1) e on true
    left join lateral (
      select sn.followers from account_snapshots sn
      where sn.account_id = ac.id and sn.taken_at < b.p_start
      order by sn.taken_at desc limit 1) s on true
  )
  select pa.p_start,
         pa.platform,
         coalesce(sum(pa.at_end), 0)::bigint,
         coalesce(sum(greatest(pa.at_end - pa.at_start, 0)), 0)::bigint,
         coalesce(sum(greatest(pa.at_start - pa.at_end, 0)), 0)::bigint
  from per_account pa
  where is_allowed()
  group by pa.p_start, pa.platform
  order by 1, 2;
$$;


-- --- rollup_engagement ------------------------------------------------------
-- Interactions per period per platform, and the rate they represent.
--
-- likes / comments / shares are gains inside the period, on the same
-- last-snapshot-in minus last-snapshot-before basis rollup_views uses for
-- views, and clamped at zero at the platform total the same way: the platforms
-- do revise counters downward when a comment or a like is deleted, and a
-- negative "likes this week" is a worse answer than a zero.
--
-- engagement_rate is (likes + comments + shares) / views over the same period
-- and the same posts — one ratio of two sums, NOT the mean of the per-post
-- rates. Those two are not the same number. A mean of rates gives a post with
-- 40 views and 4 likes the same weight as a post with 400,000 views and 4,000
-- likes, which is the standard way a dashboard ends up reporting a rate nobody
-- can find in the data. This is identical to a view-weighted mean of the
-- per-post rates, which is what the plan asked for, written the short way.
--
-- The unit is a fraction, not a percentage: 0.0625 means 6.25%. That matches
-- `post_snapshots.engagement_rate`, which is Zernio's `engagementRate` stored
-- as sent. The dashboard multiplies by 100 in one place, in format.js.
--
-- views is null-safe but not returned: no dual axes, and views already have
-- their own function. A period with no views at all returns a null rate, not
-- a zero one, so the chart can break the line instead of drawing a floor.
create or replace function rollup_engagement(
  from_ts timestamptz,
  to_ts timestamptz,
  granularity text,
  platform_filter text default 'all')
returns table (period timestamptz, platform text, likes bigint, comments bigint,
               shares bigint, engagement_rate numeric)
language sql stable security definer set search_path = public as $$
  with args as (
    select analytics_granularity(granularity) as gran,
           analytics_platform(platform_filter) as plat
  ),
  bounds as (
    select p_local at time zone 'Asia/Bangkok' as p_start,
           (p_local + ('1 ' || a.gran)::interval) at time zone 'Asia/Bangkok' as p_end
    from args a,
         generate_series(date_trunc(a.gran, from_ts at time zone 'Asia/Bangkok'),
                         date_trunc(a.gran, to_ts   at time zone 'Asia/Bangkok'),
                         ('1 ' || a.gran)::interval) as p_local
  ),
  snaps as (
    select ps.post_id, p.platform, ps.taken_at, ps.views, ps.likes, ps.comments, ps.shares
    from post_snapshots ps
    join posts p on p.id = ps.post_id, args a
    where a.plat = 'all' or p.platform = a.plat
  ),
  seen as (select distinct sn.post_id, sn.platform from snaps sn),
  per_post as (
    select b.p_start, sp.platform,
           coalesce(e.views, 0)    - coalesce(s.views, 0)    as d_views,
           coalesce(e.likes, 0)    - coalesce(s.likes, 0)    as d_likes,
           coalesce(e.comments, 0) - coalesce(s.comments, 0) as d_comments,
           coalesce(e.shares, 0)   - coalesce(s.shares, 0)   as d_shares
    from bounds b
    cross join seen sp
    left join lateral (
      select x.views, x.likes, x.comments, x.shares from snaps x
      where x.post_id = sp.post_id and x.taken_at < b.p_end
      order by x.taken_at desc limit 1) e on true
    left join lateral (
      select x.views, x.likes, x.comments, x.shares from snaps x
      where x.post_id = sp.post_id and x.taken_at < b.p_start
      order by x.taken_at desc limit 1) s on true
  ),
  totals as (
    select pp.p_start, pp.platform,
           greatest(sum(pp.d_views), 0)    as views,
           greatest(sum(pp.d_likes), 0)    as likes,
           greatest(sum(pp.d_comments), 0) as comments,
           greatest(sum(pp.d_shares), 0)   as shares
    from per_post pp
    where is_allowed()
    group by pp.p_start, pp.platform
  )
  select t.p_start, t.platform,
         t.likes::bigint, t.comments::bigint, t.shares::bigint,
         round((t.likes + t.comments + t.shares)::numeric / nullif(t.views, 0), 6)
  from totals t
  order by 1, 2;
$$;


-- --- post_deltas ------------------------------------------------------------
-- One row per post, with what it was worth at each end of the window. This is
-- the Posts tab's whole data source and, through it, the posts-table artifact.
--
--   views_end     the last snapshot AT OR BEFORE to_ts
--   views_start   the last snapshot AT OR BEFORE from_ts, or 0
--   views_gained  views_end - views_start
--
-- Note the `<=` here against the `<` the period rollups use. Those two are
-- bounding a half-open period; these two are reading a counter at an instant,
-- and "as of to_ts" ought to include a snapshot taken exactly then.
--
-- A post first seen inside the window has no snapshot at or before from_ts, so
-- views_start is 0 and views_gained is its whole view total. That is the right
-- answer — the post did gain all of those views inside the window — and it is
-- also why views_gained can exceed the lifetime figure of an older post.
--
-- views_gained is NOT clamped at zero. Platforms do revise counts down; a
-- negative here is real information about the data and the Posts tab shows it
-- rather than rounding it away. The period rollups clamp because they are
-- feeding charts that a reader will read as "activity"; this table is read as
-- "what the record says".
--
-- likes / comments / shares / engagement_rate are lifetime values from the
-- views_end snapshot, not deltas. The tab's column headers say so.
--
-- Posts with no snapshot at or before to_ts are omitted entirely: they did not
-- exist as far as this window is concerned.
create or replace function post_deltas(
  from_ts timestamptz,
  to_ts timestamptz,
  platform_filter text default 'all')
returns table (post_id text, platform text, title text, url text, published_at timestamptz,
               views_start bigint, views_end bigint, views_gained bigint,
               likes integer, comments integer, shares integer, engagement_rate numeric)
language sql stable security definer set search_path = public as $$
  with args as (select analytics_platform(platform_filter) as plat)
  select p.id, p.platform, p.title, p.url, p.published_at,
         coalesce(s.views, 0)::bigint,
         coalesce(e.views, 0)::bigint,
         (coalesce(e.views, 0) - coalesce(s.views, 0))::bigint,
         coalesce(e.likes, 0), coalesce(e.comments, 0), coalesce(e.shares, 0),
         e.engagement_rate
  from posts p
  cross join args a
  left join lateral (
    select x.views, x.likes, x.comments, x.shares, x.engagement_rate
    from post_snapshots x
    where x.post_id = p.id and x.taken_at <= to_ts
    order by x.taken_at desc limit 1) e on true
  left join lateral (
    select x.views from post_snapshots x
    where x.post_id = p.id and x.taken_at <= from_ts
    order by x.taken_at desc limit 1) s on true
  where (a.plat = 'all' or p.platform = a.plat)
    and e.views is not null
    and is_allowed()
  order by 8 desc, 7 desc;
$$;


-- --- episode_rollup ---------------------------------------------------------
-- One row per episode: the long cut on YouTube, plus every clip the collector
-- matched to it, split by platform.
--
-- `total_reach` is A SUM OF VIEW COUNTS across the episode's cuts. It is not
-- reach in the advertising sense and it is not people. One person who watches
-- the episode on YouTube and then sees two clips on Instagram is three in this
-- number. It is named `total_reach` because that is what the spec's table and
-- the episode-report artifact call the column, and the artifacts inherit this
-- figure — so when a sponsor asks what it means, this comment is the answer,
-- and the artifact carries the same sentence on the page.
--
-- The long cut is the post with id 'yt:' || youtube_video_id, which is the key
-- the collector builds in transform.post_key(). That post also matches its own
-- episode's title, so it has episode_id set too — it is excluded from every
-- clip figure by id, not by platform, because YouTube Shorts clips are also
-- youtube posts and do belong in clip_views_youtube.
--
-- An episode whose long cut has never been snapshotted (published, not yet
-- collected) still returns a row, with yt_views 0. The Episodes tab shows it.
create or replace function episode_rollup()
returns table (episode_id integer, season integer, number text, title text,
               guest text, role text, published_at timestamptz, youtube_video_id text,
               yt_views bigint, clip_count integer,
               clip_views_youtube bigint, clip_views_instagram bigint,
               clip_views_tiktok bigint, total_reach bigint)
language sql stable security definer set search_path = public as $$
  with clips as (
    select c.episode_id, c.platform, c.views
    from v_post_latest c
    join episodes e2 on e2.id = c.episode_id
    where c.post_id <> 'yt:' || e2.youtube_video_id
  ),
  by_ep as (
    select cl.episode_id,
           count(*)::int as clip_count,
           coalesce(sum(cl.views) filter (where cl.platform = 'youtube'), 0)   as v_yt,
           coalesce(sum(cl.views) filter (where cl.platform = 'instagram'), 0) as v_ig,
           coalesce(sum(cl.views) filter (where cl.platform = 'tiktok'), 0)    as v_tt,
           coalesce(sum(cl.views), 0) as v_all
    from clips cl
    group by cl.episode_id
  )
  select e.id, e.season, e.number, e.title, e.guest, e.role,
         coalesce(main.published_at, e.published_at),
         e.youtube_video_id,
         coalesce(main.views, 0)::bigint,
         coalesce(b.clip_count, 0),
         coalesce(b.v_yt, 0)::bigint,
         coalesce(b.v_ig, 0)::bigint,
         coalesce(b.v_tt, 0)::bigint,
         (coalesce(main.views, 0) + coalesce(b.v_all, 0))::bigint
  from episodes e
  left join v_post_latest main on main.post_id = 'yt:' || e.youtube_video_id
  left join by_ep b on b.episode_id = e.id
  where is_allowed()
  order by e.season desc, coalesce(main.published_at, e.published_at) desc nulls last, e.number desc;
$$;


-- --- demographics_compare ---------------------------------------------------
-- The latest demographic window for one `kind`, and a comparable earlier one,
-- side by side, so the Audience tab shows change in one round trip.
--
-- `window_days` is HOW FAR BACK THE COMPARISON SITS, not a filter on window
-- length. That distinction matters: the collector writes YouTube's 90-day
-- rolling demographics every day, so consecutive rows overlap by 89 days and
-- comparing them shows nothing but noise. With window_days = 90 the comparison
-- window is the most recent one ending at least 90 days before the current
-- one ends — i.e. the two windows do not overlap, and a shift between them is
-- a real shift.
--
-- If there is no window that old, prev_value and delta come back NULL and the
-- current figures still come back. The tab says "no comparable earlier window"
-- rather than drawing a 100% rise.
--
-- UNITS ARE NOT THE SAME ACROSS KINDS, and this function does not normalise
-- them. yt_age and yt_gender are percentages of the channel's views (they sum
-- to about 100). yt_country is an absolute view count. ig_age, ig_gender,
-- ig_city and ig_country are absolute follower counts. The renderer converts
-- to a share of the returned rows; this function returns what was collected.
--
-- Values are summed over accounts. There is exactly one account per platform
-- today, so that sum is a pass-through. If a second YouTube account is ever
-- connected, the percentage kinds above will need weighting by that account's
-- views before they are summed — summing two percentages is meaningless.
--
-- The `kind` parameter shares its name with `demographics.kind`, so every
-- reference to the parameter below is qualified as `demographics_compare.kind`.
-- Unqualified, the column would win.
create or replace function demographics_compare(kind text, window_days integer default 90)
returns table (dimension text, value numeric, prev_value numeric, delta numeric,
               window_start date, window_end date,
               prev_window_start date, prev_window_end date)
language sql stable security definer set search_path = public as $$
  with cur_end as (
    select max(d.window_end) as w_end
    from demographics d
    where d.kind = demographics_compare.kind
  ),
  cur_rows as (
    select d.dimension, d.value, d.window_start, d.window_end
    from demographics d, cur_end
    where d.kind = demographics_compare.kind and d.window_end = cur_end.w_end
  ),
  prev_end as (
    select max(d.window_end) as w_end
    from demographics d, cur_end
    where d.kind = demographics_compare.kind
      and d.window_end <= cur_end.w_end - demographics_compare.window_days
  ),
  prev_rows as (
    select d.dimension, d.value, d.window_start, d.window_end
    from demographics d, prev_end
    where d.kind = demographics_compare.kind and d.window_end = prev_end.w_end
  ),
  cur_agg  as (select r.dimension, sum(r.value) as value from cur_rows  r group by r.dimension),
  prev_agg as (select r.dimension, sum(r.value) as value from prev_rows r group by r.dimension),
  cur_win  as (select min(r.window_start) as ws, max(r.window_end) as we from cur_rows),
  prev_win as (select min(r.window_start) as ws, max(r.window_end) as we from prev_rows)
  select coalesce(c.dimension, p.dimension),
         c.value,
         p.value,
         case when p.value is null then null else coalesce(c.value, 0) - p.value end,
         cw.ws, cw.we, pw.ws, pw.we
  from cur_agg c
  full join prev_agg p on p.dimension = c.dimension
  cross join cur_win cw
  cross join prev_win pw
  where is_allowed()
  order by 2 desc nulls last, 1;
$$;


-- --- grants -----------------------------------------------------------------
-- See note 1 in the header: `from public` is what actually closes these, and
-- without it the `security definer` functions above would answer the anon key.

revoke execute on function analytics_granularity(text) from public, anon;
revoke execute on function analytics_platform(text) from public, anon;
grant  execute on function analytics_granularity(text) to authenticated;
grant  execute on function analytics_platform(text) to authenticated;

revoke execute on function rollup_followers(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_followers(timestamptz, timestamptz, text, text) to authenticated;

revoke execute on function rollup_engagement(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_engagement(timestamptz, timestamptz, text, text) to authenticated;

revoke execute on function post_deltas(timestamptz, timestamptz, text) from public, anon;
grant  execute on function post_deltas(timestamptz, timestamptz, text) to authenticated;

revoke execute on function episode_rollup() from public, anon;
grant  execute on function episode_rollup() to authenticated;

revoke execute on function demographics_compare(text, integer) from public, anon;
grant  execute on function demographics_compare(text, integer) to authenticated;

-- Re-stating 003's grants so the two files agree. Both of these are
-- `security invoker`, so RLS is already doing the work and neither is leaking
-- today; this only removes a PUBLIC grant nobody meant to hand out.
revoke execute on function rollup_views(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_views(timestamptz, timestamptz, text, text) to authenticated;

revoke execute on function live_json() from public, anon;
grant  execute on function live_json() to authenticated, service_role;
