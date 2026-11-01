> [!IMPORTANT]
> **fingerprint-fix-sdcp**: the driver. It makes the fingerprint sensor work on the Samsung Galaxy Book4 and Book5 with the 1c7a:05a1 or 1c7a:05a5 sensor.
>
> **galaxybook-fingerprint-manager**: an app to turn fingerprint for sudo and the lock screen on or off, enrol, test and delete fingerprints, and see which of the sensor's slots are in use. It works with the fingerprint-fix-sdcp driver, or with your distro's own libfprint once that supports the sensor.
>
> The driver is all you need to use the fingerprint reader with your desktop's own fingerprint settings; add the Manager if you want it. Each works on its own; the commands below install both (leave out the Manager's file for the driver alone).
>
> **Already installed?** See **2. Update** below: one command installs this release.

## 1. Install

Open a terminal in the folder you downloaded them to (usually Downloads) and run the command: it installs just these two files.

| Distro | Download these two files | Then run |
| --- | --- | --- |
| **Fedora 45** | `fingerprint-fix-sdcp-@VERSION@-1.fc45.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc45.noarch.rpm` | `sudo dnf install ./fingerprint-fix-sdcp-@VERSION@-*.fc45.x86_64.rpm ./galaxybook-fingerprint-manager-@VERSION@-*.fc45.noarch.rpm` |
| **Fedora 44** | `fingerprint-fix-sdcp-@VERSION@-1.fc44.x86_64.rpm`<br>`galaxybook-fingerprint-manager-@VERSION@-1.fc44.noarch.rpm` | `sudo dnf install ./fingerprint-fix-sdcp-@VERSION@-*.fc44.x86_64.rpm ./galaxybook-fingerprint-manager-@VERSION@-*.fc44.noarch.rpm` |
| **Ubuntu 26.04, Mint 27** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu26.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu26.04_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.ubuntu26.04_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.ubuntu26.04_all.deb` |
| **Ubuntu 24.04, Mint 22, Zorin 18** | `fingerprint-fix-sdcp_@VERSION@-1.ubuntu24.04_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.ubuntu24.04_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.ubuntu24.04_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.ubuntu24.04_all.deb` |
| **Debian 13, MX 25** | `fingerprint-fix-sdcp_@VERSION@-1.debian13_amd64.deb`<br>`galaxybook-fingerprint-manager_@VERSION@-1.debian13_all.deb` | `sudo apt install ./fingerprint-fix-sdcp_@VERSION@-*.debian13_amd64.deb ./galaxybook-fingerprint-manager_@VERSION@-*.debian13_all.deb` |
| **Arch, CachyOS, EndeavourOS** | `PKGBUILD`<br>`fingerprint-fix-sdcp.install`<br>`galaxybook-fingerprint-manager.install` | In a new, empty folder: `makepkg -si` |

## 2. Update

Already have the fix? It looks for new releases by itself, at login and then hourly, and tells you once per version: with the Fingerprint Manager, the notification's **Update now** installs it. To update straight away:

```bash
galaxybook-fingerprint-manager update
```

It downloads this release's files for your distro (both packages, or the `PKGBUILD` on Arch), checks them against `SHA256SUMS` and installs them; no `sudo`: it asks for your fingerprint or password when it installs (2.10.3 or newer). Or open the **Galaxy Book Fingerprint Manager** and press **Update**, or run `galaxybook-fingerprint-manager updates check` to see the notification now.

Driver only? Download just the driver's file and install it with the same command as in **1. Install**, leaving out the Manager's file ([Only one part](https://github.com/david-bartlett/fingerprint-fix-sdcp#only-one-part)).

<details>
<summary>The galaxybook-fingerprint-manager command</summary>

| Command | What it does |
| --- | --- |
| `galaxybook-fingerprint-manager` | Open the Fingerprint Manager window |
| `galaxybook-fingerprint-manager update` | Install the newest release: downloads, checks and installs both packages in this terminal |
| `galaxybook-fingerprint-manager updates on` / `off` | "New version" notifications on or off (the same as the Manager's ☰ → *Check for new versions*) |
| `galaxybook-fingerprint-manager updates status` | Are they on? (checked at login and hourly) |
| `galaxybook-fingerprint-manager updates check` | Look now; if there's a new version, show the notification |

With only the driver installed, turn the notifications off with `systemctl --user mask fingerprint-fix-sdcp-update-check.timer`, and back on with `systemctl --user unmask fingerprint-fix-sdcp-update-check.timer`.

</details>

`SHA256SUMS` lists the files' checksums: `sha256sum -c SHA256SUMS --ignore-missing` in the download folder checks the ones you downloaded.
