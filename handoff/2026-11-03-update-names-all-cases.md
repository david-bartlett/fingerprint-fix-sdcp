# Update messages say what they'll install

PR #150 · Claude · 2026-11-03

## What changed
- `update_name()` in `lib/update_check.py` now has a name for each case: *Fingerprint Driver*, *Galaxy Book Fingerprint Manager* or *Fingerprint Driver & Manager*. It falls back to `fingerprint-fix-sdcp` if neither marker is there.
- CHANGELOG.

## Why
- After PR #149, the driver alone and both still said the same thing, though the update does different things. This replaces that note's "with both installed the name stays `fingerprint-fix-sdcp`".

## Tested
- `update_name()` with stand-in markers: both, driver only and Manager only, for packages and `install.sh`, and a package Manager with an `install.sh` driver.
- `py_compile`.
- Not here: a real notification or window.

## For the next person
- *Fingerprint Driver & Manager* is treated as one name, so it's "is available", not "are".
- The `&` goes to the notification's title as it is. The title is plain text in the notification spec, but check it on a real desktop.
- `images/update-notification.png` still shows the old wording, so its alt text in README and `docs/driver-only.md` is left matching the picture.
