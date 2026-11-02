# Fingerprint Fix for the Samsung Galaxy Book4 and Book5

Makes the fingerprint reader work on Linux on the **Samsung Galaxy Book4 and Book5** (Egis readers `1c7a:05a5` and `1c7a:05a1`): fingerprint login, the lock screen, `sudo` and admin prompts. It adds only the reader's driver, for fprintd alone; **your distro's libfprint is not replaced.**

> [!IMPORTANT]
> - **Only for the Galaxy Book4 and Book5** with an Egis reader: check with `lsusb | grep 1c7a` (`05a5` or `05a1`). Not the Galaxy Book3, nor the ARM-based Book4 Edge: the packages refuse to install there.
> - **Windows on the same laptop?** Disable its fingerprint reader in Windows Device Manager. Otherwise every time Windows starts, it deletes your Linux fingerprints from the sensor.
> - **Several Linux distros on the laptop?** Don't enrol the same finger on each: that deletes it from the others. Enrol once and share it: the Galaxy Book Fingerprint Manager offers it on your other distros by itself (see [Multi-Distro Mode](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/multi-distro.md)).

## Documentation

| Guide | What's in it |
|---|---|
| [Using the driver on its own](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/driver-only.md) | What you get without the Manager, enrolling, fingerprint login, updating, Windows and other distros |
| [Galaxy Book Fingerprint Manager](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md) | The window, its tabs and menu, what slots are, every button |
| [Fingerprint login](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md) | Enrolling, turning fingerprint login on or off, sudo and admin prompts on Arch-based distros |
| [Multi-Distro Mode](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/multi-distro.md) | Sharing fingerprints between distros, reinstalling, reset, back up and restore |
| [Install options](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/install-options.md) | Arch-based distros, installing only one package, other distros with `install.sh` |
| [The monitor and boot check](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/monitoring.md) | What the monitor and the boot-time sensor check do, and what they tell you |
| [How it works](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/how-it-works.md) | What installing does, the problem it fixes, where the driver comes from, security notes, every file |
| [Troubleshooting](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/troubleshooting.md) | If the reader says it's already in use, dual-boot with Windows |

## Install

Each distro has two files in the [**latest release**](https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest):

- **The driver** (`fingerprint-fix-sdcp`) makes the reader work. With it alone, enrol in your desktop's own fingerprint settings.
- **The [Galaxy Book Fingerprint Manager](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md)** (`galaxybook-fingerprint-manager`) is **optional**: a window to enrol, test and remove fingerprints, see the sensor's slots and share fingerprints between installs, plus checks that tell you when something goes wrong (e.g. Windows deleted your fingerprints).

Download the files for your distro, open a terminal in that folder and run the command. It installs both; for the driver alone, leave out the Manager's file.

<details>
<summary>Expand for a list of package names for each distro</summary>

