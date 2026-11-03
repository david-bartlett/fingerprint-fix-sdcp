# Count a release as announced the moment its notification appears

PR #162 · Claude · 2026-11-03

## What changed
- `lib/update_check.py` `show_notification`:
  - starts `notify-update.sh` as unit `fingerprint-fix-sdcp-notify-<version>`, with `--setenv=NOTIFY_TOLD_FILE` (`notified-release`) and `NOTIFY_TOLD_VERSION`, and doesn't write `notified-release` itself on that path;
  - returns True without starting anything while that unit is active;
  - without systemd-run, writes it after a plain notify-send that worked, as before.
- `lib/notify-update.sh`: `told()` writes it when a notification appears:
  - notify-send's `--print-id` output is read every 0.5 s and again after it exits;
  - without `--print-id`, once notify-send returns 0;
  - `plain` notifications `&& told`.

  `wait_notify_send` returns non-zero when no ID was printed, and a first failed notification with buttons falls back to `plain`.
- `lib/notify-dbus.py`: writes `NOTIFY_SHOWN_TEXT` to `NOTIFY_SHOWN_FILE` once `Notify` has returned an ID.
- PLAN.md (`update_check.py` row), CHANGELOG.

## Why
- The same gap Codex found twice in galaxybook-fan (its PRs #55 and #56, which this matches): `systemd-run` returns 0 once the job starts, so `notified-release` was written even when nothing then appeared (no notification service yet, or the notifier stopped at logout), and that release was never announced.

## Tested
- `show_notification` called directly, with fakes for `systemd-run` (runs the notifier with its `--setenv`s), `systemctl --user is-active` and `notify-send`:
  - shown at once: told
  - killed before it appeared: not told
  - killed while on screen: told
  - notify-send failing: not told
  - unit already active: nothing started
  - no systemd-run, working: told
  - no systemd-run, failing: not told, returns False
  - main, for comparison: notify-send failing after systemd-run: told
- `bash -n`, `py_compile lib/*.py`, shellcheck: no new warnings.
- Not here: `notify-dbus.py`'s write against a real GNOME session (only compiled), and a real desktop.

## For the next person
- The installed version's scripts draw the notification, so this takes effect from the release after the one that ships it.
