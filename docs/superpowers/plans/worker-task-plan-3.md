# Worker task: TSN Talks Plan 3 — private analytics

You are building the private analytics dashboard for the TSN Talks podcast media kit.

## Read these first, in this order

1. `docs/superpowers/plans/2026-09-15-plan-3-analytics.md` — **your plan.** Tasks 1 to 17, in order, one commit each. It is written to be followed literally.
2. `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` sections 2, 3.4, 4, 7, 8 — the design spec the plan implements.
3. `PRODUCT.md` — the show's register and anti-references.
4. `docs/superpowers/plans/2026-09-15-plan-2-public-site.md` — how the public site was built. Match its conventions; you are extending that codebase, not starting one.

## The two things that will trip you up

**You have no network access to Supabase and no `.env`.** This is deliberate. Build everything against committed fixtures under `tests/analytics/fixtures/` and stub Supabase in Playwright with `page.route`, exactly as `tests/site/conftest.py` already stubs the Storage copy of `live.json`. Do not try to reach the database. Do not invent a way to get credentials. If you need to know what real data looks like, write the assumption into `docs/analytics-data-contract.md` and build against it.

**You write the SQL but you do not run it.** `db/004_analytics.sql` is applied by hand on review. Write it as if a careful person will read every line before executing it, because one will.

## Rules

- One commit per task. Conventional Commits, with a `Nav-Agent: <your worker name>` trailer. **No `Co-Authored-By` trailer.**
- `python -m pytest tests/ -q` must be green before every commit. If a test fails for an environmental reason, say so in the commit body — never edit a test to make it pass.
- Do not touch `site/index.html`, `site/live/`, `site/partner/`, `site/js/home.js`, `site/js/live.js`, or anything under `collector/`. `site/css/site.css` may only be appended to, and only with new custom properties.
- Pin every CDN dependency to an exact version, from cdnjs. No `@latest`.
- The Supabase **anon** key belongs in the client source and is safe there — RLS gives anonymous users nothing. The service-role key must never appear anywhere under `site/`.
- If a task is wrong or impossible as written: do its neighbours, and explain in that commit's body. Do not silently redesign. Half a plan executed faithfully beats a whole one executed creatively.
- Work on the branch you are already on. Commit everything; an uncommitted file never leaves this machine.

## Definition of done

Seventeen commits, the suite green, and `docs/analytics-data-contract.md` accurate enough that someone who has never seen this repo could wire the dashboard to the real database from it alone.

If you run short of budget, stop cleanly at a task boundary with the suite green rather than leaving task 12 half-built. Tasks 1 and 2 are the ones that must exist no matter what — they are what survives if nothing else does.
