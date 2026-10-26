# Packages

fingerprint-fix-sdcp ships as an `.rpm` (Fedora), a `.deb` (Ubuntu, Mint, Debian 13 / MX 25) and an Arch package, attached to each GitHub release by `.github/workflows/release-packages.yml`. `install.sh` stays for other distros and for testing.

| Folder / file | What it is |
| --- | --- |
| `files/` + `render.sh` | the scripts, units, polkit files and menu entries, shared with `install.sh` |
| `build-driver.sh` | builds the `DRIVER` commit (egismoc only) and `sensor-check` — every format |
| `install-files.sh` | puts the files in a package's staging folder — every format |
| `make-sources.sh` | source tarballs of this checkout and the driver (rpm, deb) |
| `rpm/` | `.spec` and `build.sh` |
| `debian/` | `debian/` folder contents and `build.sh` |
| `arch/` | `PKGBUILD` (this checkout), `PKGBUILD.release.in` (a release), `.install` |

Paths come from `lib/fixpaths.sh` (`package` layout): everything under `/usr/lib/fingerprint-fix-sdcp`, scripts in `/usr/libexec/fingerprint-fix-sdcp` on Fedora.

## Building one locally

Each build packages this checkout as it is now (tracked and new files) with the tested driver commit, and writes to `packaging/out/`. The version is `VERSION`; give a higher revision (`build.sh 2`, or `pkgrel`) to test an upgrade.

```bash
# Fedora
sudo dnf install rpm-build gcc meson ninja-build patch glib2-devel libgusb-devel openssl-devel systemd-rpm-macros
bash packaging/rpm/build.sh
sudo dnf install ./packaging/out/fingerprint-fix-sdcp-*.rpm

# Ubuntu / Mint / Debian 13
sudo apt install build-essential debhelper meson ninja-build patch pkgconf libglib2.0-dev libgusb-dev libssl-dev curl
bash packaging/debian/build.sh
sudo apt install ./packaging/out/fingerprint-fix-sdcp_*.deb

# Arch / CachyOS
cd packaging/arch && makepkg -si
```

A `.deb` built on Ubuntu 26.04 needs 26.04's libraries; the release one is built on 24.04 so it installs on both.

## What install and removal do

- **Install:** reloads systemd and restarts fprintd (fingerprints work at once); enables the boot check and every user's login check (from the next boot / login); stores the distro libfprint's hash for the monitor. Fingerprint login (PAM), enrolling and importing are left to the Manager.
- **Over an `install.sh` copy:** the rpm and deb remove it first with its own cleanup (fingerprints kept). pacman refuses because both own the menu entry — run `sudo bash uninstall.sh` first.
- **Upgrade:** reloads systemd and restarts fprintd; keeps the admin's choice of enabled units.
- **Removal:** fprintd goes back to the distro libfprint. Enrolled fingerprints stay (`/var/lib/fprint` and the sensor). On Arch the sudo / polkit-1 lines the Manager added are removed (no PAM tool there); on Fedora and Debian fingerprint login is left as the user set it, like `uninstall.sh`. `apt purge` also removes this fix's state in `/var/lib/samsung-galaxybook`.

## Testing a package

1. Install it (over an `install.sh` copy, on Fedora / Ubuntu, to test the migration too).
2. `fprintd-list "$USER"`, then `sudo grep fingerprint-fix-sdcp /proc/$(pidof fprintd)/maps` — fprintd uses the driver.
3. `fprintd-verify` matches existing fingerprints.
4. The Manager opens from the app menu; *About* shows the version and driver; the fingerprint-login switch works.
5. `systemctl is-enabled samsung-galaxybook-fprint-sdcp-boot-check.service` and `systemctl --user is-enabled samsung-galaxybook-fprint-sdcp-user-check.timer` say `enabled`.
6. Reboot: `journalctl -b -u samsung-galaxybook-fprint-sdcp-boot-check` shows the check ran.
7. Upgrade to a higher revision: fingerprints still verify.
8. Remove: `/var/lib/fprint` is still there; fprintd no longer maps the driver.
