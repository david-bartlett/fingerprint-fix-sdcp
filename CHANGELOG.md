# Changelog

## Unreleased

- Arch: admin dialogs (pkexec, graphical password prompts) take a typed password after at most 10 seconds instead of 30 (`arch-pam.sh`: polkit-1 gets `timeout=10`; package upgrades update existing lines)
- Packages: `.rpm` (Fedora 44 / 45), `.deb` (Ubuntu 24.04 / 26.04 and Mint, Debian 13 and MX) and Arch, installed under `/usr` — one per distro release, built and attached to each GitHub release automatically, with a PKGBUILD for building from source (`packaging/README.md`)
- Scripts and units that `install.sh` used to write inline are now real files in `packaging/files/`, shared by `install.sh` and the packages; their paths are in `lib/fixpaths.sh`. `install.sh` writes the same files as before
- The Manager, its helper and the export / import tools find the fix whether it was installed by `install.sh` or as a package
- First login after installing: a notification points to the Galaxy Book Fingerprint Manager when no finger is enrolled yet
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
