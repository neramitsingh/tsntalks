-- ============================================================================
-- 005_view_privileges.sql — close the two views that read past RLS.
--
-- Found on review of 004 (2026-09-16, docs/analytics-data-contract.md §7.2):
-- 003 created v_post_latest and v_account_latest as ordinary views, which run
-- with their owner's privileges (postgres) and therefore ignore row-level
-- security on posts, post_snapshots and account_snapshots. Supabase's default
-- privileges then granted `anon` and `authenticated` every privilege on both,
-- so an anonymous PostgREST call could read the latest snapshot of every post
-- while the tables themselves gave it nothing. Checked live before this file
-- was written: information_schema.role_table_grants listed anon with SELECT
-- (and INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER) on both views.
--
-- Two fixes, both needed:
--   1. security_invoker = on: the view runs as whoever queries it, so the
--      tables' RLS applies. The collector (service_role, bypasses RLS) and the
--      security-definer rollups in 004 (run as postgres) are unaffected;
--      rollup_views (security invoker) now sees exactly what the caller may.
--   2. revoke from anon and authenticated: nothing in the dashboard reads the
--      views directly (it goes through the functions), so there is no reason
--      for either role to hold a grant. service_role keeps its access for the
--      collector's live_json().
--
-- Idempotent. Apply after 004:
--   python infra/apply_sql.py db/005_view_privileges.sql
-- ============================================================================

alter view v_post_latest    set (security_invoker = on);
alter view v_account_latest set (security_invoker = on);

revoke all on v_post_latest    from anon, authenticated, public;
revoke all on v_account_latest from anon, authenticated, public;

-- And stop the default privileges handing the next view out the same way.
alter default privileges in schema public revoke all on tables from anon;
