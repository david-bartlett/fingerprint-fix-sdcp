# User checks: not on the login screen

PR #190 · Claude · 2026-11-25

## What changed
- `ConditionUser=!@system` on all six user units in `packaging/files/`: `user-check`, `fix-update-check` and `mgr-update-check`, each `.timer.in` and `.service.in`.
- PLAN.md (§ *How it works*, a new *Not for system accounts* line), CHANGELOG.

## Why
- galaxybook-fan's PR #62: on CachyOS, after a kernel upgrade, its login check put a polkit password prompt on the login screen. The packages `systemctl --global enable` the user timers, so they also run in the greeter's session (`gdm` / `sddm`, which reaches `graphical-session.target`).
- Here the login check already uses `systemctl start --no-ask-password`, so no prompt, but all three timers still ran as the greeter user. The update check could put a new-version notification on the login screen.

## Tested
- All six rendered units (`render.sh package`) parse with `systemd-analyze verify`.
- The condition itself was tested for galaxybook-fan's #62: skipped for root and for a `useradd -r` system account (like gdm), run for a normal user.
- Not here: a real greeter session.
