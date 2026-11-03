# Using the driver on its own

[← Back to the README](../README.md)

The driver (`fingerprint-fix-sdcp`) is all you need to use the fingerprint reader. This guide is for when you've installed it without the Galaxy Book Fingerprint Manager.

## What you get

| With the driver alone | Only with the Manager |
| --- | --- |
| The reader works, with your desktop's own fingerprint settings | The window to enrol, test and remove fingerprints, and see the sensor's slots |
| Fingerprint login, turned on at the first install | The switch that turns it on or off |
| A notification for each new release, with **Update now** | |
| The `fingerprint-fix-sdcp` command for updates | The `galaxybook-fingerprint-manager` command |
| | The monitor (e.g. *your distro now supports the reader*) |
| | The boot check (warns when Windows deletes your fingerprints) |
| | Fingerprints shared between distros automatically |

To install it, see [Installing only one package](install-options.md#installing-only-one-package).

## Enrolling a fingerprint

Use your desktop's settings. No reboot is needed.

| Desktop | Where |
| --- | --- |
| KDE | System Settings → Users → Fingerprint Authentication |
| GNOME | Settings → System → Users → Fingerprint Login |
| Mint | Menu → Fingerprints |
| Xfce (e.g. MX Linux) | None: use `fprintd-enroll` |

Check it with `fprintd-verify`. If that never matches, those fingers were enrolled with another driver (e.g. your distro's own, before this fix) and can never match here. The Manager finds them, and offers to delete them and enrol them again.

## Turning fingerprint login on or off

This changes your system's login settings, the way each distro expects: `authselect` on Fedora, `pam-auth-update` on Ubuntu, Debian, MX Linux and Mint, and `/etc/pam.d` on Arch-based distros. The driver's package keeps its own copy of the script that does this:

```bash
bash /usr/lib/fingerprint-fix-sdcp/pam/fingerprint-pam.sh status
sudo bash /usr/lib/fingerprint-fix-sdcp/pam/fingerprint-pam.sh enable
sudo bash /usr/lib/fingerprint-fix-sdcp/pam/fingerprint-pam.sh disable    # enrolled fingerprints are kept
```

With an `install.sh` copy, run `tools/fingerprint-pam.sh` from its folder instead. [Fingerprint login](fingerprint-login.md#turning-fingerprint-login-on-or-off) says what it does on each distro.

Fingerprint works at the login screen, the lock screen, `sudo` and admin prompts on every desktop, except that KDE's login screen doesn't support fingerprints yet.

## Updating

You're told about each new release. **Update now** in the notification, or `fingerprint-fix-sdcp update`, installs just the driver. See [With only the driver](../README.md#with-only-the-driver).

## Windows on the same laptop

Disable the fingerprint reader in Windows Device Manager. Otherwise every time Windows starts, it deletes your Linux fingerprints from the sensor.

Without the Manager's boot check, you won't be told when that happens: the fingerprint just stops working with no explanation. See [Dual-Boot With Windows](troubleshooting.md#dual-boot-with-windows).

## Several Linux distros on the laptop

Don't enrol the same finger on each: that deletes it from the others. Share it with an export file instead. See [Without the Manager](multi-distro.md#without-the-manager).

## Removing fingerprints

Don't delete `/var/lib/fprint` records by hand, as that leaves the templates on the sensor as orphans. Don't use `fprintd-delete` to make room either: it deletes the template from the sensor too, which breaks every install sharing it.

## Adding the Manager later

Install the `galaxybook-fingerprint-manager` file the same way as the driver. See [Installing only one package](install-options.md#installing-only-one-package).

## Removing the driver

See [Uninstall](../README.md#uninstall). Enrolled fingerprints are always kept, and fingerprint login stays as you set it.
