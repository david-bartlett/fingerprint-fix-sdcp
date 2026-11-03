# Use the notification icon's file, not its name

PR #144 · Claude · 2026-11-03

## What changed
- `lib/notify-update.sh` gives the notification the icon's file: the theme's copy, or the one beside the script with only the driver. The name is only the last resort.
- `packaging/files/user-check.sh.in`: the login check's plain notification uses `@MGR_ICON@`.

## Why
- After David removed and reinstalled the Manager on Fedora KDE, the update notification showed a blank icon. `notify-send -i <name>` was blank and `notify-send -i <path>` was fine, so the file was there and only the lookup by name failed. Clearing the icon caches didn't help; restarting Plasma did (`systemctl --user restart plasma-plasmashell.service`).

## Tested
- `notify-update.sh` with a stand-in `notify-send`: the theme's file, the file beside it, and neither.
- `bash -n`, and the rendered `user-check.sh`.
- David ran this branch's `notify-update.sh` on Fedora KDE: it shows the icon. By then Plasma had been restarted, so that shows it works, not that it gets round a blank name.
- Not tested: GNOME, where the notification now gets a `file://` address, as the driver-only one already did.

## For the next person
- `update_check.py`'s fallback `notify-send` still uses the name. It only runs if `notify-update.sh` can't be started.
