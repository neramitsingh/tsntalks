-- db/007_first_seen_baseline.sql
--
-- A post we started watching mid-window no longer "gains" its whole lifetime
-- on the day of its first snapshot.
--
-- Before: a post's baseline for a period was its last snapshot before the
-- period, else 0. Every post existed before 14 Sep 2026 and none had a
-- snapshot before it, so on 14 Sep each one gained its lifetime total and the
-- Overview drew a 2,367,710 column that flattened every other day to nothing
-- (the 16-Sep screenshots). The same rule sat in post_deltas, which is why the
-- Top-posts table read "gained here 943,702" for a video from November.
--
-- After, in all three functions:
--   baseline = the last snapshot strictly before the period start;
--            else, if the post was published before the period start (or its
--              published_at is unknown), its FIRST snapshot ever — only growth
--              since we began watching counts;
--            else 0 — a post published inside the period did gain everything
--              inside it.
--   and a post with no snapshot before the period END contributes 0, not a
--   negative (it has not been seen yet as far as that period is concerned).
--
-- Everything else — bounds, Bangkok day boundaries, the security-definer +
-- is_allowed() guard, the greatest(…, 0) clamp on the period rollups and the
-- deliberate absence of that clamp on post_deltas, the <= vs < asymmetry —
-- is carried over from 004 and 006 unchanged. Grants are restated because
-- CREATE OR REPLACE keeps them but a reader should not have to know that.
--
-- Applied by Nav on 2026-09-18 with infra/apply_sql.py. The dashboard prose
-- that describes the rule changes in Plan 4, Task 11.


-- --- rollup_views (from 006) -------------------------------------------------

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
  -- every post that has ever been snapshotted, on the platforms asked for,
  -- with its first snapshot (the baseline for posts we began watching late)
  seen as (
    select p.id as post_id, p.platform, p.published_at, f.views as first_views
    from posts p, args a
    join lateral (
      select x.views from post_snapshots x
      where x.post_id = p.id
      order by x.taken_at asc limit 1) f on true
    where (a.plat = 'all' or p.platform = a.plat)
  ),
  per_post as (
    select b.p_start, s.platform,
           case
             when e.views is null then 0
             else e.views - coalesce(
                    st.views,
                    case when s.published_at is null or s.published_at < b.p_start
                         then s.first_views else 0 end)
           end as delta
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

revoke execute on function rollup_views(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_views(timestamptz, timestamptz, text, text) to authenticated;


-- --- rollup_engagement (from 006) --------------------------------------------

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
    select p.id as post_id, p.platform, p.published_at,
           f.views as f_views, f.likes as f_likes, f.comments as f_comments, f.shares as f_shares
    from posts p, args a
    join lateral (
      select x.views, x.likes, x.comments, x.shares from post_snapshots x
      where x.post_id = p.id
      order by x.taken_at asc limit 1) f on true
    where (a.plat = 'all' or p.platform = a.plat)
  ),
  per_post as (
    select b.p_start, s.platform,
           -- `late` is true for a post we began watching after the period had
           -- already started: its first snapshot is the baseline, not zero.
           (s.published_at is null or s.published_at < b.p_start) as late,
           e.views, e.likes, e.comments, e.shares,
           st.views as st_views, st.likes as st_likes, st.comments as st_comments, st.shares as st_shares,
           s.f_views, s.f_likes, s.f_comments, s.f_shares
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
  deltas as (
    select p_start, platform,
      case when views    is null then 0 else views    - coalesce(st_views,    case when late then f_views    else 0 end) end as d_views,
      case when views    is null then 0 else likes    - coalesce(st_likes,    case when late then f_likes    else 0 end) end as d_likes,
      case when views    is null then 0 else comments - coalesce(st_comments, case when late then f_comments else 0 end) end as d_comments,
      case when views    is null then 0 else shares   - coalesce(st_shares,   case when late then f_shares   else 0 end) end as d_shares
    from per_post
  ),
  totals as (
    select d.p_start, d.platform,
           greatest(sum(d.d_views), 0)    as views,
           greatest(sum(d.d_likes), 0)    as likes,
           greatest(sum(d.d_comments), 0) as comments,
           greatest(sum(d.d_shares), 0)   as shares
    from deltas d
    where is_allowed()
    group by d.p_start, d.platform
  )
  select t.p_start, t.platform,
         t.likes::bigint, t.comments::bigint, t.shares::bigint,
         round((t.likes + t.comments + t.shares)::numeric / nullif(t.views, 0), 6)
  from totals t
  order by 1, 2;
$$;

revoke execute on function rollup_engagement(timestamptz, timestamptz, text, text) from public, anon;
grant  execute on function rollup_engagement(timestamptz, timestamptz, text, text) to authenticated;


-- --- post_deltas (from 004) --------------------------------------------------
-- views_start is now the first-seen baseline for a post that existed before
-- from_ts; the rest of 004's commentary on this function still holds
-- (<= bounds, no clamp, reach nullif, episode_id).

create or replace function post_deltas(
  from_ts timestamptz,
  to_ts timestamptz,
  platform_filter text default 'all')
returns table (post_id text, platform text, title text, url text, published_at timestamptz,
               views_start bigint, views_end bigint, views_gained bigint,
               likes integer, comments integer, shares integer, reach bigint,
               engagement_rate numeric, episode_id integer)
language sql stable security definer set search_path = public as $$
  with args as (select analytics_platform(platform_filter) as plat)
  select p.id, p.platform, p.title, p.url, p.published_at,
         coalesce(s.views, case when p.published_at is null or p.published_at < from_ts
                                then f.views else 0 end, 0)::bigint,
         coalesce(e.views, 0)::bigint,
         (coalesce(e.views, 0)
          - coalesce(s.views, case when p.published_at is null or p.published_at < from_ts
                                   then f.views else 0 end, 0))::bigint,
         coalesce(e.likes, 0), coalesce(e.comments, 0), coalesce(e.shares, 0),
         nullif(e.reach, 0),
         e.engagement_rate,
         p.episode_id
  from posts p
  cross join args a
  left join lateral (
    select x.views, x.likes, x.comments, x.shares, x.reach, x.engagement_rate
    from post_snapshots x
    where x.post_id = p.id and x.taken_at <= to_ts
    order by x.taken_at desc limit 1) e on true
  left join lateral (
    select x.views from post_snapshots x
    where x.post_id = p.id and x.taken_at <= from_ts
    order by x.taken_at desc limit 1) s on true
  left join lateral (
    select x.views from post_snapshots x
    where x.post_id = p.id
    order by x.taken_at asc limit 1) f on true
  where (a.plat = 'all' or p.platform = a.plat)
    and e.views is not null
    and is_allowed()
  order by 8 desc, 7 desc;
$$;

revoke execute on function post_deltas(timestamptz, timestamptz, text) from public, anon;
grant  execute on function post_deltas(timestamptz, timestamptz, text) to authenticated;
