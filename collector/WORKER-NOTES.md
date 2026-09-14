# Worker notes

## Pytest output (last line)

```
30 passed in 0.23s
```

## Deviations from the plan

- **Test count.** The plan's "Definition of done" line 3 says the suite should print
  `27 passed`, but the per-task counts in the plan itself (3 + 11 + 8 + 5 + 3) sum
  to 30, and that is what the suite actually reports. No code change was needed; I
  treated the per-task counts as authoritative. The reason for the discrepancy in
  the plan text isn't stated — most likely a copy-paste leftover from an earlier
  version of the episodes or transform modules.
- **Python version.** The plan says Python 3.12; only Python 3.13.2 is installed
  on this machine. `requires-python = ">=3.12"` in `pyproject.toml` accepts 3.13,
  every test passes, and `pip install -e ".[dev]"` succeeded with `yt-dlp`
  2026.8.19 (so the no-`yt-dlp` fallback path in the brief was not exercised).
- **`TITLE_RE` delimiter class.** Wrote it as `[:\-–,\s]` (colon / hyphen /
  en-dash / comma / whitespace) instead of `[:\-–,]` so the title
  `TSN Talks Ep. 13 - Dr. Sunil (Part 2)` continues to parse when the dash is
  followed by an extra space. All eight episode tests pass unchanged.