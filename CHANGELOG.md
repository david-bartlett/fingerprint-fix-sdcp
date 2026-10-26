# Changelog

## 1.2.0 — 2026-10-26

- `uninstall.sh` always keeps enrolled fingerprints; it no longer offers to delete them (an accidental *y* also wiped the templates on the sensor). Delete fingers in the Fingerprint Manager instead
- `.deb`: removing the package and installing it again turns the boot check and login check back on
- README: installing and removing the packages comes first; `install.sh` for other distros and testing
- Fingerprint Manager: checks for a new version each time it starts (instead of at most once a day). *Update* offers **Download**, which saves the package for this distro and release in Downloads, checks it against GitHub's checksum and shows the command to install it, and **View on GitHub**

## 1.1.2 — 2026-10-26

**Driver:** unchanged, libfprint-egismoc-sdcp `3b0ee1f`.

### Releases

- Packages are built and the GitHub release is made automatically when a version tag is pushed
- Fedora packages build again (they needed `gcc-c++`)
- Arch: no separate debug package in the downloads
- Galaxy Book 4 with the `1c7a:05a1` sensor confirmed working (firmware 9050.1.2.33) on Zorin OS 18.1 (Ubuntu 24.04 base)

### Packages

- `.rpm` (Fedora 44 / 45), `.deb` (Ubuntu 24.04 / 26.04 and Mint, Debian 13 and MX) and Arch, installed under `/usr` — one per distro release, built and attached to each GitHub release automatically, with a PKGBUILD for building from source (`packaging/README.md`)
- Scripts and units that `install.sh` used to write inline are now real files in `packaging/files/`, shared by `install.sh` and the packages; their paths are in `lib/fixpaths.sh`. `install.sh` writes the same files as before
- The Manager, its helper and the export / import tools find the fix whether it was installed by `install.sh` or as a package

### Notifications

- New releases: at login, one notification per newer release on GitHub; in the Fingerprint Manager, an *Update* button with how to update for the way the fix was installed. One check a day shared by both (`lib/update_check.py`); menu → *Check for new versions* turns both off
- Hints at login, once each, with an *Open Fingerprint Manager* button: enrol a finger (none enrolled yet), or turn on fingerprint login (fingers enrolled but login still asks for the password). The packages show them right after installing too

### Fingerprint Manager and tools

- Larger, clearer text in the top card and tips; a › before right-click menu options; more right-click options, and a right-click menu on the Sensor tab
- The Sensor tab recognises templates of fingers removed on this install (shown as that finger, *Removed here*, with *Restore*), and the Sensor list uses the same wording for unknown templates as the cards
- When administrator access is refused, it says so and offers to try again or close
- Import adds what's missing: fingers you already have are kept and only the missing ones are imported (`--replace` still replaces all); fingers no longer on the sensor are left out instead of refusing the whole file; `--fingers` imports only some. The Manager asks *add the missing ones* or *replace all*, and offers on start-up to import fingers from `~/fingerprint-export.tgz` that this install lacks (once per export file)

### Fingerprint login

- Arch: admin dialogs (pkexec, graphical password prompts) take a typed password after at most 10 seconds instead of 30 (`arch-pam.sh`: polkit-1 gets `timeout=10`; package upgrades update existing lines)
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
