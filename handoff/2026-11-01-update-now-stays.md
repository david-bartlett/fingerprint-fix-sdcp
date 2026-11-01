# Update now: the terminal stays open when started from the login notification

PR #128 · Claude · 2026-11-01

## What changed
- `lib/notify-update.sh`: on **Update now**, `exec python3 update_check.py --update-now VERSION URL` (was a child, then `break` and exit).
- `lib/update_check.py` `update_now(version, url)`: `os.execvp` the terminal (was `subprocess.Popen` with `start_new_session`); if none starts, `xdg-open URL`.
- CHANGELOG, PLAN.md §4.

## Why
- David on Fedora KDE, at login: Update now did nothing. The login notification runs in a `systemd-run` service; when its main process (`notify-update.sh`) ended, systemd stopped the whole service, Konsole included (a new session isn't a new cgroup). Our tests ran `notify-update.sh` from a terminal, where nothing stops it. galaxybook-fan does `exec $term`, so its terminal is the service's main process.

## Tested
- `update_now()` with a stand-in terminal: the process is replaced by the terminal command (`--install 2.10.3`). shellcheck, `bash -n`, `py_compile`.
- David on Fedora 45 KDE, run through `systemd-run` as the login check does: Update now opened Konsole and it stayed: both 2.10.4 packages downloaded and checked, then `sudo dnf install` (fingerprint prompt). Before, Konsole closed at once. (A first try failed only because the test steps switched the folder back to `main` while the notification was still up.)
