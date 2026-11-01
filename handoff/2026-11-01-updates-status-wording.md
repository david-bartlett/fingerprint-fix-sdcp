# updates status: the on / off command on its own line

PR #127 · Claude · 2026-11-01

## What changed
- `lib/update_check.py` `cmd_updates("status")`: *"New version" notifications: on (GitHub checked at login and hourly)*, then *To turn them off: galaxybook-fingerprint-manager updates off* (off: *To turn them on: …*). `updates on` says *checked at login and hourly*.
- CHANGELOG.

## Why
- David, on galaxybook-fan's same line: the command in brackets read as if the notifications were off. galaxybook-fan's PR #39 does the same.

## Tested
- `py_compile`; both states.
