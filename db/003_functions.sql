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
-- where a post's delta = last snapshot in period - last snapshot before the period (or its first snapshot's views if new).
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
           coalesce((select views from snaps x where x.post_id = s.post_id and x.taken_at < b.p_end order by taken_at desc limit 1), 0)
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
    select e.id, e.season, e.number, e.guest, e.role, e.youtube_video_id,
           coalesce(pl.published_at, e.published_at) as published_at,
           pl.views, pl.likes, pl.comments,
           'https://www.youtube.com/watch?v=' || e.youtube_video_id as url,
           'https://i.ytimg.com/vi/' || e.youtube_video_id || '/maxresdefault.jpg' as thumb,
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
    'episodes', (select jsonb_agg(to_jsonb(eps) order by published_at desc nulls last, season desc, (number)::int desc) from eps),
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
