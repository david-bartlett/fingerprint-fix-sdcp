# An update can't leave the Manager behind

PR #158 · Claude · 2026-11-03

## What changed
- `pick_asset()` in `lib/update_check.py`: with the Manager installed, a deb or rpm release without its file gives `None`, rather than the driver alone.
- CHANGELOG.

## Why
- Codex finding (second pass), reproduced by Codex and here. The last line was a fallback for single-package releases, but every release since 2.0.0 has two, and an update only goes to a newer one. So it could only ever fire on an incomplete release, leaving the Manager on the old version.

## Tested
- `pick_asset()` for rpm and deb: both files, no Manager file, no driver file and neither, for driver only, Manager only and both.
- `py_compile`.
- Not here: a real update.

## For the next person
- With no match, the update stops with the existing message, and the notification's next check tries again.
