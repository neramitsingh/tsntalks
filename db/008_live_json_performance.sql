-- ============================================================================
-- 008_live_json_performance.sql — live_json() reads each post's latest
-- snapshot once, through the snapshot index.
--
-- Found when the hourly collect run went red on 2026-10-04 and stayed red:
--   "publish: rpc live_json failed 500: {"code":"57014", ...
--    "message":"canceling statement due to statement timeout"}"
-- The service-role call runs under the authenticator's 8 s statement timeout,
-- and live_json() had crept up to 7.5-9.4 s (91,607 snapshots, 229 posts).
-- It failed on and off from 4-Oct 05:00 UTC, then every hour from 18:00.
--
-- The cause is the same shape 006 fixed in the rollups. Every reference to
-- v_post_latest re-runs its DISTINCT ON over the whole of post_snapshots, and
-- the eps CTE referenced it twice per episode in correlated subqueries
-- (clip_views, clips): 34 episodes x 2 x 150 ms = 8.6 of the 9.4 s. Each
-- hourly run adds ~400 snapshots, so the cost grew by about a second a day.
--
-- Now a `latest` CTE takes each post's newest snapshot by a single probe of
-- the primary key (post_id, taken_at), once, and everything that read
-- v_post_latest reads that instead. Measured on the live data: 25 ms, and it
-- scales with posts, not with snapshots.
--
-- Same output, byte for byte (compared against the old function in one
-- statement before applying). The one textual change is `order by m, platform`
-- in months: the old order inside a month was an unpinned tie that happened
-- to come out by platform; it is now pinned to what the site already gets.
-- v_post_latest itself is unchanged; the dashboard still uses it.
--
-- Idempotent:  python infra/apply_sql.py db/008_live_json_performance.sql
-- ============================================================================

create or replace function live_json() returns jsonb
language sql stable as $$
  with latest as materialized (
    select p.id as post_id, p.platform, p.published_at, p.title, p.url, p.thumb_url, p.episode_id,
           s.taken_at, s.views, s.likes, s.comments
    from posts p
    join lateral (
      select x.taken_at, x.views, x.likes, x.comments from post_snapshots x
      where x.post_id = p.id
      order by x.taken_at desc limit 1) s on true
  ),
  plat as (
    select a.platform,
           max(al.followers) as followers,
           sum(pl.views) as views, count(pl.post_id) as posts,
           max(al.taken_at) as followers_at
    from accounts a
    left join v_account_latest al on al.account_id = a.id
    left join latest pl on pl.platform = a.platform
    group by a.platform
  ),
  tops as (
    select platform, jsonb_build_object('title', title, 'views', views, 'url', url, 'thumb', thumb_url, 'date', published_at) as top
    from (select *, row_number() over (partition by platform order by views desc) rn from latest) t where rn = 1
  ),
  months as (
    select to_char(date_trunc('month', published_at at time zone 'Asia/Bangkok'), 'YYYY-MM') as m, platform, sum(views) as views
    from latest where published_at is not null group by 1, 2
  ),
  eps as (
    select e.id, e.season, e.number, e.guest, e.role, e.youtube_video_id,
           coalesce(pl.published_at, e.published_at) as published_at,
           pl.views, pl.likes, pl.comments,
           'https://www.youtube.com/watch?v=' || e.youtube_video_id as url,
           'https://i.ytimg.com/vi/' || e.youtube_video_id || '/maxresdefault.jpg' as thumb,
           (select coalesce(sum(c.views), 0) from latest c where c.episode_id = e.id and c.platform <> 'youtube') as clip_views,
           (select count(*) from latest c where c.episode_id = e.id and c.platform <> 'youtube') as clips
    from episodes e left join latest pl on pl.post_id = 'yt:' || e.youtube_video_id
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
    'months', (select jsonb_agg(jsonb_build_object('m', m, 'platform', platform, 'views', views) order by m, platform) from months),
    'episodes', (select jsonb_agg(to_jsonb(eps) order by published_at desc nulls last, season desc, (number)::int desc) from eps),
    'demographics', (select jsonb_object_agg(kind, items) from demo),
    'yt_90d', (select to_jsonb(yt88) from yt88)
  );
$$;

revoke execute on function live_json() from public, anon;
grant  execute on function live_json() to authenticated, service_role;
