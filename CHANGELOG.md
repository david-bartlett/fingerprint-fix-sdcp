# Changelog

## Unreleased

- Fingerprint Manager: no lines between the options of the right-click menus
- The distro-driver check now also asks the package manager where the library came from (`rpm`, `dpkg` / `apt-cache`, `pacman`). Only the distro's own, unmodified libfprint package counts as "your distro now supports the reader". An SDCP build from another fix — copied over the distro's file, not owned by any package, or from a COPR, PPA, the AUR or a local package — gets "Another fingerprint fix is installed — keep this fix" from the monitor, the Fingerprint Manager and `install.sh`, and the Manager doesn't offer to remove the fix

## 1.4.0 — 2026-10-26

- When a distro libfprint update brings an SDCP driver for the reader, the monitor says so once and points to the Fingerprint Manager's new **Test your distro's driver** (menu), which checks one of your enrolled fingers with the distro's driver through fprintd — the way login would work without the fix — and gives the remove command if it matches. The Manager also shows this when it opens. The fix no longer removes itself (an `install.sh` copy did, without checking your fingerprints still worked)
- The check for that is new (`lib/distro-driver-check.py`): it asks the distro's libfprint whether its driver for the reader is an SDCP driver, without stopping fprintd or touching the sensor. The monitor used to stop fprintd for up to 10 seconds and test only whether the sensor was listed — which the distro's older, non-SDCP egismoc driver passes on `1c7a:05a1`
- `install.sh` Step 3 uses the same check, so it no longer stops with "probably not needed" on `1c7a:05a1` laptops, where the distro's egismoc driver lists the reader but can't keep prints
- Fingerprint Manager: when Windows is installed on the laptop, a reminder at the bottom of the window to disable the fingerprint reader in Windows (Windows Hello deletes Linux fingerprints when it starts with the reader enabled), with the steps in its tooltip. Found from the UEFI boot entries and Windows' partitions, without a password; **Got it** hides it, *Menu → Remind me about Windows* brings it back
- Fingerprints enrolled with another driver (e.g. the distro's own egismoc driver before this fix, which saves non-SDCP prints) are recognised: the Fingerprint Manager marks them **Other driver** with a warning and a *Delete them* button, and right-click → *Delete and enrol again* deletes the old template from the sensor (freeing its slot) and starts enrolling. They used to show as *Gone from sensor*
- Boot check: no longer moves those fingerprints aside as "removed from the sensor" with a message blaming Windows; the login check says once which fingers were enrolled with another driver

## 1.3.5 — 2026-10-26

- Packages are only for a Samsung with the Galaxy Book's Egis reader (`1c7a:05a5` / `1c7a:05a1`): on other hardware the `.rpm` and `.deb` stop before installing anything, saying why (`FPRINT_SDCP_FORCE=1` installs anyway, e.g. for a system image), and pacman warns
- fprintd uses the fix's driver only while that reader is present: the drop-in checks each time fprintd starts, so on any other hardware (a moved disk, a forced install) fprintd keeps the distro libfprint and its drivers, and other fingerprint readers keep working
- Fingerprint Manager: without that reader, explains that the app is for the Galaxy Book's reader and how to remove the fix, instead of asking for a password and failing
- `install.sh`: the Samsung check also accepts `board_vendor`, like the packages
- Arch-based distros: releases have a `PKGBUILD` (with `fingerprint-fix-sdcp.install`) to build with `makepkg -si`, and no longer a ready-made `.pkg.tar.zst` — built on your laptop against Arch's current libraries, so an Arch library update can't break it between releases. It stops before building on hardware without the Galaxy Book's reader (`FPRINT_SDCP_FORCE=1` builds anyway)
- Fingerprint Manager on Arch-based distros: **Download** fetches the new release's `PKGBUILD` into `~/Downloads/fingerprint-fix-sdcp-<version>/` and gives the `makepkg -si` command. Managers from 1.3.4 and earlier don't find a package in the new release and point to the release page instead

## 1.3.4 — 2026-10-26

- Fingerprint Manager: the hints on both tabs sit in a rounded card like the one above, so their text lines up; on the Sensor tab the slot count, bar and key share it

## 1.3.3 — 2026-10-26

- Fingerprint Manager: the sensor line is labelled — *Sensor · Serial · Driver commit*, with the version at the end
- Fingerprint Manager: clearer hints under the tabs — *Test: double-click · Enrol: click a grey finger · More: right-click*, and on the Sensor tab what green, grey, *Removed here* and dashed mean
- Fingerprint Manager: the fingerprint switch says what it covers on this system — *login, the lock screen and sudo* (GNOME, Mint), *the lock screen and sudo* (KDE, whose login screen can't take fingerprints), or *sudo and admin prompts* (Arch-based); the tooltip has the details
- Fingerprint Manager: shorter Update and Downloaded dialogs — the file to download, then what *Open folder* does and the install command (shown in a fixed-width font); *Open folder* is the default

## 1.3.2 — 2026-10-26

- Fingerprint Manager on Arch: when the fix was installed with `install.sh`, the install command after **Download** removes that copy first (pacman refused to install over its files), keeping fingerprints and fingerprint login
- `install.sh`: the Fingerprint Manager's icon goes in `/usr/share/icons` like its menu entry, so Cinnamon's menu shows it straight away (it didn't notice an icon added under `/usr/local/share/icons` until Cinnamon restarted); the old `/usr/local` copy is removed

## 1.3.1 — 2026-10-26

- Moving from an `install.sh` copy to the `.rpm` or `.deb`: the Manager's icon is no longer shown as a broken image (the old copy's icon cache in `/usr/local` is refreshed — by the package for copies installed before 1.3.1, and by their own cleanup from 1.3.1 on)
## 1.3.0 — 2026-10-26

- `install.sh` no longer looks for or migrates the old `fingerprint-fix` (nobody has it installed); its steps are renumbered
- Fingerprint Manager: notices when a new version is installed while it is open — from a software centre, `dnf` / `apt` / `pacman` or `install.sh` — and offers **Restart**; the download dialog says the file can also be installed by opening it
- Fingerprint Manager: after a download, **Open folder** and **Quit Manager** copy the install command and close the Manager, ready for the new version to be installed; Open folder brings an already open (or minimised) file manager to the front
- Fingerprint Manager: the *Update* button stands out more, with a red ring and a soft glow

## 1.2.1 — 2026-10-26

- README: Credits link to Abdallah Alkanani's libfprint-egismoc-sdcp; "Version built" describes the pinned `DRIVER` commit (it still described building the fork's newest commit)
- Fingerprint Manager and the login notification no longer use GitHub's API, which allows only 60 requests an hour per internet connection without a login (a used-up limit hid new releases). The newest version comes from the releases page, and Download finds and checks the package with the `SHA256SUMS` file now attached to each release

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
