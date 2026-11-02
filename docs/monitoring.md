# The monitor and boot check

[← Back to the README](../README.md)

Two checks that tell you when something goes wrong: the monitor runs after you log in, and the boot check at every boot.

## The Monitor

A user timer fires 10 seconds after login and starts a root service (allowed by a polkit rule). The service:

- notifies you if the fix's library or drop-in has gone missing;
- when the **distro libfprint changes**, checks whether it now has an SDCP driver for the sensor (`lib/distro-driver-check.py`: it lists USB devices with the distro library, as root — some libfprint builds open the reader while listing it — and fprintd keeps running), and where that library came from: only the distro's own, unmodified libfprint package counts. An SDCP build from another fix — copied over the distro's file (it no longer matches its package's checksum), not owned by any package, or from a COPR, PPA, the AUR or a local package — gets a warning to keep this fix instead, since the next distro update may replace it. If it's the distro's own, you are told once that the fix may no longer be needed, and to try **Test your distro's driver** in the Galaxy Book Fingerprint Manager's menu first. That test switches fprintd to the distro library for a moment and checks one of your enrolled fingers with it, the way login would work without the fix; if it matches, the Manager offers to remove the fix for you. The fix never removes itself;
- notifies you if fprintd cannot see the sensor at all;
- notifies you if fprintd isn't running this fix's driver, naming any other fingerprint fix's fprintd setting that overrides it (added after this fix was installed). Reinstalling the fix moves it aside.

Notifications are written to `/run/samsung-galaxybook/fprint-sdcp-status` and shown by the user check script in your own session.

## Boot-Time Sensor Check

Windows Hello deletes templates it did not create when Windows boots with its fingerprint device enabled, so your Linux fingerprints can vanish from the sensor while their records remain. Without a check, the fingerprint just stops working with no explanation.

At every boot, a small service compares fprintd's records with the templates actually stored on the sensor:

- It runs **before fprintd starts**, so nothing else can use the sensor while it checks, and nothing needs pausing. It runs in parallel with the rest of the boot — only fprintd waits for it, and only for the second or two it takes — so boot is not slower.
- If a fingerprint's template is gone, the login check shows **Fingerprint Removed From Sensor** (once per boot) naming the finger, at the first login after the wipe — before you try to use it.
- It **clears only the dead fingers' records**, so your desktop's fingerprint settings show them as not enrolled and you can simply add them again. Fingerprints still on the sensor are not touched. (Windows normally removes every Linux fingerprint, so in practice that is usually all of them.)
- Cleared records are **moved, not deleted**, to `/var/lib/samsung-galaxybook/removed-fingerprints/<date>/` (the Manager deletes them once it finds their slots really gone). They are useless once the template is gone, but if the check were ever wrong they could be moved back.
- Each Linux install that shared the fingerprint clears its own dead record at its own next boot.
- Fingerprints **enrolled with another driver** (the distro's own egismoc driver, or another non-SDCP build) are not treated as removed: they can never match here, so the login check says so once (**Fingerprints From Another Driver**) and they are left for you to delete and enrol again in the Galaxy Book Fingerprint Manager.
- A fingerprint removed from the sensor can't be brought back by an import or a backup: those only point at its slot, and the slot is what was deleted.

The check is a small Python program (`lib/sensor-check.py`) that uses whichever libfprint drives the reader — this fix's driver, or your distro's once it has SDCP and the driver is removed. It gives up after a few seconds if the sensor does not appear, and never fails the boot. Its output is in `journalctl -u samsung-galaxybook-fprint-sdcp-boot-check`.
