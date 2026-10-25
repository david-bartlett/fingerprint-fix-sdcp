# Fingerprint Fix (egismoc SDCP driver)

Enables fingerprint authentication on Samsung Galaxy Book laptops with an EgisTec SDCP fingerprint sensor. It builds **only the egismoc driver** from [libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp), pinned to a tested commit, and points fprintd at it. **The distro's libfprint is not replaced.**

This is the successor to `fingerprint-fix`, which built the unmerged `feature/sdcp-v2` branch and installed it over the system libfprint. That fix has been removed from the repo; it is kept under the [`fingerprint-fix-final`](https://github.com/david-bartlett/samsung-galaxybook-fixes/tree/fingerprint-fix-final/extras/fingerprint-fix) tag. Installing this fix migrates an existing `fingerprint-fix` install automatically.

## The Problem

These sensors are Windows Hello readers that expect the host to use Microsoft's [Secure Device Connection Protocol](https://github.com/microsoft/SecureDeviceConnectionProtocol/wiki/Secure-Device-Connection-Protocol) (SDCP). Released libfprint has no SDCP support for the egismoc driver, so enrolled prints are not kept or the SDCP handshake fails.

## Where the Code Comes From

| | |
| --- | --- |
| Base | [libfprint-TOD v1.95.2+tod1](https://gitlab.freedesktop.org/3v1n0/libfprint/-/tree/v1.95.2+tod1) — the released shared SDCP core (Benjamin Berg, Joshua Grisham, Marco Trevisan) |
| Driver | Joshua Grisham's Egis SDCP driver from libfprint [MR !547](https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/547) / `feature/sdcp-v2`, ported onto that core by Abdallah Alkanani |
| Extra fixes | Fresh random nonce for every identify, full certificate-chain, attestation and identity-MAC checks, bounds-checked responses, clean failed opens and suspend; Roman2K's longer finger wait for `05a5`; Philip Walsh's ET171 fixes |
| Pinned commit | `c4880d057e80` on branch `egismoc-sdcp` (2026-10-16) — set in `install.sh` (`PINNED_COMMIT`); `SDCP_COMMIT=latest` builds the newest commit instead |

See the upstream [`SDCP.md`](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp/blob/egismoc-sdcp/libfprint/drivers/egismoc/SDCP.md) for the protocol mapping and trust rules.

## Supported Hardware

| USB ID | Galaxy Book Model | Status |
| --- | --- | --- |
| `1c7a:05a5` | Galaxy Book 4 / Book 5 Pro | **Confirmed working** on Galaxy Book 5 Pro 14" (940XHA): Fedora 45, Linux Mint 27 (beta), Ubuntu 26.04 and MX Linux (Xfce), 2026-10-24/25 — including an existing enrolment migrated from `fingerprint-fix` without re-enrolling |
| `1c7a:05a1` | Galaxy Book 3 / Book 4 (ETU905A80-E) | Tested upstream with this build (597 logins through `pam_fprintd`) |

Find your reader's ID with `lsusb | grep 1c7a`.

## What This Fix Does

1. Checks the sensor is present
2. Installs build dependencies, fprintd and fprintd's PAM module
3. **Migrates from the old `fingerprint-fix`** if it is installed: removes its monitor and restores the distro libfprint, **keeping enrolled fingerprints** (both builds use the same SDCP on-disk format)
4. Exits without changes if the distro libfprint already handles the sensor (override with `FORCE=1`)
5. Fetches the pinned commit and builds the egismoc driver only (`-Ddrivers=egismoc -Dtod=false`)
6. Installs the library to `/usr/local/lib/libfprint-egismoc-sdcp/` and adds a systemd drop-in so **only fprintd** loads it (`LD_LIBRARY_PATH`)
7. Configures PAM (Fedora: authselect; Ubuntu/Debian/Mint: pam-auth-update; Arch: see below)
8. Installs a login-time monitor and a boot-time sensor check (see below)
9. Offers to import fingerprints exported from another install on this laptop, if `~/fingerprint-export.tgz` exists (see [Sharing Fingerprints](#sharing-fingerprints-between-linux-installs))

It does **not** delete `/var/lib/fprint`. Deleting fprintd's records by hand leaves the templates on the sensor as orphans.

## Install

```bash
sudo bash install.sh
```

This builds the tested, pinned commit. To try the newest upstream commit instead (not tested on Galaxy Books):

```bash
sudo SDCP_COMMIT=latest bash install.sh
```

The installer says when the newest commit is newer than the tested one. To go back, run `sudo bash install.sh` again — enrolled fingerprints are kept either way. `/etc/samsung-galaxybook-egismoc-sdcp.installed` records which commit is installed and whether it was `pinned` or `latest`.

No reboot needed. Then test with `fprintd-verify`, or enrol:

```bash
fprintd-enroll
```

KDE: System Settings → Users → Fingerprint Authentication · GNOME: Settings → System → Users → Fingerprint Login · Mint: Menu → Fingerprints · Xfce (e.g. MX Linux) has no fingerprint settings page — use `fprintd-enroll`, `fprintd-list $USER` and `fprintd-delete $USER` in a terminal

If `fprintd-verify` never matches, those prints were enrolled with a non-SDCP driver. Delete them — this also frees their slots on the sensor — and enrol again:

```bash
fprintd-delete "$USER" && fprintd-enroll
```

## Uninstall

```bash
sudo bash uninstall.sh
```

It asks whether to delete enrolled fingerprints first (default: keep; no answer within 30 seconds also keeps them), while the SDCP driver is still loaded so the templates are removed from the sensor too. Set `DELETE_PRINTS=1` or `DELETE_PRINTS=0` to answer non-interactively. Then it removes the drop-in, the library and the monitor. Nothing needs reinstalling because the distro libfprint was never replaced. PAM fingerprint authentication is left enabled.

To switch it off temporarily instead:

```bash
sudo mv /etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf /root/
sudo systemctl daemon-reload && sudo systemctl restart fprintd
```

## The Monitor

A user timer fires 10 seconds after login and starts a root service (allowed by a polkit rule). The service:

- notifies you if the fix's library or drop-in has gone missing;
- when the **distro libfprint changes**, briefly disables the drop-in and tests the distro library on its own. If it can use the sensor, the fix removes itself and tells you; otherwise the drop-in is restored and nothing is shown. fprintd is unavailable for up to ~10 seconds during this test;
- notifies you if fprintd cannot see the sensor at all.

Notifications are written to `/run/samsung-galaxybook/fprint-sdcp-status` and shown by the user check script in your own session.

## Boot-Time Sensor Check

Windows Hello deletes templates it did not create when Windows boots with its fingerprint device enabled, so your Linux fingerprints can vanish from the sensor while their records remain. Without a check, the fingerprint just stops working with no explanation.

At every boot, a small service compares fprintd's records with the templates actually stored on the sensor:

- It runs **before fprintd starts**, so nothing else can use the sensor while it checks, and nothing needs pausing. It runs in parallel with the rest of the boot — only fprintd waits for it, and only for the second or two it takes — so boot is not slower.
- If a fingerprint's template is gone, the login check shows **Fingerprint Removed From Sensor** (once per boot) naming the finger, at the first login after the wipe — before you try to use it.
- It **clears only the dead fingers' records**, so your desktop's fingerprint settings show them as not enrolled and you can simply add them again. Fingerprints still on the sensor are not touched. (Windows normally removes every Linux fingerprint, so in practice that is usually all of them.)
- Cleared records are **moved, not deleted**, to `/var/lib/samsung-galaxybook/removed-fingerprints/<date>/` (the last 5 are kept). They are useless once the template is gone, but if the check were ever wrong they could be moved back.
- Each Linux install that shared the fingerprint clears its own dead record at its own next boot.
- A removed fingerprint cannot be restored from an export — the export only points at the template on the sensor, and the template is what was deleted.

The check is a small C program (`sensor-check.c`) that the installer builds against the egismoc SDCP library. It gives up after a few seconds if the sensor does not appear, and never fails the boot. Its output is in `journalctl -u samsung-galaxybook-fprint-sdcp-boot-check`.

## Dual-Boot Warning

The sensor has a single template store shared by every OS:

- **Windows** removes templates it did not create when its biometric service starts, so booting Windows with the sensor enabled deletes your Linux enrolments. Disable the fingerprint device in Windows Device Manager if you dual-boot.
- **fprintd** deletes an unknown template when you enrol a finger that matches it, and deletes unknown templates when the sensor is full. Enrolling the same finger in two Linux installs breaks the first one — use a different finger per install, or share one enrolment between installs (below).

## Sharing Fingerprints Between Linux Installs

Several Linux installs on the same laptop can share one enrolment instead of each enrolling the same finger (which would make them delete each other's templates). fprintd's record for a finger holds only the ID of its template on the sensor — no fingerprint image and no secret — so the same record works on every install that runs this fix.

**Tested:** a finger enrolled on Fedora 45, exported and imported on Linux Mint 27 (beta) (via `FPRINT_IMPORT` during install), verified on Mint — and still verified on Fedora afterwards (940XHA, 2026-10-24). Importing for a different username (exported by `dave`, imported for `daveb` on MX Linux) also verified (2026-10-25).

**On the install where the fingers are enrolled:**

```bash
sudo bash export-fingerprint.sh          # writes ~/fingerprint-export.tgz (all your fingers)
```

**On the other install**, copy it to your home folder as `~/fingerprint-export.tgz`. The username there does not have to match — the fingerprints are imported for whoever imports them.

- **While installing the fix:** if `~/fingerprint-export.tgz` exists and you have nothing enrolled, the installer asks `Import them? [Y/n]` (skipped after 30 seconds, or when run without a terminal, e.g. from the GUI app). It does not ask if the file isn't there. `FPRINT_IMPORT=/path/to/file.tgz` imports a file kept anywhere else.
- **With the fix already installed:**

  ```bash
  sudo bash import-fingerprint.sh ~/fingerprint-export.tgz
  sudo bash import-fingerprint.sh --user NAME FILE.tgz      # for another user
  fprintd-verify
  ```

When the username differs from the one that exported them, each record's owner is rewritten for the new user (by the small `sensor-check` helper the installer builds). The template on the sensor is the same either way. Exports made under the older name `fprint-<user>.tgz` import the same way.

The import refuses records made on a different sensor, users who don't exist on this install, and archives containing anything other than fingerprint records. It never overwrites existing fingerprints, because that would orphan their templates on the sensor.

**Once installs share fingerprints:**

- **Do not enrol the same finger on any of them.** fprintd would delete the other installs' template.
- **Answer N to deleting fingerprints when uninstalling** on one of them, or the others lose them too.
- **Export again after deleting or re-enrolling** — an old export points at templates that no longer exist.

## Enabling Fingerprint Authentication on Arch (manual)

Arch does not use authselect or pam-auth-update. Add `auth sufficient pam_fprintd.so` to the top of the auth section of the relevant files.

**sudo** — `/etc/pam.d/sudo`:
```
#%PAM-1.0
auth sufficient pam_fprintd.so
auth include system-auth
account include system-auth
session include system-auth
```

**Login screen** — add `auth sufficient pam_fprintd.so` at the top of the auth section of `/etc/pam.d/system-local-login`.

**KDE lock screen** — `/etc/pam.d/kde-fingerprint`. KDE Plasma 6 has a known bug where `pam_faillock` counts successful fingerprint scans as failures, so use:
```
#%PAM-1.0
auth [success=1 ignore=ignore module_unknown=die default=bad] \
     pam_fprintd.so max-tries=3 timeout=65535
auth [default=die] pam_faillock.so authfail
auth optional pam_permit.so
auth required pam_faillock.so authsucc
auth required pam_env.so
account include system-local-login
password required pam_deny.so
session include system-local-login
```

> ⚠️ Always keep a root terminal open while editing PAM files.

## Security Notes (from upstream)

- The reader's certificate must chain to Microsoft's certificates and carry the Windows Hello biometric key usage; both attestation signatures and every identity MAC are checked.
- Certificate expiry dates are ignored because these readers ship with expired factory certificates. There is no revocation list or firmware denylist.
- The Linux host holds the SDCP session secret. This protects against a spoofed or replayed USB device, but not against a compromised root account.

## Files Installed

- `/usr/local/lib/libfprint-egismoc-sdcp/libfprint-2.so.2` — the egismoc SDCP build
- `/etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf` — makes fprintd load it
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-monitor.sh` — root monitor script
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-user-check.sh` — user login check
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh` — removes the fix once it is no longer needed
- `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-monitor.service`
- `~/.config/systemd/user/samsung-galaxybook-fprint-sdcp-user-check.{service,timer}`
- `/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules`
- `/etc/samsung-galaxybook-egismoc-sdcp.installed` — marker (pinned commit and install date)
- `/var/lib/samsung-galaxybook/libfprint-system.sha256` — distro libfprint hash, to spot updates
- `/usr/local/lib/libfprint-egismoc-sdcp/sensor-check` — boot-time sensor check program
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-boot-check.sh` and `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-boot-check.service` — runs it at boot, before fprintd
- `/run/samsung-galaxybook/fprint-sdcp-boot-status` — boot check result (cleared at every boot)
- `/var/lib/samsung-galaxybook/removed-fingerprints/` — records cleared by the boot check (last 5 boots that cleared any)
- `~/.cache/samsung-galaxybook/fprint-sdcp-boot-shown` — remembers the boot check message was shown this boot

## Credits

libfprint is LGPL-2.1-or-later. Egis protocol work and SDCP driver: Joshua Grisham. Shared SDCP core: Benjamin Berg, Joshua Grisham, Marco Trevisan. Port and hardening: Abdallah Alkanani. `05a5` finger-wait: Roman2K. ET171 fixes: Philip Walsh.