| Distro | Command |
| --- | --- |
| Fedora 45 | `sudo dnf install ./fingerprint-fix-sdcp-*.fc45.x86_64.rpm ./galaxybook-fingerprint-manager-*.fc45.noarch.rpm` |
| Fedora 44 | `sudo dnf install ./fingerprint-fix-sdcp-*.fc44.x86_64.rpm ./galaxybook-fingerprint-manager-*.fc44.noarch.rpm` |
| Ubuntu 26.04, Linux Mint 27 | `sudo apt install ./fingerprint-fix-sdcp_*ubuntu26.04_amd64.deb ./galaxybook-fingerprint-manager_*ubuntu26.04_all.deb` |
| Ubuntu 24.04, Linux Mint 22, Zorin OS 18 | `sudo apt install ./fingerprint-fix-sdcp_*ubuntu24.04_amd64.deb ./galaxybook-fingerprint-manager_*ubuntu24.04_all.deb` |
| Debian 13, MX Linux 25 | `sudo apt install ./fingerprint-fix-sdcp_*debian13_amd64.deb ./galaxybook-fingerprint-manager_*debian13_all.deb` |
| Arch, CachyOS, EndeavourOS | see [Arch-based distros](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/install-options.md#arch-based-distros) |

</details>

Fingerprint login (lock screen, `sudo`, admin prompts) is turned on at the first install, and updates leave it as you set it. You can turn it off later in the Manager (see [Turning Fingerprint Login On or Off](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md#turning-fingerprint-login-on-or-off)).

<details>
<summary>Installing with fingerprint login off</summary>

| Distro | Command |
| --- | --- |
| Fedora | `sudo FPRINT_PAM=0 dnf install ./fingerprint-fix-sdcp-*.rpm ./galaxybook-fingerprint-manager-*.rpm` |
| Ubuntu, Linux Mint, Zorin OS, Debian, MX Linux | `sudo FPRINT_PAM=0 apt install ./fingerprint-fix-sdcp_*.deb ./galaxybook-fingerprint-manager_*.deb` |
| Arch, CachyOS, EndeavourOS | `makepkg -s`, then `sudo FPRINT_PAM=0 pacman -U ./*.pkg.tar.zst` (`makepkg -si` ignores `FPRINT_PAM=0`) |
| Any, with install.sh | `sudo FPRINT_PAM=0 bash install.sh` |

</details>

Once installed, **[enrol a fingerprint](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md#enrolling-a-fingerprint)**.

## Uninstall

Installed from a package — remove both with your package manager:

```bash
sudo dnf remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Fedora
sudo apt remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Ubuntu, Mint, Debian, MX
sudo pacman -R fingerprint-fix-sdcp galaxybook-fingerprint-manager       # Arch, CachyOS
```

Installed with `install.sh` — from its folder:

```bash
sudo bash uninstall.sh
```

Enrolled fingerprints are always kept, so reinstalling uses them again, and fingerprint login stays as you set it.

### Removing only one part, and what's kept

**Only the driver** — e.g. once your distro's own libfprint handles the reader with SDCP (the monitor tells you, and the Galaxy Book Fingerprint Manager offers it): `sudo dnf remove fingerprint-fix-sdcp` (or `apt remove` / `pacman -R` the same name), or `sudo bash uninstall.sh --driver-only`. fprintd goes back to your distro's libfprint; the Manager, its checks and fingerprint login stay.

**Only the Manager:** `sudo dnf remove galaxybook-fingerprint-manager` (or `apt remove` / `pacman -R`), or `sudo bash uninstall.sh --manager-only`. The driver, fingerprint login and enrolled fingerprints stay.

Either way, enrolled fingerprints are always kept — fprintd's records and the templates on the sensor — so reinstalling uses them again. To delete fingers, use the Manager before uninstalling (while the driver is still loaded, so the templates leave the sensor too). Both remove the drop-in, the library, the Manager and the monitor; nothing needs reinstalling because the distro libfprint was never replaced. Fingerprint login is left as you set it, on every distro, so it keeps working once your distro's libfprint has SDCP.

To switch an `install.sh` copy off **temporarily** instead:

```bash
sudo mv /etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf /root/
sudo systemctl daemon-reload && sudo systemctl restart fprintd
```

## Fingerprint Manager Updating

You're told about each new release with a notification, checked 30 seconds after login and then hourly. With the Galaxy Book Fingerprint Manager, click the notification's **Update now** (or the Manager's **Update** button): it downloads the new files and installs them in a terminal window, where you confirm with your fingerprint or password. Without it, download the new files and install them the same way. Enrolled fingerprints are always kept.

From a terminal (no `sudo`; `update` asks for your password when it installs):

| Command | What it does |
| --- | --- |
| `galaxybook-fingerprint-manager update` | Install the newest release: downloads, checks and installs both packages in this terminal |
| `galaxybook-fingerprint-manager updates on` / `off` | "New version" notifications on or off (the same as the Manager's switch) |
| `galaxybook-fingerprint-manager updates status` | Are they on? (checked hourly) |
| `galaxybook-fingerprint-manager updates check` | Look now; if there's a new version, show the notification |

`galaxybook-fingerprint-manager --help` lists them all.

<details>
<summary>Turning the update check off, and how it works</summary>

- The notification comes once per version, with **Update now** (with the Manager installed from a package: both packages are downloaded, checked against the release's `SHA256SUMS` and installed together) and **What's new** (the release page; the notification comes back afterwards). On GNOME, hover over it to see the buttons, or click it for **What's new**.
- Only one check runs: the driver's own check is skipped while the Manager is installed.
- A release is only announced once its files are attached, so **Update** always has something to install.
- With no terminal found, the Manager's **Update** saves the files to `~/Downloads` instead, with the command to paste.
- **Turn it off** in the Manager: ☰ → *Check for new versions*, or `galaxybook-fingerprint-manager updates off`. With the driver alone: `systemctl --user mask fingerprint-fix-sdcp-update-check.timer` (off) and `systemctl --user unmask fingerprint-fix-sdcp-update-check.timer` (on); for an `install.sh` copy, `systemctl --user disable` / `enable`.
- Turning it off in the Manager also turns off the driver's check, and that stays off if you remove the Manager; removing it tells you so, with a **Turn on** button.
- `install.sh` copies: in the `fingerprint-fix-sdcp` folder, `git pull`, then `sudo bash install.sh` again.

</details>

**Note:** If only the fingerprint-fix-sdcp driver is installed you will not receive update notifications.  It is suggested that you watch this repo for updates.

## Supported Hardware

**Confirmed working:** Galaxy Book5 Pro 14" (940XHA, reader `05a5`) on Fedora 45, Ubuntu 26.04, Linux Mint 22.3 and 27, MX Linux 25 and CachyOS; Galaxy Book4 (reader `05a1`) on Zorin OS 18. Find your reader with `lsusb | grep 1c7a`.

<details>
<summary>Test details by reader</summary>

| USB ID | Galaxy Book Model | Status |
| --- | --- | --- |
| `1c7a:05a5` | Galaxy Book4 / Book5 Pro | **Confirmed working** on Galaxy Book5 Pro 14" (940XHA): Fedora 45, Linux Mint 27 (beta), Linux Mint 22.3 (OpenSSL 3.0.13 — needs commit 3b0ee1f or later), Ubuntu 26.04, MX Linux (Xfce) and CachyOS (KDE), 2026-10-24/25 |
| `1c7a:05a1` | Galaxy Book4 (ETU905A80-E) | **Confirmed working** on a Galaxy Book4 by [@gabaritei88](https://github.com/gabaritei88) (firmware 9050.1.2.33): Zorin OS 18.1 (Ubuntu 24.04 base, OpenSSL 3.0.13 — needs commit 3b0ee1f or later), driver installed for fprintd only, enrol, verify and PAM login working; the 4 existing Windows Hello templates on the sensor were kept, 2026-10-26. Also tested upstream with this build (597 logins through `pam_fprintd`). On a Galaxy Book4 (960XGL) with Ubuntu 26.04 (libfprint 1.95.1+tod1), Ubuntu's own egismoc driver lists the reader but without SDCP, so it can't keep fingerprints — this fix is needed there too, 2026-10-27 |

</details>

The **Galaxy Book3** can have the `05a1` reader too, but nobody has tested this fix on one, so `install.sh`, the `.rpm`, the `.deb` and the Arch `PKGBUILD` refuse to install there (a Book3 is recognised by its model name, or its model code: the letter after `X` or `Q` is `F` for the Book3, `G` for the Book4 and `H` for the Book5 — e.g. `940XFG`, `960XGL`, `940XHA`). To try it anyway: `FPRINT_SDCP_FORCE=1`. If it works on your Book3, please tell us with the form below.

Only 64-bit Intel/AMD (`x86_64`) Galaxy Books are supported. The ARM-based **Galaxy Book4 Edge** (Snapdragon) isn't: every install method refuses on an ARM processor.

Got it working on a model or distro not listed here? Please tell us with the [**It works on my laptop / distro**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=works_on.yml) form — that's how this list grows.

## How it stays safe

- **Your distro's libfprint is not replaced.** Only fprintd loads the fix's driver, and only while the reader is present.
- **Enrolled fingerprints are always kept** when you update or uninstall.
- **Clearing a slot can't be undone.** It erases the fingerprint from the sensor, for every install. See [What's a slot?](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md).
- **Don't delete `/var/lib/fprint` records by hand,** as that leaves the templates on the sensor as orphans. Don't use `fprintd-delete` to make room either: it deletes the template from the sensor too, which breaks every install sharing it. Use the Manager.
- **Fingerprint login is changed by the fix's own scripts,** which back up and verify what they change. See [Fingerprint login](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md).

See [How it works](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/how-it-works.md) for the detail.

## Reporting Problems

Use the [**Bug report**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=bug_report.yml) form. It asks for the laptop model, sensor ID, distro, fingerprint-fix-sdcp version and the relevant logs, which usually saves a round of questions. Please check the [existing issues](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues) first.

## Licence

GPL-2.0-or-later — see [LICENSE](LICENSE). The driver it builds, libfprint, is LGPL-2.1-or-later.

## Credits

libfprint is LGPL-2.1-or-later. Egis protocol work and SDCP driver: Joshua Grisham. Shared SDCP core: Benjamin Berg, Joshua Grisham, Marco Trevisan. Port and hardening: Abdallah Alkanani ([abdallah-alkanani/libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp)). `05a5` finger-wait: Roman2K. ET171 fixes: Philip Walsh.
