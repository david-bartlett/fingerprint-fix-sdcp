# Use the notification icon's file, not its name

PR #144 · Claude · 2026-11-03

## What changed
- `lib/notify-update.sh` gives the notification the icon's file: the theme's copy, or the one beside the script with only the driver. The name is only the last resort.
- `packaging/files/user-check.sh.in`: the login check's plain notification uses `@MGR_ICON@`.

## Why
- After David removed and reinstalled the Manager on Fedora KDE, the update notification showed a blank icon. `notify-send -i <name>` was blank and `notify-send -i <path>` was fine, so the file was there and only the lookup by name failed.

## Tested
- `notify-update.sh` with a stand-in `notify-send`: the theme's file, the file beside it, and neither.
- `bash -n`, and the rendered `user-check.sh`.
- Not tested: a real notification, on KDE or GNOME. The notification on GNOME now gets a `file://` address, as the driver-only one already did.

## For the next person
- `update_check.py`'s fallback `notify-send` still uses the name. It only runs if `notify-update.sh` can't be started.
