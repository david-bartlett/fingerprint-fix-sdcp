# Fingerprint Fix for the Samsung Galaxy Book4 and Book5

Makes the fingerprint reader work on Linux on the **Samsung Galaxy Book4 and Book5** (Egis readers `1c7a:05a5` and `1c7a:05a1`): fingerprint login, the lock screen, `sudo` and admin prompts. It adds only the reader's driver, for fprintd alone; **your distro's libfprint is not replaced.**

> [!IMPORTANT]
> - **Only for the Galaxy Book4 and Book5** with an Egis reader: check with `lsusb | grep 1c7a` (`05a5` or `05a1`). Not the Galaxy Book3, nor the ARM-based Book4 Edge: the packages refuse to install there.
> - **Windows on the same laptop?** Disable its fingerprint reader in Windows Device Manager. Otherwise every time Windows starts, it deletes your Linux fingerprints from the sensor.
>
> **There are two packages:**
>
> - **The driver** (`fingerprint-fix-sdcp`) makes the fingerprint reader work on the Galaxy Book4 and Book5 (`1c7a:05a1` or `1c7a:05a5`). It's all you need to use the reader with your desktop's own fingerprint settings.
> - **The [Galaxy Book Fingerprint Manager](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md)** (`galaxybook-fingerprint-manager`) is optional: an app to turn fingerprint login for `sudo` and the lock screen on or off, enrol, test and delete fingerprints, and see which of the sensor's slots are in use. It works with the driver, or with your distro's own libfprint once that supports the reader.
>
> Each works on its own. The install commands below install both; leave out the Manager's file for the driver alone.
>
> The software can also be installed by cloning the repo and running `install.sh`: see [Other distros: install.sh](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/install-options.md#other-distros-installsh).

## Documentation

| Guide | What's in it |
|---|---|
| [Using the driver on its own](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/driver-only.md) | What you get without the Manager, enrolling, fingerprint login, updating, Windows and other distros |
| [Galaxy Book Fingerprint Manager](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md) | The window, its tabs and menu, what slots are, every button |
| [Fingerprint login](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md) | Enrolling, turning fingerprint login on or off, sudo and admin prompts on Arch-based distros |
| [Multi-Distro Mode](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/multi-distro.md) | Sharing fingerprints between distros (enrol a finger once, not on each), reinstalling, reset, back up and restore |
| [Updating](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/updating.md) | The notification, updating with the Manager or only the driver, `install.sh` copies, how the check works |
| [Uninstalling](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/uninstall.md) | Removing both packages or only one, what's kept, switching the driver off temporarily |
| [Supported hardware](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/supported-hardware.md) | Confirmed models and distros, test details by reader, the Galaxy Book3 and Book4 Edge |
| [Install options](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/install-options.md) | Arch-based distros, installing only one package, other distros with `install.sh` |
| [The monitor and boot check](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/monitoring.md) | What the monitor and the boot-time sensor check do, and what they tell you |
| [How it works](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/how-it-works.md) | What installing does, the problem it fixes, where the driver comes from, security notes, every file |
| [Troubleshooting](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/troubleshooting.md) | If the reader says it's already in use, if the shared fingerprint file can't be read, dual-boot with Windows |
| [Testing on hardware that isn't confirmed](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/untested-hardware.md) | Trying the fix on a model that isn't confirmed, at your own risk: what to check first, the `FPRINT_SDCP_FORCE=1` override, and reporting back |

## Install

Each distro has two files in the [**latest release**](https://github.com/david-bartlett/fingerprint-fix-sdcp/releases/latest): the driver and the Manager. Download the files for your distro, open a terminal in that folder and run the command. It installs both; for the driver alone, leave out the Manager's file. On Arch-based distros, use the driver's own `PKGBUILD-driver` instead: see [Only one package on Arch](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/install-options.md#only-one-package-on-arch).

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

Remove both packages with your package manager, or use `uninstall.sh` if you installed with `install.sh`:

```bash
sudo dnf remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Fedora
sudo apt remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Ubuntu, Mint, Debian, MX
sudo pacman -R fingerprint-fix-sdcp galaxybook-fingerprint-manager       # Arch, CachyOS
sudo bash uninstall.sh                                                   # install.sh, from its folder
```

Enrolled fingerprints are always kept, so reinstalling uses them again. To remove only the driver or only the Manager, see [Uninstalling](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/uninstall.md).

## Updating

You're told about each new release with a notification, checked 30 seconds after login and then hourly. Nothing is installed until you choose to: click **Update now**, or run `galaxybook-fingerprint-manager update` in a terminal (`fingerprint-fix-sdcp update` if you only have the driver). Installed with `install.sh`: `git pull`, then `sudo bash install.sh` again. Enrolled fingerprints are always kept. See [Updating](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/updating.md) for the details.

## Supported Hardware

**Confirmed working:** Galaxy Book5 Pro 14" (940XHA, reader `05a5`) on Fedora 45, Ubuntu 26.04, Linux Mint 22.3 and 27, MX Linux 25 and CachyOS; Galaxy Book4 (reader `05a1`) on Zorin OS 18, and Galaxy Book4 Ultra (960XGL, reader `05a1`) on Ubuntu 26.04. Find your reader with `lsusb | grep 1c7a`. The Galaxy Book3 and the ARM-based Galaxy Book4 Edge aren't supported: every install method refuses there. Test details and why: [Supported hardware](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/supported-hardware.md).

Got it working on a model or distro not listed here? Please tell us with the [**It works on my laptop / distro**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=works_on.yml) form — that's how this list grows.

## How it stays safe

- **Your distro's libfprint is not replaced.** Only fprintd loads the fix's driver, and only while the reader is present.
- **Enrolled fingerprints are always kept** when you update or uninstall.
- **Clearing a slot can't be undone.** It erases the fingerprint from the sensor, for every install. See [What's a slot?](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/manager.md).
- **Don't delete `/var/lib/fprint` records by hand,** as that leaves the templates on the sensor as orphans. Don't use `fprintd-delete` to make room either: it deletes the template from the sensor too, which breaks every install sharing it. Use the Manager.
- **Fingerprint login is changed by the fix's own scripts,** which use your distro's own tools and check the result. See [Fingerprint login](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/fingerprint-login.md).

See [How it works](https://github.com/david-bartlett/fingerprint-fix-sdcp/blob/main/docs/how-it-works.md) for the detail.

## Reporting Problems

Use the [**Bug report**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=bug_report.yml) form. It asks for the laptop model, sensor ID, distro, fingerprint-fix-sdcp version and the relevant logs, which usually saves a round of questions. Please check the [existing issues](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues) first.

## Licence

GPL-2.0-or-later — see [LICENSE](LICENSE). The driver it builds, libfprint, is LGPL-2.1-or-later.

## Credits

libfprint is LGPL-2.1-or-later. Egis protocol work and SDCP driver: Joshua Grisham. Shared SDCP core: Benjamin Berg, Joshua Grisham, Marco Trevisan. Port and hardening: Abdallah Alkanani ([abdallah-alkanani/libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp)). `05a5` finger-wait: Roman2K. ET171 fixes: Philip Walsh.
