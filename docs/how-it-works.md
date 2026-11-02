# How it works

[← Back to the README](../README.md)

What installing does, the problem the fix solves, where the driver comes from, and every file it adds.

## What installing does

1. Checks the sensor is present
2. Installs build dependencies, fprintd and fprintd's PAM module
3. Exits without changes if the distro libfprint already has an **SDCP** driver for the sensor (override with `FORCE=1`). The distro's older egismoc driver also claims `1c7a:05a1`, but without SDCP it can't keep prints on these readers, so it doesn't count
4. Fetches the driver commit named in `DRIVER` (the one this release was tested with) from the fork and builds the egismoc driver only (`-Ddrivers=egismoc -Dtod=false`)
5. Installs the library to `/usr/local/lib/libfprint-egismoc-sdcp/` and adds a systemd drop-in so **only fprintd** loads it (`LD_LIBRARY_PATH`), and only while the Galaxy Book's reader is present: each time fprintd starts, the drop-in checks for `1c7a:05a5` / `1c7a:05a1` on USB, so on other hardware fprintd keeps the distro libfprint and its drivers
   - If another fingerprint fix's fprintd setup is found — most often a manual install of [Abdallah's libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp) from its README (`/etc/systemd/system/fprintd.service.d/egismoc-sdcp.conf` and `/usr/local/lib/libfprint-egismoc-sdcp/`), or any admin fprintd drop-in that sets `LD_LIBRARY_PATH` / `LD_PRELOAD` or replaces `ExecStart` — it is **moved aside** first, to `/var/lib/samsung-galaxybook/other-fingerprint-fix/<date>/` with a `RESTORE.txt` saying how to put it back. Fingerprints enrolled with Abdallah's build keep working (it's the same driver). The packages do the same when installed
