# Install options

[← Back to the README](../README.md)

Other ways to install: Fedora, Ubuntu, Debian and their derivatives, Arch-based distros, only one of the two packages, or with `install.sh`.

## Fedora, Ubuntu, Debian and their derivatives

These get ready-made packages, built for each distro release. In the [latest release](https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest), find your distro in the **Install** table and download its two files: the driver (`fingerprint-fix-sdcp`) and the Galaxy Book Fingerprint Manager (`galaxybook-fingerprint-manager`). Open a terminal in the folder you saved them to (usually Downloads) and run the command. It installs both, and your package manager pulls in what they need.

| Distro | Command |
| --- | --- |
| Fedora 45 | `sudo dnf install ./fingerprint-fix-sdcp-*.fc45.x86_64.rpm ./galaxybook-fingerprint-manager-*.fc45.noarch.rpm` |
| Fedora 44 | `sudo dnf install ./fingerprint-fix-sdcp-*.fc44.x86_64.rpm ./galaxybook-fingerprint-manager-*.fc44.noarch.rpm` |
| Ubuntu 26.04, Linux Mint 27 | `sudo apt install ./fingerprint-fix-sdcp_*ubuntu26.04_amd64.deb ./galaxybook-fingerprint-manager_*ubuntu26.04_all.deb` |
| Ubuntu 24.04, Linux Mint 22, Zorin OS 18 | `sudo apt install ./fingerprint-fix-sdcp_*ubuntu24.04_amd64.deb ./galaxybook-fingerprint-manager_*ubuntu24.04_all.deb` |
| Debian 13, MX Linux 25 | `sudo apt install ./fingerprint-fix-sdcp_*debian13_amd64.deb ./galaxybook-fingerprint-manager_*debian13_all.deb` |

Pick the files that match your distro's release, e.g. the `fc45` files on Fedora 45. The `./` in front is needed so `dnf` and `apt` read the files from the folder instead of looking for packages by name.

Fingerprint login (lock screen, `sudo`, admin prompts) is turned on at the first install, and updates leave it as you set it. To install with it off, put `FPRINT_PAM=0` after `sudo`, e.g. `sudo FPRINT_PAM=0 dnf install ./fingerprint-fix-sdcp-*.rpm ./galaxybook-fingerprint-manager-*.rpm`. See [Fingerprint login](fingerprint-login.md#turning-fingerprint-login-on-or-off).

**Updating:** the new-version notification's **Update now** downloads and installs the new files for you, or run `galaxybook-fingerprint-manager update` (see the README's Updating section). Or download the new files and run the same command again. **Removing:** see the README's Uninstall section.

## Arch-based distros

Arch is rolling, so the fix is built on your laptop against your current libraries rather than downloaded ready-made (the usual way on Arch, as with the AUR). Only the one driver is built, so it takes seconds:

```bash
sudo pacman -S --needed base-devel git
```

Download `PKGBUILD`, `fingerprint-fix-sdcp.install` and `galaxybook-fingerprint-manager.install` from the release into an empty folder, then in that folder run `makepkg -si`. Or, all in one go:

```bash
mkdir -p ~/fingerprint-pkg && cd ~/fingerprint-pkg
curl -L -O https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest/download/PKGBUILD \
     -O https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest/download/fingerprint-fix-sdcp.install \
     -O https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest/download/galaxybook-fingerprint-manager.install
makepkg -si
```

(This works in bash, zsh and fish, CachyOS's default shell.)

`makepkg` installs the build tools it needs, builds the driver commit the release was tested with, and asks for your password to install both packages. **Updating:** the Manager's **Update** fetches the new release's `PKGBUILD` and runs `makepkg -si` in your terminal. With only the driver, **Update now** or `fingerprint-fix-sdcp update` builds and installs just the driver. On 2.11.4 or older, download the new files and follow the steps below.

### Only one package on Arch

Each release has a `PKGBUILD` for each package, as well as the one that builds both. Download the two files, put them in an empty folder, and run the command there:

| Install | Command | Files |
| --- | --- | --- |
| **Only the driver** | `makepkg -si -p PKGBUILD-driver` | `PKGBUILD-driver`, `fingerprint-fix-sdcp.install` |
| **Only the Manager** | `makepkg -si -p PKGBUILD-manager` | `PKGBUILD-manager`, `galaxybook-fingerprint-manager.install` |

The Manager has nothing to compile, so it builds in seconds.

These files start with 2.12.2. For an older release, build both with `makepkg -s` and the `PKGBUILD` above, then install just one with `sudo pacman -U ./fingerprint-fix-sdcp-[0-9]*.pkg.tar.zst`, or `./galaxybook-fingerprint-manager-*.pkg.tar.zst` for the Manager. Those `.pkg.tar.zst` files are the ones `makepkg` has just built on your laptop, as releases don't include any to download.

## Installing only one package

Either package works on its own. Most desktops have their own fingerprint settings for enrolling, so the driver alone may be all you need:

| Install only | What you get | What you don't |
| --- | --- | --- |
| **The driver** (`fingerprint-fix-sdcp`) | Fingerprints work, and fingerprint login is turned on. Enrol in your desktop's settings (GNOME, KDE, Mint's Fingerprints) | The Galaxy Book Fingerprint Manager's window, the monitor (e.g. *your distro now supports the reader*) and the boot check (warns when Windows deletes your fingerprints) |
| **The Galaxy Book Fingerprint Manager** (`galaxybook-fingerprint-manager`) | The window, monitor and checks, using whichever driver fprintd has: for when your distro's own libfprint supports the reader with SDCP | The driver: on a distro without SDCP support the Galaxy Book Fingerprint Manager can't use the reader |

Install just that file, e.g. `sudo dnf install ./fingerprint-fix-sdcp-*.fc45.x86_64.rpm`, `sudo apt install ./galaxybook-fingerprint-manager_*ubuntu26.04_all.deb`, or on Arch, as in [Only one package on Arch](#only-one-package-on-arch). With `install.sh`: `sudo bash install.sh --driver-only` or `--manager-only`. The other part can be added later the same way. The Manager's **Update** updates whatever is installed: both packages, or only the Manager.

Update notifications name what you have. With only the Manager:

<img src="../images/update-notification-manager.png" width="300" alt="Notification: Galaxy Book Fingerprint Manager 2.13.2 is available. You have 2.13.1. Buttons: Update now and What's new">

## Other distros: install.sh

For a distro without a package, or for testing. Needs `git` and an internet connection (the installer downloads and builds the driver):

```bash
git clone https://github.com/david-bartlett/fingerprint-fix-sdcp
cd fingerprint-fix-sdcp
sudo bash install.sh
```

The installer checks your distro, installs the build packages it needs, builds the driver and sets everything up; at the end it offers to open the Manager. It works on Fedora, Debian / Ubuntu and their derivatives (Linux Mint, Zorin, Pop!_OS, MX Linux…) and Arch-based distros. `/etc/samsung-galaxybook-egismoc-sdcp.installed` records the installed version, the driver commit, its date and where it came from. Each release builds one tested driver commit (see [Releases](https://github.com/david-bartlett/fingerprint-fix-sdcp/releases) and [CHANGELOG.md](../CHANGELOG.md)).

**Updating:** in the `fingerprint-fix-sdcp` folder, run `git pull`, then `sudo bash install.sh` again. Enrolled fingerprints are kept.
