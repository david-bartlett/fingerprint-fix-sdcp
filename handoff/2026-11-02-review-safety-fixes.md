# Safety fixes from a code review

PR #135 · Claude · 2026-11-02

## What changed
- `lib/shared_slots.py`: `used_elsewhere()` returns `None` when it can't tell (no EFI partition, `fingerprint-slots.json` unreadable or not version 1); an empty set only when the file is readable, or not made yet on a found EFI partition. `_save()` returns `True` written / `None` unchanged / `False` failed; `merge_backup()` raises `OSError` on a failed write.
- `lib/fingerprint-manager-helper.py`: `do_reset_install` refuses (nothing changed) when `used_elsewhere()` is `None`; `do_restore_slots` turns the `OSError` into a message; `Sensor.__enter__` has the context and listing inside the retry `try`, so fprintd is always started again on failure.
- `tools/export-fingerprint.sh`: `tar -czf -` piped to `runuser -u $USER_NAME`, which saves the file (`umask 077`, `chmod 600`); root no longer writes, `chown`s or `chmod`s it.
- `tools/import-fingerprint.sh`: refuses a link; copies the archive once to `$TMP/.archive.tgz` (made before the checks now) and checks and extracts only that copy. The leading dot keeps it apart from the archive's `<user>/` folder.
- PLAN.md §10 (three rules), README (Reset), CHANGELOG.

## Why
- A Codex review of `8822889` found the first four (export following a link as root, Reset taking an unreadable EFI file as "no other installs", `Sensor` leaving fprintd stopped, restore ignoring a failed write). The import check/extract gap was found while checking them.

## Tested
- Export block as root with a stand-in user: normal (owned by the user, 600), destination a link to a root file (refused, file unchanged), a folder the user can't write (refused), tar failing (refused).
- Import from the copy step to the extract, with the archive swapped for one holding a link to `/etc` straight after the copy: the copy is checked and extracted. The old script, swapped between check and extract, extracted the link. A link as the archive is refused.
- `used_elsewhere` (no EFI, no file, broken, other format, readable), `merge_backup` (written, unchanged, unwritable), and the helper's `Sensor`, `do_reset_install` and `do_restore_slots` with stand-ins.
- `py_compile`, `bash -n`, shellcheck (no new warnings; import has one fewer).
- Not here: the real sensor, the Manager's dialogs, a real EFI partition. David tests on Fedora 45.

## For the next person
- `used_elsewhere()` can now be `None`: any new caller must treat it as "don't clear slots".
