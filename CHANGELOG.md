# Changelog

## Unreleased

- Packages: `.rpm` (Fedora), `.deb` (Ubuntu, Mint, Debian 13 / MX 25) and Arch, installed under `/usr`; built and attached to each GitHub release automatically, with a PKGBUILD for building from source (`packaging/README.md`)
- Scripts and units that `install.sh` used to write inline are now real files in `packaging/files/`, shared by `install.sh` and the packages; their paths are in `lib/fixpaths.sh`. `install.sh` writes the same files as before
- The Manager, its helper and the export / import tools find the fix whether it was installed by `install.sh` or as a package
- New releases: at login, one notification per newer release on GitHub; in the Fingerprint Manager, an *Update* button with how to update for the way the fix was installed. One check a day shared by both (`lib/update_check.py`); menu → *Check for new versions* turns both off
- Import adds what's missing: fingers you already have are kept and only the missing ones are imported (`--replace` still replaces all); fingers no longer on the sensor are left out instead of refusing the whole file; `--fingers` imports only some. The Manager asks *add the missing ones* or *replace all*, and offers on start-up to import fingers from `~/fingerprint-export.tgz` that this install lacks (once per export file)
- Hints at login, once each, with an *Open Fingerprint Manager* button: enrol a finger (none enrolled yet), or turn on fingerprint login (fingers enrolled but login still asks for the password). The packages show them right after installing too
- Fingerprint login check: commented-out `pam_fprintd` lines no longer count as enabled (Arch status and enable, Debian status)

## 1.0.0 — 2026-10-25

First release as its own repository (previously `extras/fingerprint-fix-sdcp` in Samsung Galaxy Book Fixes).

**Driver:** libfprint-egismoc-sdcp `3b0ee1f` (25 October 2026), which includes the SDCP key-derivation fix for OpenSSL 3.0/3.1 (Ubuntu 24.04 and its derivatives, e.g. Linux Mint 22).

- Builds only the egismoc SDCP driver and points fprintd at it; the distro's libfprint is not replaced
- Each release builds one tested driver commit (`DRIVER`); `VERSION` and the driver commit are recorded at install and shown in the Fingerprint Manager
- Galaxy Book Fingerprint Manager: ten-finger view, test / enrol / remove with right-click menu and Undo, sensor view (optional), export / import, fingerprint login on/off
- Monitor and boot-time check that notice when the sensor loses a fingerprint (e.g. after booting Windows)
- Sharing one enrolment between several Linux installs (export / import)
- Tested on a Galaxy Book 5 Pro 14" (940XHA, `1c7a:05a5`): Fedora 45, Ubuntu 26.04, Linux Mint 22.3 and 27 (beta), MX Linux, CachyOS
