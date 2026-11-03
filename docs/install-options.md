# Install options

[← Back to the README](../README.md)

Other ways to install: on Arch-based distros, only one of the two packages, or with `install.sh`.

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

### Only the driver on Arch

There's no separate driver download on Arch, as the same `PKGBUILD` always builds both packages, and `makepkg -si` then installs both. For just the driver, build them without installing, then install the driver's:

```bash
makepkg -s
sudo pacman -U ./fingerprint-fix-sdcp-[0-9]*.pkg.tar.zst
```

That `.pkg.tar.zst` file is one `makepkg` has just built on your laptop, in the same folder. The releases don't include one to download.

`makepkg` installs the build tools it needs, builds the driver commit the release was tested with, and asks for your password to install both packages. **Updating:** the Manager's **Update** fetches the new release's `PKGBUILD` and runs `makepkg -si` in your terminal; without the Manager, download the new files and run `makepkg -si` again.

## Installing only one package

Either package works on its own. Most desktops have their own fingerprint settings for enrolling, so the driver alone may be all you need:

| Install only | What you get | What you don't |
| --- | --- | --- |
| **The driver** (`fingerprint-fix-sdcp`) | Fingerprints work, and fingerprint login is turned on. Enrol in your desktop's settings (GNOME, KDE, Mint's Fingerprints) | The Galaxy Book Fingerprint Manager's window, the monitor (e.g. *your distro now supports the reader*) and the boot check (warns when Windows deletes your fingerprints) |
| **The Galaxy Book Fingerprint Manager** (`galaxybook-fingerprint-manager`) | The window, monitor and checks, using whichever driver fprintd has: for when your distro's own libfprint supports the reader with SDCP | The driver: on a distro without SDCP support the Galaxy Book Fingerprint Manager can't use the reader |

Install just that file, e.g. `sudo dnf install ./fingerprint-fix-sdcp-*.fc45.x86_64.rpm`, `sudo apt install ./galaxybook-fingerprint-manager_*ubuntu26.04_all.deb`, or on Arch, as in [Only the driver on Arch](#only-the-driver-on-arch), with the Manager's name for the Manager alone. With `install.sh`: `sudo bash install.sh --driver-only` or `--manager-only`. The other part can be added later the same way. The Manager's **Update** updates whatever is installed: both packages, or only the Manager.

## Other distros: install.sh

For a distro without a package, or for testing. Needs `git` and an internet connection (the installer downloads and builds the driver):

```bash
git clone https://github.com/david-bartlett/fingerprint-fix-sdcp
cd fingerprint-fix-sdcp
sudo bash install.sh
```

The installer checks your distro, installs the build packages it needs, builds the driver and sets everything up; at the end it offers to open the Manager. It works on Fedora, Debian / Ubuntu and their derivatives (Linux Mint, Zorin, Pop!_OS, MX Linux…) and Arch-based distros. `/etc/samsung-galaxybook-egismoc-sdcp.installed` records the installed version, the driver commit, its date and where it came from. Each release builds one tested driver commit (see [Releases](https://github.com/david-bartlett/fingerprint-fix-sdcp/releases) and [CHANGELOG.md](../CHANGELOG.md)).

**Updating:** in the `fingerprint-fix-sdcp` folder, run `git pull`, then `sudo bash install.sh` again. Enrolled fingerprints are kept.
