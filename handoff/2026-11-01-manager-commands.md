# galaxybook-fingerprint-manager update / updates, and --help as a table

PR #<n> · Claude · 2026-11-01

## What changed
- `fingerprint-manager.sh`: `--help` (and `help`) prints a table of the commands like galaxybook-fan's (80 columns, bold on a terminal; `show_help`); `update` and `updates on|off|status|check` go to `lib/update_check.py` before the desktop checks (they work in any terminal; still refused as root, like the window).
- `lib/update_check.py`: `show_notification(new)` (taken out of `notify_once`, shared with `updates check`), `cmd_update()` (`--update`), `cmd_updates()` (`--updates WHAT`). `install()` and `update-in-terminal.sh` skip the window title and the waits to close when `GBF_OWN_TERMINAL=1`.
- README (Updating), PLAN.md §4, CHANGELOG.
- Built on #124's branch (Update now): merge #124 first.

## Why
- David: fingerprint-fix-sdcp had no command like `galaxybook-fan update` / `updates check`; he chose the same words and the same help layout (mock-up approved).

## Tested
- `cmd_update` / `cmd_updates` with stand-ins: up to date, a new release (`install` with `GBF_OWN_TERMINAL=1`; `check` shows the notification), files not attached yet, offline, on / off / status (`set_enabled`, `enabled`), a wrong word (exit 2).
- `--help`: every line 80 characters, bold only on a terminal. shellcheck (only the existing SC1091 notes), `bash -n`, `py_compile`.
- Not tested here: a real update and the notification from `updates check`.
