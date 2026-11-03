# install.sh writes into a home as that user

PR #154 · Claude · 2026-11-03

## What changed
- `install.sh`: new `_fp_user_file` writes a rendered unit through `runuser`. `_fp_user_timer` makes the folder as the user too, and stops if a write fails. The `chown -R` calls are gone.
- The user-check timer now goes through `_fp_user_timer`, like the two update timers. Its messages are unchanged.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding 1, confirmed on `d57a002`: root's `render … >` followed a link in `~/.config/systemd/user`. A process running as the user could plant a link before someone ran `install.sh`, and root would overwrite the target with a unit file.

## Tested
- The real functions taken from `install.sh`, as root with a real test user, and `render` and systemctl stood in: a fresh home, a link to a root-owned file, `~/.config` linked to a root folder, a root-owned unit file, and no desktop user. The old code overwrote the link's target; the new code leaves it, warns and carries on.
- `bash -n`. `shellcheck` adds one note, SC2016, on the deliberate single quotes.
- Not here: a real `install.sh` run, which needs systemd, a Samsung and the sensor.

## For the next person
- A failed write now gives the existing warning rather than stopping the install. A unit file left owned by root would fail, but `chown -R` on every earlier install means that shouldn't happen.
- Packages aren't affected: they use `systemctl --global`, and write nothing into homes.
