> [!IMPORTANT]
> **fingerprint-fix-sdcp**: the driver. It makes the fingerprint sensor work on the Samsung Galaxy Book4 and Book5 with the 1c7a:05a1 or 1c7a:05a5 sensor.
>
> **galaxybook-fingerprint-manager**: an app to turn fingerprint for sudo and the lock screen on or off, enrol, test and delete fingerprints, and see which of the sensor's slots are in use. It works with the fingerprint-fix-sdcp driver, or with your distro's own libfprint once that supports the sensor.
>
> Most people want both: download both files for your distro and install them together. Either also works on its own.
>
> **Update notifications:** either one checks for a new release about every hour while you're logged in, and tells you once per version. Turn it on or off in the Fingerprint Manager (☰ → *Check for new versions*). With only the driver installed: `systemctl --user mask fingerprint-fix-sdcp-update-check.timer` (off) or `systemctl --user unmask fingerprint-fix-sdcp-update-check.timer` (on).
>
> **Already have the fix?** Open **Galaxy Book Fingerprint Manager** and press **Update**: it downloads the new files for whatever you have installed. Driver only? Download just the driver's file and install it with the same command, leaving out the Manager's file ([Only one part](https://github.com/david-bartlett/fingerprint-fix-sdcp#only-one-part)).

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
