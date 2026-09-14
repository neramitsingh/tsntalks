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
