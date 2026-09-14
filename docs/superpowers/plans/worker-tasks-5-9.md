# Worker task: implement Plan 1 Tasks 5 to 9 (collector code)

You are working in a git worktree of the `tsntalks` repo on a branch of your own. Commit on the current branch when done. Do not push.

## What to build

Open `docs/superpowers/plans/2026-09-15-plan-1-collector-and-database.md` and implement **Task 5, Task 6, Task 7, Task 8 and Task 9 exactly as written**, in that order. Every file's full content is in the plan; copy it faithfully, then run the tests. The fixtures the tests need are already committed under `collector/tests/fixtures/`.

Do NOT do Tasks 1 to 4 or 10 to 12. They touch secrets and live services and are done elsewhere.

## Environment

- Windows, Python 3.12. Create the venv once: from `collector/`, run `python -m venv .venv` then `.venv\Scripts\pip install -e ".[dev]"`.
- Run tests from `collector/` with `.venv\Scripts\python -m pytest -q`.
- There is no `.env` and no network access needed: every test uses recorded fixtures or the `responses` library.
- If `pip install` fails on `yt-dlp` (no network), install the package without it: `.venv\Scripts\pip install requests pytest responses` and `.venv\Scripts\pip install -e . --no-deps`. The tests never import yt_dlp.

## Definition of done

1. `collector/tsn_collector/` contains `__init__.py`, `config.py`, `supa.py`, `transform.py`, `episodes.py`, `zernio.py`, `youtube.py`, `run.py`.
2. `collector/tests/` contains `test_supa.py`, `test_transform.py`, `test_episodes.py`, `test_clients.py`, `test_run.py`.
3. `.venv\Scripts\python -m pytest -q` prints `27 passed`.
4. One commit per task with the commit messages given in the plan (five commits). If a test in the plan fails because of a genuine mistake in the plan's code, fix the code (not the test) in the smallest way, and say what you changed in the commit body.
5. Write a short `collector/WORKER-NOTES.md`: the pytest output's last line, and any deviation from the plan with the reason.

Never commit `.venv`, `__pycache__` or `.env`.
