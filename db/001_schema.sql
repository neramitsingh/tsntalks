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
