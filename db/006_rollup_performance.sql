-- ============================================================================
-- 006_rollup_performance.sql — rollup_views and rollup_engagement, indexed.
--
-- Found on the first live open of /analytics (2026-09-16): with a 30-day
-- frame by day, rollup_views and rollup_engagement both hit the 8 s statement
-- timeout Supabase sets for `authenticated`, and the Overview's first two
-- panels showed "canceling statement due to statement timeout". Through the
-- management connection the same calls took 0.7 s and 3.9 s — slow, and the
-- dashboard fires four of them at once on a shared-CPU instance.
--
-- The cause is the shape, not the data (1,660 snapshots). Both functions built
-- a `snaps` CTE (post_snapshots joined to posts, filtered by platform) and then
-- read it twice per post per period through correlated subqueries. A CTE that
-- is referenced more than once is materialised, and a materialised CTE has no
-- index, so every one of those 30 × 218 × 2 lookups was a sequential scan of
-- the whole set. The same lookups against post_snapshots itself are single
-- probes of its primary key (post_id, taken_at).
--
-- Same signatures, same rows, same semantics: half-open periods in Bangkok
-- time, deltas of cumulative counters, clamped at zero at the platform total,
-- one ratio of two sums for the engagement rate.
--
-- rollup_views also moves from `security invoker` to `security definer` with
-- the `is_allowed()` guard, the posture every 004 function has. Measured as
-- the caller with the index rewrite alone it took 3.4 s, slower than before:
-- with RLS on, the policy is re-evaluated on every one of the 13,000 index
-- probes, which is exactly the cost the materialised CTE had been hiding. As
-- definer with the guard it is one check and 0.3 s. The guard, not RLS, is
-- what keeps a signed-in stranger at zero rows — same as 004.
--
-- rollup_followers changes one thing: a period with no snapshot from any
-- account on the platform returns NULL followers, not 0. The collector started
-- on 14 September; a 30-day chart drew a month of zeros and then a cliff to
-- 6,000, which is the fabricated zero line the data contract's own rule 1.2
-- forbids. The charts break a line on NULL. gained and lost stay 0.
-- Grants re-stated.
--
-- Idempotent:  python infra/apply_sql.py db/006_rollup_performance.sql
-- ============================================================================

create or replace function rollup_views(
  from_ts timestamptz,
  to_ts timestamptz,
  granularity text,
  platform_filter text default 'all')
returns table (period timestamptz, platform text, views bigint, posts_published integer)
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
  -- every post that has ever been snapshotted, on the platforms asked for
  seen as (
    select p.id as post_id, p.platform
    from posts p, args a
    where (a.plat = 'all' or p.platform = a.plat)
      and exists (select 1 from post_snapshots ps where ps.post_id = p.id)
  ),
  per_post as (
    select b.p_start, s.platform,
           coalesce(e.views, 0) - coalesce(st.views, 0) as delta
    from bounds b
    cross join seen s
    left join lateral (
      select x.views from post_snapshots x
      where x.post_id = s.post_id and x.taken_at < b.p_end
      order by x.taken_at desc limit 1) e on true
    left join lateral (
      select x.views from post_snapshots x
      where x.post_id = s.post_id and x.taken_at < b.p_start
      order by x.taken_at desc limit 1) st on true
  )
  select pp.p_start as period,
         pp.platform,
         greatest(sum(pp.delta), 0)::bigint as views,
         (select count(*) from posts q, args a
            where q.published_at >= pp.p_start
              and q.published_at < pp.p_start + ('1 ' || a.gran)::interval
              and (a.plat = 'all' or q.platform = pp.platform))::int as posts_published
  from per_post pp
  where is_allowed()
  group by pp.p_start, pp.platform
  order by 1, 2;
$$;


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
  seen as (
    select p.id as post_id, p.platform
    from posts p, args a
    where (a.plat = 'all' or p.platform = a.plat)
      and exists (select 1 from post_snapshots ps where ps.post_id = p.id)
  ),
  per_post as (
    select b.p_start, s.platform,
           coalesce(e.views, 0)    - coalesce(st.views, 0)    as d_views,
           coalesce(e.likes, 0)    - coalesce(st.likes, 0)    as d_likes,
           coalesce(e.comments, 0) - coalesce(st.comments, 0) as d_comments,
           coalesce(e.shares, 0)   - coalesce(st.shares, 0)   as d_shares
    from bounds b
    cross join seen s
    left join lateral (
      select x.views, x.likes, x.comments, x.shares from post_snapshots x
      where x.post_id = s.post_id and x.taken_at < b.p_end
      order by x.taken_at desc limit 1) e on true
    left join lateral (
      select x.views, x.likes, x.comments, x.shares from post_snapshots x
      where x.post_id = s.post_id and x.taken_at < b.p_start
      order by x.taken_at desc limit 1) st on true
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


-- rollup_followers, from 004, with NULL for a period nothing has been
-- snapshotted in yet (see the header).
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
         sum(pa.at_end)::bigint,                                            -- NULL until the first snapshot
         coalesce(sum(greatest(pa.at_end - pa.at_start, 0)), 0)::bigint,
         coalesce(sum(greatest(pa.at_start - pa.at_end, 0)), 0)::bigint
  from per_account pa
  where is_allowed()
  group by pa.p_start, pa.platform
  order by 1, 2;
$$;


revoke execute on function rollup_views(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_views(timestamptz, timestamptz, text, text) to authenticated, service_role;

revoke execute on function rollup_followers(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_followers(timestamptz, timestamptz, text, text) to authenticated;

revoke execute on function rollup_engagement(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_engagement(timestamptz, timestamptz, text, text) to authenticated;
