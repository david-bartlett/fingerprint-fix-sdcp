# GNOME: working notification buttons (notify-dbus.py)

PR #123 · Claude · 2026-10-31

## What changed
- `lib/notify-dbus.py` (new, 755): the same helper as galaxybook-fan's (its PR #32). `URGENCY APP ICON TITLE BODY [KEY LABEL]...`: sends `Notify` over D-Bus with Gio, waits for `ActionInvoked` / `NotificationClosed` for its id, prints the key; exit 2 if it can't (no PyGObject or bus).
- `lib/notify-update.sh`: on GNOME (not Budgie) uses it, critical, with the buttons plus `default` = the first button (the Manager, else GitHub) and a line saying a click does that; exit 2 → the plain notification with the URL. Elsewhere `notify-send --action` as before.
- `lib/notify-open-manager.sh`: the same on GNOME (normal urgency as before; `default` = open the Manager), inside the existing `timeout 3600`.
- Installed beside both scripts: `install-files.sh` (the driver's update folder and the Manager's lib) and `install.sh` (both, and its list of files it needs).
- README (update check details), CHANGELOG, PLAN.md §4.

## Why
- David on Ubuntu 26.04: no buttons on GNOME. galaxybook-fan found why: `notify-send` 0.8.8 prints *Actions are not supported by this notifications server* and drops them, although GNOME lists `actions`, shows buttons when asked over D-Bus, and reported `ActionInvoked` to a Python/Gio test. The new-version notification then also had no link (its text only has it without buttons).

## Tested
- Stand-ins for `notify-send`, `python3`, `xdg-open`, `timeout`, and the Manager launcher (in a scratch copy): GNOME → helper with the right urgency, buttons, `default` and click line, a click opens GitHub / the Manager; helper exit 2 → plain (with the URL for notify-update.sh); KDE / Cinnamon → `notify-send --action` as before. `bash -n`, shellcheck, `py_compile`.
- Not tested here: the real helper on GNOME (galaxybook-fan's identical copy works on David's Ubuntu 26.04).

## For the next person
- Keep `notify-dbus.py` in step with galaxybook-fan's copy.
