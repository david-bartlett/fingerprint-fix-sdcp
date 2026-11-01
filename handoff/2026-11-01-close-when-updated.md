# The new-version notification closes once the new version is installed

PR #132 · Claude · 2026-11-01

## What changed
- `lib/notify-update.sh`: `updated()` compares VERSION (the announced one) with the installed `VERSION` next to `lib/` (`sort -V`); `wait_notify_send` runs `notify-send --print-id …` in the background, notices a click within 0.5 s, and every 2 s, once `updated`, calls `gdbus … CloseNotification ID` once; it prints the button. The D-Bus helper gets `NOTIFY_WATCH_FILE` / `NOTIFY_WATCH_VERSION`.
- `lib/notify-dbus.py`: brought in step with galaxybook-fan's: with those variables, every 2 s it reads the file and closes its own notification once updated.
- CHANGELOG, PLAN.md §4.

## Why
- David on Ubuntu: after updating with the Manager the notification stayed on screen (and its Update now then had nothing to do: #131). galaxybook-fan has the same change (its PR #41).

## Tested
- Stand-ins for `notify-send` (`--print-id`, waits), `gdbus`, Cinnamon: the installed VERSION changed after 3 s → `CloseNotification 42`, ended about 1 s later. shellcheck, `bash -n`, `py_compile`.
- David on Ubuntu 26.04 (GNOME, the D-Bus helper): the notification closed by itself within about 1–2 s of VERSION changing.
- David on Fedora 45 KDE (the notify-send route): closed by itself too, so Plasma allows `CloseNotification` from another connection.
- Not tested yet: Cinnamon, MATE, Xfce (low risk: if one refuses, the notification just stays, as before).
