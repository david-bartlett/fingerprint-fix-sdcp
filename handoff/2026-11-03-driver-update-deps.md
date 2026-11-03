# The driver's package brings in what its updates need

PR #146 · Claude · 2026-11-03

## What changed
- rpm: the driver requires `python3` and `libnotify`, and recommends `xdg-utils` and `python3-gobject`.
- deb: the driver depends on `python3` and `libnotify-bin`, and recommends `xdg-utils` and `python3-gi`.
- Arch, both PKGBUILDs: the driver depends on `python`, `libnotify`, `xdg-utils` and `python-gobject`.
- `install.sh`: `xdg-utils` added to each distro's list.

## Why
- David asked if the fan's dependency fix applied here too. The driver's update check runs Python and its notification uses `notify-send`, but those were only required by the Manager, so a driver-only install relied on them being there.

## Tested
- `bash -n install.sh`, and the PKGBUILD read back in bash.
- Not tested: a real package. This repo's workflow only builds on a tag.

## For the next person
- No code changed. The notification still falls back when `xdg-open` or the GObject bindings are missing.
