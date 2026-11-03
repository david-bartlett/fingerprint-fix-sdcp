# Fewer duplicate new-version notifications

PR #163 · Claude · 2026-11-03

## What changed
- These never replace a newer version already in `notified-release`: `told` (`lib/notify-update.sh`, `sort -V`), `notify-dbus.py`'s `NOTIFY_SHOWN_FILE` write (`_version`), and `show_notification`'s plain-path write (`version_key`, with unparsable versions ignored).
- `show_notification`: after a refused `systemd-run`, checks `is-active` again before the plain fallback.
- PLAN.md (`update_check.py` row), CHANGELOG.

## Why
- Codex review of `61d2cf1` (2.13.4), on #162. The same three findings as galaxybook-fan's #57, all duplicates and none a missed release:
  1. Concurrent starts showed a plain copy as well. Fixed.
  2. A notifier stopped between appearing and being noted. **Left on purpose**: noting earlier brings back #162's missed-release case. The window is up to 0.5 s, or the notification's lifetime with a notify-send without `--print-id`. Documented.
  3. An older notifier overwrote a newer version's record. Fixed.

## Tested
- `told` through `notify-update.sh`, and `notify-dbus.py` with a stand-in `gi`, with `notified-release` already newer, older or absent: an older version never replaces a newer one.
- `show_notification` without systemd-run (plain path): it keeps the newer record and writes a newer one.
- A fake `systemd-run` that refuses while the unit becomes active: no plain copy.
- `bash -n`, `py_compile lib/*.py`, shellcheck: no new warnings.
