# The hourly check asks every hour, not every other hour

PR #<n> · Claude · 2026-11-01

## What changed
- `lib/update_check.py`: `notify_once()` reuses GitHub's answer for 55 minutes (`REUSE`), not 3600 s.
- CHANGELOG.

## Why
- The timer is `OnCalendar=hourly` with `AccuracySec=1s`, and the cache time is written just after each run asks GitHub, so the next run on the hour found it a little under 3600 s old, reused it, and didn't ask: GitHub was asked every other hour (and at login). Spotted while making galaxybook-fan's check hourly (its PR #38 uses 55 minutes for the same reason).

## Tested
- `py_compile`.
