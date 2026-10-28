# Packages

fingerprint-fix-sdcp ships as `.rpm` (Fedora), `.deb` (Ubuntu, Mint, Debian 13 / MX 25) and Arch packages, attached to each GitHub release by `.github/workflows/release-packages.yml`. `install.sh` stays for other distros and for testing.

From 2.0.0 each format builds two packages from one source, with the same version:

| Package | What | Arch |
| --- | --- | --- |
| `fingerprint-fix-sdcp` | the driver: the egismoc SDCP libfprint build, fprintd's drop-in, `fprintd-env.sh`, `other-fix.sh` | x86_64 |
| `galaxybook-fingerprint-manager` | the Manager, its helper and tools, the monitor, boot and login checks (`sensor-check.py`), units, polkit files, menu entry | noarch / all / any |

Either can be installed without the other. The driver *recommends* the Manager of its version (deb `Recommends`, rpm `Recommends`, pacman `optdepends`): installed from a repository, dnf and apt add it unless told not to; from local files, only what is named is installed. Each package turns fingerprint login on at the first install on a computer (`tools/pam-first-install.sh`, a copy in each package; `/var/lib/samsung-galaxybook/fingerprint-login-set-up` records it), so the driver alone gets it too. The Manager takes over files that `fingerprint-fix-sdcp` 1.x owned (deb: `Replaces` / `Breaks: fingerprint-fix-sdcp (<< 2.0.0~)`; rpm and pacman allow the move within one transaction), so 1.x upgrades by installing both.

| Folder / file | What it is |
| --- | --- |
| `files/` + `render.sh` | the scripts, units, polkit files and menu entries, shared with `install.sh` |
| `build-driver.sh` | builds the `DRIVER` commit (egismoc only) — every format |
| `install-files.sh` | puts one package's files (`driver` or `manager`) in its staging folder — every format |
| `make-sources.sh` | source tarballs of this checkout and the driver (rpm, deb) |
| `rpm/` | `.spec` (the driver, with the Manager as a subpackage) and `build.sh` |
| `debian/` | `debian/` folder contents (maintainer scripts per package) and `build.sh` |
| `arch/` | split `PKGBUILD` (this checkout), `PKGBUILD.release.in` (a release), one `.install` per package |

Paths come from `lib/fixpaths.sh` (`package` layout): the driver under `/usr/lib/fingerprint-fix-sdcp`, the Manager under `/usr/lib/galaxybook-fingerprint-manager`; on Fedora their scripts are in `/usr/libexec/<package>`.

## Building one locally

Each build packages this checkout as it is now (tracked and new files) with the tested driver commit, and writes to `packaging/out/`. The version is `VERSION`; give a higher revision (`build.sh 2`, or `pkgrel`) to test an upgrade.

```bash
# Fedora
sudo dnf install rpm-build gcc gcc-c++ meson ninja-build patch glib2-devel libgusb-devel openssl-devel systemd-rpm-macros
bash packaging/rpm/build.sh
sudo dnf install ./packaging/out/*.rpm

# Ubuntu / Mint / Debian 13
sudo apt install build-essential debhelper meson ninja-build patch pkgconf libglib2.0-dev libgusb-dev libssl-dev curl
bash packaging/debian/build.sh
sudo apt install ./packaging/out/*.deb

# Arch / CachyOS
cd packaging/arch && makepkg -si
```

A package is for the release it was built on: its library dependencies come from that system, and Debian / Ubuntu rename library packages between releases (Ubuntu 26.04 renamed `libgusb2` to `libgusb2a`, so a `.deb` built on Debian 13 can't install there). So the release name is in the version — `1.0.1-1~ubuntu26.04`, `1.0.1-1~debian13`, `1.0.1-1.fc45` — and each GitHub release has one per supported release:

| File | For |
| --- | --- |
| `…~ubuntu24.04_amd64.deb` + `…_all.deb` | Ubuntu 24.04, Linux Mint 22 |
| `…~ubuntu26.04_amd64.deb` + `…_all.deb` | Ubuntu 26.04, Linux Mint 27 |
| `…~debian13_amd64.deb` + `…_all.deb` | Debian 13, MX Linux 25 |
| `…fc44.x86_64.rpm` + `…fc44.noarch.rpm` / the same for `fc45` | Fedora 44 / 45 |
| `PKGBUILD`, `fingerprint-fix-sdcp.install`, `galaxybook-fingerprint-manager.install` | Arch, CachyOS, EndeavourOS, … (built with `makepkg -si`; CI builds the package only as a check) |

## What install and removal do

- **Install:** the driver reloads systemd and restarts fprintd (fingerprints work at once); the Manager enables the boot check and every user's login check (from the next boot / login) and stores the distro libfprint's hash for the monitor. On the first install on a system (no `/var/lib/samsung-galaxybook/libfprint-system.sha256` yet), the Manager also turns fingerprint login on with `tools/fingerprint-pam.sh enable` (authselect, pam-auth-update, or the marked sudo / polkit-1 lines on Arch), like `install.sh`; `FPRINT_PAM=0` skips it. Upgrades, later installs and removal leave it as the user set it, on every distro: once a distro's libfprint has SDCP, fingerprint login keeps working without the fix. Enrolling and importing are left to the Manager.
- **Over an `install.sh` copy:** the rpm and deb remove it first with its own cleanups — the driver's, then the Manager's (fingerprints kept). pacman refuses because both own the menu entry — run `sudo bash uninstall.sh` first.
- **Upgrade:** reloads systemd and restarts fprintd; keeps the admin's choice of enabled units.
- **Removing the driver alone:** fprintd goes back to the distro libfprint; the Manager, its checks and fingerprint login stay.
- **Removing both:** as above, and the Manager's units are disabled. Enrolled fingerprints stay (`/var/lib/fprint` and the sensor). Fingerprint login is left as the user set it, on every distro (the Arch sudo / polkit-1 lines too), like `uninstall.sh`. `apt purge` of the Manager also removes this fix's state in `/var/lib/samsung-galaxybook`.

## Testing a package

1. Install it (over an `install.sh` copy, on Fedora / Ubuntu, to test the migration too).
2. `fprintd-list "$USER"`, then `sudo grep fingerprint-fix-sdcp /proc/$(pidof fprintd)/maps` — fprintd uses the driver.
3. `fprintd-verify` matches existing fingerprints.
4. The Manager opens from the app menu; *About* shows the version and driver; the fingerprint-login switch works.
5. `systemctl is-enabled samsung-galaxybook-fprint-sdcp-boot-check.service` and `systemctl --user is-enabled samsung-galaxybook-fprint-sdcp-user-check.timer` say `enabled`.
6. Reboot: `journalctl -b -u samsung-galaxybook-fprint-sdcp-boot-check` shows the check ran.
7. Upgrade to a higher revision: fingerprints still verify.
8. Upgrade from a 1.x package (one `fingerprint-fix-sdcp`) by installing both new packages: the units stay enabled, fingerprints still verify.
9. Remove the driver alone: fprintd no longer maps it; the Manager still opens, says *Driver: your distro's libfprint*, and its boot check still runs.
10. Remove both: `/var/lib/fprint` is still there.
