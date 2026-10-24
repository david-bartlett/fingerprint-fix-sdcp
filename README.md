# Fingerprint Fix (egismoc SDCP driver)

Enables fingerprint authentication on Samsung Galaxy Book laptops with an EgisTec SDCP fingerprint sensor. It builds **only the egismoc driver** from [libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp), pinned to a tested commit, and points fprintd at it. **The distro's libfprint is not replaced.**

This is the successor to [`fingerprint-fix`](../fingerprint-fix/), which builds the unmerged `feature/sdcp-v2` branch and installs it over the system libfprint.

## The Problem

These sensors are Windows Hello readers that expect the host to use Microsoft's [Secure Device Connection Protocol](https://github.com/microsoft/SecureDeviceConnectionProtocol/wiki/Secure-Device-Connection-Protocol) (SDCP). Released libfprint has no SDCP support for the egismoc driver, so enrolled prints are not kept or the SDCP handshake fails.

## Where the Code Comes From

| | |
| --- | --- |
| Base | [libfprint-TOD v1.95.2+tod1](https://gitlab.freedesktop.org/3v1n0/libfprint/-/tree/v1.95.2+tod1) — the released shared SDCP core (Benjamin Berg, Joshua Grisham, Marco Trevisan) |
| Driver | Joshua Grisham's Egis SDCP driver from libfprint [MR !547](https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/547) / `feature/sdcp-v2`, ported onto that core by Abdallah Alkanani |
| Extra fixes | Fresh random nonce for every identify, full certificate-chain, attestation and identity-MAC checks, bounds-checked responses, clean failed opens and suspend; Roman2K's longer finger wait for `05a5`; Philip Walsh's ET171 fixes |
| Pinned commit | `c4880d057e80` on branch `egismoc-sdcp` (2026-10-16) — set in `install.sh` (`SDCP_COMMIT`) |

See the upstream [`SDCP.md`](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp/blob/egismoc-sdcp/libfprint/drivers/egismoc/SDCP.md) for the protocol mapping and trust rules.

## Supported Hardware

| USB ID | Galaxy Book Model | Status |
| --- | --- | --- |
| `1c7a:05a5` | Galaxy Book 4 / Book 5 Pro | In the driver's device list; reported working with MR !547 builds. **Not yet confirmed with this exact build** |
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
8. Installs a login-time monitor (see below)

It does **not** delete `/var/lib/fprint`. Deleting fprintd's records by hand leaves the templates on the sensor as orphans.

## Install

```bash
sudo bash install.sh
```

No reboot needed. Then test with `fprintd-verify`, or enrol:

```bash
fprintd-enroll
```

KDE: System Settings → Users → Fingerprint Authentication · GNOME: Settings → System → Users → Fingerprint Login · Mint: Menu → Fingerprints

If `fprintd-verify` never matches, those prints were enrolled with a non-SDCP driver. Delete them — this also frees their slots on the sensor — and enrol again:

```bash
fprintd-delete "$USER" && fprintd-enroll
```

## Uninstall

```bash
sudo bash uninstall.sh
```

It asks whether to delete enrolled fingerprints first (default: keep), while the SDCP driver is still loaded so the templates are removed from the sensor too. Set `DELETE_PRINTS=1` or `DELETE_PRINTS=0` to answer non-interactively. Then it removes the drop-in, the library and the monitor. Nothing needs reinstalling because the distro libfprint was never replaced. PAM fingerprint authentication is left enabled.

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

## Dual-Boot Warning

The sensor has a single template store shared by every OS:

- **Windows** removes templates it did not create when its biometric service starts, so booting Windows with the sensor enabled deletes your Linux enrolments. Disable the fingerprint device in Windows Device Manager if you dual-boot.
- **fprintd** deletes an unknown template when you enrol a finger that matches it, and deletes unknown templates when the sensor is full. Enrolling the same finger in two Linux installs breaks the first one — use a different finger per install, or copy `/var/lib/fprint/<user>/` between installs so they share one template.

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

## Credits

libfprint is LGPL-2.1-or-later. Egis protocol work and SDCP driver: Joshua Grisham. Shared SDCP core: Benjamin Berg, Joshua Grisham, Marco Trevisan. Port and hardening: Abdallah Alkanani. `05a5` finger-wait: Roman2K. ET171 fixes: Philip Walsh.
