# Update messages name what's installed

PR #149 · Claude · 2026-11-03

## What changed
- `lib/update_check.py`: new `update_name()`. With only the Manager it's *Galaxy Book Fingerprint Manager*, otherwise `fingerprint-fix-sdcp`. Used in the notification's title, the update terminal's title, and the `update` and `updates check` output.
- `lib/fingerprint-manager.py`: the Update button's tooltip and the update and "has been installed" dialogs use it too.
- CHANGELOG.

## Why
- David found the notification said `fingerprint-fix-sdcp` whichever package was being updated, so someone with only the Manager was told about a package they don't have.

## Tested
- `update_name()` with stand-in markers: both, driver only and Manager only, for packages and `install.sh`, and a package Manager with an `install.sh` driver.
- `py_compile`.
- Not here: a real notification or window.

## For the next person
- It reads the same marker files as `install()`, so deb, rpm, Arch and `install.sh` all work the same way.
- With both installed the name stays `fingerprint-fix-sdcp`, which is also the release's name.
- The About box's "Installed" line is left alone: it describes the driver.