6. Turns on fingerprint for login and sudo with `fingerprint-pam.sh` (Fedora: authselect; Ubuntu/Debian/MX: pam-auth-update; Mint: its own `fingwit` profile; Arch-based: asks whether to add fingerprint to sudo and polkit — see [Fingerprint for sudo and Admin Prompts on Arch-Based Distros](fingerprint-login.md#fingerprint-for-sudo-and-admin-prompts-on-arch-based-distros))
7. Installs a login-time monitor and a boot-time sensor check (see [The Monitor](monitoring.md#the-monitor) and [Boot-Time Sensor Check](monitoring.md#boot-time-sensor-check))
8. Offers to import fingerprints exported from another install on this laptop, if `~/fingerprint-export.tgz` exists (see [Sharing Fingerprints](multi-distro.md#sharing-fingerprints))
9. Installs the [Galaxy Book Fingerprint Manager](manager.md) and adds it to the app menu, then offers to open it: `Open the Galaxy Book Fingerprint Manager now? [Y/n]` (skipped after 30 seconds, or when there is no terminal or no desktop session; `FPRINT_OPEN_MANAGER=1` or `=0` answers in advance). It opens as you, in your desktop session — never as root

It does **not** delete `/var/lib/fprint`. Deleting fprintd's records by hand leaves the templates on the sensor as orphans.

**With the packages:** The two packages are the driver (`fingerprint-fix-sdcp`) and the [Galaxy Book Fingerprint Manager](manager.md) (`galaxybook-fingerprint-manager`, with the monitor and the boot and login checks). `dnf` and `apt` install what the fix needs from your distro (fprintd, the Manager's GTK libraries…); nothing is compiled on your laptop. Fingerprints work straight away, and on a first install fingerprint login (the lock screen, sudo and admin prompts) is turned on, as `install.sh` does: open **Galaxy Book Fingerprint Manager** from the app menu to enrol a finger. Turn it off there if you prefer, or install with `FPRINT_PAM=0` (e.g. `sudo FPRINT_PAM=0 apt install ./*.deb`). Upgrades and reinstalls keep your choice.

The packages are only for a Samsung with the Egis reader (`1c7a:05a5` / `1c7a:05a1`, see `lsusb | grep 1c7a`): on other hardware the packages and the Arch `PKGBUILD` stop before installing anything (`sudo FPRINT_SDCP_FORCE=1 dnf install …` / `apt install …`, or `FPRINT_SDCP_FORCE=1 makepkg -si`, installs anyway, e.g. for a system image). Either way, fprintd only uses the fix's driver while the reader is present, so another laptop's fingerprint reader keeps working.

- **Already installed with `install.sh`?** The `.rpm` and `.deb` replace it themselves, keeping your fingerprints. On Arch, run `sudo bash uninstall.sh` in the old folder first (pacman won't install over its files).

## The problem this fixes

These sensors are Windows Hello readers that expect the host to use Microsoft's [Secure Device Connection Protocol](https://github.com/microsoft/SecureDeviceConnectionProtocol/wiki/Secure-Device-Connection-Protocol) (SDCP). Released libfprint has no SDCP support for the egismoc driver, so enrolled prints are not kept or the SDCP handshake fails.

## Where the driver comes from

| | |
| --- | --- |
| Base | [libfprint-TOD v1.95.2+tod1](https://gitlab.freedesktop.org/3v1n0/libfprint/-/tree/v1.95.2+tod1) — the released shared SDCP core (Benjamin Berg, Joshua Grisham, Marco Trevisan) |
| Driver | Joshua Grisham's Egis SDCP driver from libfprint [MR !547](https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/547) / `feature/sdcp-v2`, ported onto that core by Abdallah Alkanani |
| Extra fixes | Fresh random nonce for every identify, full certificate-chain, attestation and identity-MAC checks, bounds-checked responses, clean failed opens and suspend; Roman2K's longer finger wait for `05a5`; Philip Walsh's ET171 fixes |
| Source repo | [david-bartlett/libfprint-egismoc-sdcp](https://github.com/david-bartlett/libfprint-egismoc-sdcp), a fork of [abdallah-alkanani/libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp) with its full history and authorship, so new installs don't depend on the original repo staying online |
| Version built | The commit named in the `DRIVER` file — the one each release was tested with (currently `3b0ee1f`, 25 Oct 2026). Syncing the fork changes nothing for users by itself: a new driver commit reaches them only in a new release, after it is tested and put in `DRIVER` |
| Build-time fixes | `lib/patches/*.patch`, applied by the installer to the fetched source **only while the source still needs them** (skipped once the fix is in the source; the install stops if the source has changed so much a fix no longer fits). The installer prints which it applied, and they are recorded in `/etc/samsung-galaxybook-egismoc-sdcp.installed`. Currently one: `0001-close-while-suspended` keeps the reader working when the laptop suspends during a scan |

See the upstream [`SDCP.md`](https://github.com/david-bartlett/libfprint-egismoc-sdcp/blob/egismoc-sdcp/libfprint/drivers/egismoc/SDCP.md) for the protocol mapping and trust rules.

## Security notes (from upstream)

- The reader's certificate must chain to Microsoft's certificates and carry the Windows Hello biometric key usage; both attestation signatures and every identity MAC are checked.
- Certificate expiry dates are ignored because these readers ship with expired factory certificates. There is no revocation list or firmware denylist.
- The Linux host holds the SDCP session secret. This protects against a spoofed or replayed USB device, but not against a compromised root account.

## Files installed

- `/usr/local/lib/libfprint-egismoc-sdcp/libfprint-2.so.2` — the egismoc SDCP build
- `/etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf` — makes fprintd load it
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-fprintd-env.sh` — run by the drop-in each time fprintd starts; writes `/run/samsung-galaxybook/fprintd-sdcp.env` (the library's path, or nothing if the reader isn't present)
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-monitor.sh` — root monitor script
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-user-check.sh` — user login check
- Arch-based, if you said yes: one marked line in `/etc/pam.d/sudo` and `/etc/pam.d/polkit-1` (plus `*.bak-samsung-galaxybook` backups, and `/var/lib/samsung-galaxybook/pam-polkit-1-created` if `polkit-1` was copied)
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh` and `/usr/local/bin/galaxybook-fingerprint-manager-cleanup.sh` — remove the driver and the Galaxy Book Fingerprint Manager of this copy, keeping fingerprints (used by the packages when replacing an `install.sh` copy, and by `uninstall.sh --driver-only` / `--manager-only`)
- `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-monitor.service`
- `~/.config/systemd/user/samsung-galaxybook-fprint-sdcp-user-check.{service,timer}`
- `/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules`
- `/var/lib/samsung-galaxybook/fingerprint-login-set-up` — fingerprint login was turned on (or left alone) at the first install; it isn't turned on again
- `/etc/samsung-galaxybook-egismoc-sdcp.installed` — the driver's marker (commit, its date, source and install date)
- `/etc/galaxybook-fingerprint-manager.installed` — the Manager's marker (version and install date)
- `/var/lib/samsung-galaxybook/libfprint-system.sha256` — distro libfprint hash, to spot updates
- `~/.config/systemd/user/fingerprint-fix-sdcp-update-check.{service,timer}` and `galaxybook-fingerprint-manager-update-check.{service,timer}` — the hourly check for new releases (the driver's and the Manager's; only one runs)
- `/usr/local/lib/libfprint-egismoc-sdcp/update/` — the driver's copy of that check
- `/usr/local/lib/galaxybook-fingerprint-manager/` — Galaxy Book Fingerprint Manager (root-owned copy of `fingerprint-manager.sh`, `lib/` Python files including the boot-time `sensor-check.py`, and `tools/`)
- `/usr/local/bin/galaxybook-fingerprint-manager` — link to start it
- `/usr/share/applications/io.github.david_bartlett.GalaxyBookFingerprintManager.desktop` and `/usr/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg` — its menu entry and icon
- `/usr/share/polkit-1/actions/io.github.david-bartlett.galaxybook-fingerprint-manager.policy` — its password prompt
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-boot-check.sh` and `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-boot-check.service` — runs it at boot, before fprintd
- `/run/samsung-galaxybook/fprint-sdcp-boot-status` — boot check result (cleared at every boot)
- `/run/samsung-galaxybook/fprint-sdcp-other-driver` — fingers enrolled with another driver, found by the boot check
- `/var/lib/samsung-galaxybook/removed-fingerprints/` — records removed in the Manager or cleared by the boot check, kept while they can still be restored
- `/var/lib/samsung-galaxybook/replaced-fingerprints/` — records moved aside by `import-fingerprint.sh --replace`, kept while they can still be restored
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-other-fix.sh` — finds another fingerprint fix's fprintd setup (for the installer and the monitor)
- `/var/lib/samsung-galaxybook/other-fingerprint-fix/<date>/` — another fix's fprintd setup, moved aside at install (only if there was one), with `RESTORE.txt`
- `~/.cache/samsung-galaxybook/fprint-sdcp-boot-shown` — remembers the boot check message was shown this boot
- `~/.cache/samsung-galaxybook/fprint-sdcp-other-driver-shown` — remembers the "Fingerprints From Another Driver" message was shown
- `~/.cache/galaxybook-fingerprint-manager/` — the update check's last answer from GitHub and the last version you were told about
- `EFI/samsung-galaxybook/fingerprint-slots.json` on the EFI system partition (e.g. `/boot/efi` or `/boot`) — each install that runs the Manager (and which partition it's on), what each knows about the sensor's slots, and each slot's fprintd record (an ID and the sensor's signature, never a fingerprint) for the others to import; shared by every install (see [Multi-Distro Mode](multi-distro.md)); removing the Manager takes this install out

## What's in this repository

| | |
| --- | --- |
| `install.sh` / `uninstall.sh` | Install or remove the fix |
| `PLAN.md`, `AGENTS.md`, `handoff/` | How the project works, how to contribute (changes go in as pull requests), and a short note on each pull request |
| `fingerprint-manager.sh` | Starts the [Galaxy Book Fingerprint Manager](manager.md) from the repository folder (the installer also installs it) |
| `tools/` | Optional command-line tools: `export-fingerprint.sh`, `import-fingerprint.sh` ([sharing fingerprints](multi-distro.md#sharing-fingerprints)), `fingerprint-pam.sh` ([fingerprint login on/off](fingerprint-login.md#turning-fingerprint-login-on-or-off)), `arch-pam.sh` (used by it on Arch), `test-latest-libfprint.sh` (try upstream's newest driver; see [packaging/README.md](../packaging/README.md#driver-updates-and-releases)), and `dev/` (sensor debugging scripts) |
| `lib/` | Used by the above — not run directly: the Galaxy Book Fingerprint Manager's Python files and icon, `sensor-check.py` (the boot-time sensor check), `terminal.py` and `update-in-terminal.sh` (the Galaxy Book Fingerprint Manager's **Update** in your terminal), `distro-driver-check.py` (whether the distro's own libfprint now has an SDCP driver for the sensor, and where it came from — see [The Monitor](monitoring.md#the-monitor)), and `patches/` (fixes applied to the driver source at build time) |

Keep the repository folder together: the installer and the Manager use the files in `tools/` and `lib/`.
