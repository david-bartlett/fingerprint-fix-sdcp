## Install

Download **both** files for your distro into an empty folder, then install them together from that folder. The driver (`fingerprint-fix-sdcp`) needs the Fingerprint Manager (`galaxybook-fingerprint-manager`) of the same version, so installing only one of them fails.

| Distro | Files | Install |
| --- | --- | --- |
| Fedora 45 | `fingerprint-fix-sdcp-@VERSION@-*.fc45.x86_64.rpm` and `galaxybook-fingerprint-manager-@VERSION@-*.fc45.noarch.rpm` | `sudo dnf install ./*.fc45.*.rpm` |
| Fedora 44 | `fingerprint-fix-sdcp-@VERSION@-*.fc44.x86_64.rpm` and `galaxybook-fingerprint-manager-@VERSION@-*.fc44.noarch.rpm` | `sudo dnf install ./*.fc44.*.rpm` |
| Ubuntu 26.04, Linux Mint 27 | `fingerprint-fix-sdcp_@VERSION@-*ubuntu26.04_amd64.deb` and `galaxybook-fingerprint-manager_@VERSION@-*ubuntu26.04_all.deb` | `sudo apt install ./*ubuntu26.04_*.deb` |
| Ubuntu 24.04, Linux Mint 22, Zorin OS 18 | `fingerprint-fix-sdcp_@VERSION@-*ubuntu24.04_amd64.deb` and `galaxybook-fingerprint-manager_@VERSION@-*ubuntu24.04_all.deb` | `sudo apt install ./*ubuntu24.04_*.deb` |
| Debian 13, MX Linux 25 | `fingerprint-fix-sdcp_@VERSION@-*debian13_amd64.deb` and `galaxybook-fingerprint-manager_@VERSION@-*debian13_all.deb` | `sudo apt install ./*debian13_*.deb` |
| Arch, CachyOS, EndeavourOS | `PKGBUILD`, `fingerprint-fix-sdcp.install` and `galaxybook-fingerprint-manager.install` | `makepkg -si` (needs `sudo pacman -S --needed base-devel git`) |

Already installed? The Fingerprint Manager's **Update** button downloads the right files for you. Full instructions: [README — Install](https://github.com/david-bartlett/fingerprint-fix-sdcp#install).

## What's new

