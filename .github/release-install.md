> [!IMPORTANT]
> **Download both files for your distro and install them together**: the driver and the Fingerprint Manager. Most people want both. Either also works on its own: the driver alone (enrol in your desktop's settings), or the Manager alone once your distro's own driver supports the reader.
> Already have the fix? Open **Galaxy Book Fingerprint Manager** and press **Update**: it downloads both files for you.

## Install

Open a terminal in the folder you downloaded them to (usually Downloads) and run the command: it installs just these two files.

| Distro | Download these two files | Then run |
| --- | --- | --- |
| **Fedora 45** | `fingerprint-fix-sdcp-@VERSION@-1.fc45.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc45.noarch.rpm` | `sudo dnf install ./fingerprint-fix-sdcp-@VERSION@-*.fc45.x86_64.rpm ./galaxybook-fingerprint-manager-@VERSION@-*.fc45.noarch.rpm` |
| **Fedora 44** | `fingerprint-fix-sdcp-@VERSION@-1.fc44.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc44.noarch.rpm` | `sudo dnf install ./fingerprint-fix-sdcp-@VERSION@-*.fc44.x86_64.rpm ./galaxybook-fingerprint-manager-@VERSION@-*.fc44.noarch.rpm` |
| **Ubuntu 26.04, Mint 27** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu26.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu26.04_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.ubuntu26.04_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.ubuntu26.04_all.deb` |
| **Ubuntu 24.04, Mint 22, Zorin 18** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu24.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu24.04_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.ubuntu24.04_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.ubuntu24.04_all.deb` |
| **Debian 13, MX 25** | `fingerprint-fix-sdcp_@VERSION@-1.debian13_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.debian13_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.debian13_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.debian13_all.deb` |
| **Arch, CachyOS, EndeavourOS** | `PKGBUILD`<br>`fingerprint-fix-sdcp.install`<br>`galaxybook-fingerprint-manager.install` | In a new, empty folder: `makepkg -si` |
