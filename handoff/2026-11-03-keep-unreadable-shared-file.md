# Don't overwrite a shared file that can't be used

PR #NUMBER · Claude · 2026-11-03

## What changed
- `lib/shared_slots.py`: `_unusable()` and `problem_file()` tell a shared file that's there but can't be used from one that's missing. `share_slots()` returns `None` without writing, and `merge_backup()` raises `SharedFileProblem`.
- `share_slots(listed=False)` keeps every entry, for a driver without `STORAGE_LIST`.
- Helper: passes `listed`, adds `shared_problem` to the status, and gives clearer refusals in Reset and restore.
- Manager: `_warn_shared_problem()` shows one warning a run, with what to do under **Details…**.
- `docs/troubleshooting.md`, README's guide table, PLAN.md §10, CHANGELOG.

## Why
- Codex findings 2 and 3, both reproduced on `d57a002`. `_load()` gives `{}` for a bad file, so `share_slots()` replaced it. `used_elsewhere()` then went from `None` to an empty set, undoing PR #135's Reset protection and losing the other installs' records.
- With no `STORAGE_LIST`, the empty template list dropped every entry on the sensor.

## Tested
- With stand-ins for the partition and lsblk: truncated, newer version, empty, no version and non-dict files, each through `share_slots`, `used_elsewhere`, `problem_file`, `merge_backup` and `forget_installs`, with the bytes compared. Also a read error, a missing file, a valid file, `listed` True and False, and a merge into a good file.
- `_warn_shared_problem` with a stand-in window: none, then twice gives one message.
- `py_compile`.
- Not here: the real window, a real EFI partition, `do_status()` itself and the sensor.

## For the next person
- Any new writer of the shared file must check `_unusable()` first.
- `forget_installs()` was already safe: it stops when `_load` gives nothing.
- A file moved aside by hand means `used_elsewhere()` gives an empty set until the other distros have opened the Manager, so the docs say to open it on each distro.
