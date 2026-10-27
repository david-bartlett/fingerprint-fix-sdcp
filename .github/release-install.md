> [!IMPORTANT]
> **Download both files for your distro and install them together**: the driver and the Fingerprint Manager. The driver won't install without the Manager, so one file on its own isn't enough.
> Already have the fix? Open **Galaxy Book Fingerprint Manager** and press **Update**: it downloads both files for you.

## Install

Put both files in an empty folder, open a terminal there and run the command.

| Distro | Download these two files | Then run |
| --- | --- | --- |
| **Fedora 45** | `fingerprint-fix-sdcp-@VERSION@-1.fc45.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc45.noarch.rpm` | `sudo dnf install ./*.rpm` |
| **Fedora 44** | `fingerprint-fix-sdcp-@VERSION@-1.fc44.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc44.noarch.rpm` | `sudo dnf install ./*.rpm` |
| **Ubuntu 26.04, Mint 27** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu26.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu26.04_all.deb` | `sudo apt install ./*.deb` |
| **Ubuntu 24.04, Mint 22, Zorin 18** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu24.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu24.04_all.deb` | `sudo apt install ./*.deb` |
| **Debian 13, MX 25** | `fingerprint-fix-sdcp_@VERSION@-1.debian13_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.debian13_all.deb` | `sudo apt install ./*.deb` |
| **Arch, CachyOS, EndeavourOS** | `PKGBUILD`<br>`fingerprint-fix-sdcp.install`<br>`galaxybook-fingerprint-manager.install` | `makepkg -si` |

## What's new

