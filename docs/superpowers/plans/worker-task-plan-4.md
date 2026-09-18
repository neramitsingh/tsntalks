# Worker task: TSN Talks Plan 4 — charts on Observable Plot

You are moving the private analytics dashboard's charts onto Observable Plot without changing what the dashboard promises.

## Read these first, in this order

1. `docs/superpowers/plans/2026-09-18-plan-4-charts.md` — **your plan.** Tasks 1 to 13, in order, one commit each. Part A is not yours.
2. `site/js/analytics/charts.js` — the file you are rewriting. Its header comment is the rulebook.
3. `tests/analytics/test_charts.py` and `tests/analytics/test_tabs.py` — the contracts. Plot goes *under* them.
4. `PRODUCT.md` "The visual world" and `docs/superpowers/specs/2026-09-15-tsn-talks-live-design.md` §3.4 — the register.

## The two things that will trip you up

**You have no network access to Supabase and no `.env`.** Deliberate. Everything runs against the committed fixtures with the Playwright stubs in `tests/analytics/conftest.py`. The first test run downloads d3 and Plot once into `tests/analytics/stubs/vendor/` (gitignored) — that is the only network the suite needs.

**Plot must not repaint the platforms.** Never hand Plot a `fill`/`stroke` *channel* for series identity; one mark per series with a constant colour, resolved from the CSS token (`resolvedColor` in Task 2). YouTube `#E8621A`, TikTok `#2EA6A0`, Instagram `#7C6BF0`, fixed for life.

## Rules

- One commit per task. Conventional Commits, with a `Nav-Agent: <your worker name>` trailer. **No `Co-Authored-By` trailer.**
- `python -m pytest tests/ -q` must be green before every commit. If a test fails for an environmental reason, say so in the commit body — never edit a test to make it pass, except the three the plan rewrites by name.
- Do not touch `site/index.html`, `site/live/`, `site/partner/`, `site/js/home.js`, `site/js/live.js`, anything under `collector/`, or anything under `db/`.
- Pin every CDN dependency to the exact versions and hashes in the plan. No `@latest`, no jsDelivr `.min` that jsDelivr generates itself.
- Line endings are LF. `.gitattributes` enforces it; do not fight it.
- If a task is wrong or impossible as written: do its neighbours and explain in that commit's body. Do not silently redesign.
- Work on the branch you are already on. Commit everything; an uncommitted file never leaves this machine.

## Definition of done

Thirteen commits, the suite green, six PNGs under `docs/superpowers/plans/plan-4-shots/` that a reviewer can open without running anything.

If you run short of budget, stop cleanly at a task boundary with the suite green. Tasks 1 to 5 are what must exist no matter what: with them, every existing chart is on Plot and nothing has regressed.
