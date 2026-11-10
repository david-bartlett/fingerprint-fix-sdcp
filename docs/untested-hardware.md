# Testing on hardware that isn't confirmed

[← Back to the README](../README.md)

How to try the fix on a Galaxy Book that isn't on the [Supported hardware](supported-hardware.md) list, what to check first, and how to undo it.

> [!WARNING]
> **You do this at your own risk.** Nobody has confirmed that the fix works on your model, and the installer's checks are there to stop it being installed where it hasn't been tested. If you turn them off, you're responsible for what happens. The software comes with no warranty, as the [licence](../LICENSE) says.

## Before you start

- **Check the reader:** run `lsusb | grep 1c7a`. The fix only accepts the Egis readers `1c7a:05a5`, `1c7a:05a1` and `1c7a:0582`. If yours is a different reader, the fix can't make it work, so don't force it.
- **Check what's already on the sensor:** if Windows is on the laptop, or another distro uses the reader, the sensor holds their fingerprints. Disable the reader in Windows Device Manager first, as Windows deletes Linux fingerprints from the sensor each time it starts. See [Dual-Boot With Windows](troubleshooting.md#dual-boot-with-windows).
- **Enrol a finger you don't use in Windows Hello:** fprintd deletes a fingerprint it doesn't know about from the sensor when you enrol a finger that matches it.
- **Know how to undo it:** see [Uninstalling](uninstall.md).

## What's refused, and the override

The packages and `install.sh` refuse to install when:

| Check | Packages | `install.sh` |
| --- | --- | --- |
| Not a 64-bit Intel/AMD processor | Refused | Refused |
| A Galaxy Book3 | Refused | Refused |
| An immutable system, such as Fedora Silverblue | Refused | Refused |
| Not a Samsung | Refused | Refused, no override |
| No `05a5`, `05a1` or `0582` reader found | Refused | Refused, no override |

Setting `FPRINT_SDCP_FORCE=1` turns the checks off. It's meant for a Samsung with one of these two readers that the checks refuse, such as a Galaxy Book3:

| Install method | Command |
| --- | --- |
| Fedora | `sudo FPRINT_SDCP_FORCE=1 dnf install ./fingerprint-fix-sdcp-*.rpm ./galaxybook-fingerprint-manager-*.rpm` |
| Ubuntu, Debian, Mint | `sudo FPRINT_SDCP_FORCE=1 apt install ./fingerprint-fix-sdcp_*.deb ./galaxybook-fingerprint-manager_*.deb` |
| Arch-based | `FPRINT_SDCP_FORCE=1 makepkg -si` |
| `install.sh` | `sudo FPRINT_SDCP_FORCE=1 bash install.sh` |

Some models aren't refused at all, though nobody has confirmed them, such as the Galaxy Book2 Pro SE. They install normally, and this page applies to them too.

`install.sh` has a second override, `FORCE=1`, for something else: it installs the fix even when your distro's own libfprint already has an SDCP driver for the sensor. See [How it works](how-it-works.md).

## Checking it works

1. Enrol a finger with the [Galaxy Book Fingerprint Manager](manager.md), or with `fprintd-enroll`.
2. Run `fprintd-verify` and touch the sensor. It should say `verify-match`.
3. Restart the laptop and run `fprintd-verify` again. The fingerprint should still match: if it's gone, the fix isn't keeping fingerprints on your sensor.
4. Try the lock screen and `sudo`.

## If it doesn't work

Uninstall it, as described in [Uninstalling](uninstall.md). Enrolled fingerprints stay on the sensor until they're removed.

## If it works

Please tell us with the [**It works on my laptop / distro**](https://github.com/david-bartlett/fingerprint-fix-sdcp/issues/new?template=works_on.yml) form, including your model (`cat /sys/class/dmi/id/product_name`) and reader. That's how a model gets onto the confirmed list.
