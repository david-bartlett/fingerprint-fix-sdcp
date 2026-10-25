# Fingerprint Fix (egismoc SDCP driver)

Enables fingerprint authentication on Samsung Galaxy Book laptops with an EgisTec SDCP fingerprint sensor. It builds **only the egismoc driver** from [libfprint-egismoc-sdcp](https://github.com/david-bartlett/libfprint-egismoc-sdcp) (a fork of [Abdallah Alkanani's repo](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp)), and points fprintd at it. **The distro's libfprint is not replaced.**

This is the successor to `fingerprint-fix`, which built the unmerged `feature/sdcp-v2` branch and installed it over the system libfprint. That fix has been removed from the repo; it is kept under the [`fingerprint-fix-final`](https://github.com/david-bartlett/samsung-galaxybook-fixes/tree/fingerprint-fix-final/extras/fingerprint-fix) tag. Installing this fix migrates an existing `fingerprint-fix` install automatically.

## What's in This Folder

| | |
| --- | --- |
| `install.sh` / `uninstall.sh` | Install or remove the fix |
| `fingerprint-manager.sh` | Starts the [Galaxy Book Fingerprint Manager](#galaxy-book-fingerprint-manager) from this folder (the installer also installs it) |
| `tools/` | Optional command-line tools: `export-fingerprint.sh`, `import-fingerprint.sh` ([sharing fingerprints](#sharing-fingerprints-between-linux-installs)), `fingerprint-pam.sh` ([fingerprint login on/off](#turning-fingerprint-login-on-or-off)), `arch-pam.sh` (used by it on Arch) |
| `lib/` | Used by the above — not run directly: the Fingerprint Manager's Python files and icon, `sensor-check.c`, and `patches/` (fixes applied to the driver source at build time) |

Keep the folder together: the installer and the Fingerprint Manager use the files in `tools/` and `lib/`.

## The Problem

These sensors are Windows Hello readers that expect the host to use Microsoft's [Secure Device Connection Protocol](https://github.com/microsoft/SecureDeviceConnectionProtocol/wiki/Secure-Device-Connection-Protocol) (SDCP). Released libfprint has no SDCP support for the egismoc driver, so enrolled prints are not kept or the SDCP handshake fails.

## Where the Code Comes From

| | |
| --- | --- |
| Base | [libfprint-TOD v1.95.2+tod1](https://gitlab.freedesktop.org/3v1n0/libfprint/-/tree/v1.95.2+tod1) — the released shared SDCP core (Benjamin Berg, Joshua Grisham, Marco Trevisan) |
| Driver | Joshua Grisham's Egis SDCP driver from libfprint [MR !547](https://gitlab.freedesktop.org/libfprint/libfprint/-/merge_requests/547) / `feature/sdcp-v2`, ported onto that core by Abdallah Alkanani |
| Extra fixes | Fresh random nonce for every identify, full certificate-chain, attestation and identity-MAC checks, bounds-checked responses, clean failed opens and suspend; Roman2K's longer finger wait for `05a5`; Philip Walsh's ET171 fixes |
| Source repo | [david-bartlett/libfprint-egismoc-sdcp](https://github.com/david-bartlett/libfprint-egismoc-sdcp), a fork of [abdallah-alkanani/libfprint-egismoc-sdcp](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp) with its full history and authorship, so new installs don't depend on the original repo staying online |
| Version built | The newest commit of branch `egismoc-sdcp` **in the fork**. The fork is the release channel: updating it (**Sync fork** on GitHub) is how a new version reaches users. Currently `c4880d057e80` (2026-10-16) |
| Build-time fixes | `lib/patches/*.patch`, applied by the installer to the fetched source **only while the source still needs them** (skipped once the fix is in the source; the install stops if the source has changed so much a fix no longer fits). The installer prints which it applied, and they are recorded in `/etc/samsung-galaxybook-egismoc-sdcp.installed`. Currently: `sdcp-kdf-openssl30` — on OpenSSL 3.0/3.1 (e.g. Ubuntu 24.04, Linux Mint 22, Zorin 17/18, Pop!_OS 24.04, Debian 12 / MX Linux 23) the SDCP key derivation dropped half its input, so every connection failed with "SDCP ConnectResponse claim validation failed". No change on OpenSSL 3.2+. **Confirmed on hardware** (940XHA, 2026-10-25): on Linux Mint 22.3 (OpenSSL 3.0.13) the sensor fails with that error without the fix, and connects and verifies with it. **Now upstream** in Abdallah's `egismoc-sdcp` branch ([3b0ee1f](https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp/commit/3b0ee1f40fececc78ca44b218ea094390df6f58a), written slightly differently); the installer recognises that and skips the patch once the fork has it |

See the upstream [`SDCP.md`](https://github.com/david-bartlett/libfprint-egismoc-sdcp/blob/egismoc-sdcp/libfprint/drivers/egismoc/SDCP.md) for the protocol mapping and trust rules.

## Supported Hardware

| USB ID | Galaxy Book Model | Status |
| --- | --- | --- |
| `1c7a:05a5` | Galaxy Book 4 / Book 5 Pro | **Confirmed working** on Galaxy Book 5 Pro 14" (940XHA): Fedora 45, Linux Mint 27 (beta), Linux Mint 22.3 (OpenSSL 3.0.13 — with the build-time fix, see above), Ubuntu 26.04, MX Linux (Xfce) and CachyOS (KDE), 2026-10-24/25 — including an existing enrolment migrated from `fingerprint-fix` without re-enrolling |
| `1c7a:05a1` | Galaxy Book 3 / Book 4 (ETU905A80-E) | Tested upstream with this build (597 logins through `pam_fprintd`) |

Find your reader's ID with `lsusb | grep 1c7a`.

## What This Fix Does

1. Checks the sensor is present
2. Installs build dependencies, fprintd and fprintd's PAM module
3. **Migrates from the old `fingerprint-fix`** if it is installed: removes its monitor and restores the distro libfprint, **keeping enrolled fingerprints** (both builds use the same SDCP on-disk format)
4. Exits without changes if the distro libfprint already handles the sensor (override with `FORCE=1`)
5. Fetches the newest commit of `egismoc-sdcp` from the fork and builds the egismoc driver only (`-Ddrivers=egismoc -Dtod=false`)
6. Installs the library to `/usr/local/lib/libfprint-egismoc-sdcp/` and adds a systemd drop-in so **only fprintd** loads it (`LD_LIBRARY_PATH`)
7. Turns on fingerprint for login and sudo with `fingerprint-pam.sh` (Fedora: authselect; Ubuntu/Debian/MX: pam-auth-update; Mint: its own `fingwit` profile; Arch-based: asks whether to add fingerprint to sudo and polkit — see below)
8. Installs a login-time monitor and a boot-time sensor check (see below)
9. Offers to import fingerprints exported from another install on this laptop, if `~/fingerprint-export.tgz` exists (see [Sharing Fingerprints](#sharing-fingerprints-between-linux-installs))
10. Installs the [Galaxy Book Fingerprint Manager](#galaxy-book-fingerprint-manager) and adds it to the app menu, then offers to open it: `Open the Galaxy Book Fingerprint Manager now? [Y/n]` (skipped after 30 seconds, or when there is no terminal or no desktop session; `FPRINT_OPEN_MANAGER=1` or `=0` answers in advance). It opens as you, in your desktop session — never as root

It does **not** delete `/var/lib/fprint`. Deleting fprintd's records by hand leaves the templates on the sensor as orphans.

## Install

```bash
sudo bash install.sh
```

This builds whatever the fork currently holds. `/etc/samsung-galaxybook-egismoc-sdcp.installed` records the commit, its date and where it came from.

**Updating the fork (maintainer):** test the original repo's newest commit on your own laptop *before* clicking **Sync fork**, because syncing publishes it to everyone:

```bash
sudo SDCP_REPO_URL=https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp.git bash install.sh
```

If it works, sync the fork. Either way, `sudo bash install.sh` puts you back on the fork's version — enrolled fingerprints are kept. `SDCP_REPO_URL` only accepts `https://github.com/OWNER/REPO` addresses.

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

The check is a small C program (`lib/sensor-check.c`) that the installer builds against the egismoc SDCP library. It gives up after a few seconds if the sensor does not appear, and never fails the boot. Its output is in `journalctl -u samsung-galaxybook-fprint-sdcp-boot-check`.

## Dual-Boot Warning

The sensor has a single template store shared by every OS:

- **Windows** removes templates it did not create when its biometric service starts, so booting Windows with the sensor enabled deletes your Linux enrolments. Disable the fingerprint device in Windows Device Manager if you dual-boot.
- **fprintd** deletes an unknown template when you enrol a finger that matches it, and deletes unknown templates when the sensor is full. Enrolling the same finger in two Linux installs breaks the first one — use a different finger per install, or share one enrolment between installs (below).

## Sharing Fingerprints Between Linux Installs

Several Linux installs on the same laptop can share one enrolment instead of each enrolling the same finger (which would make them delete each other's templates). fprintd's record for a finger holds only the ID of its template on the sensor — no fingerprint image and no secret — so the same record works on every install that runs this fix.

**Tested:** a finger enrolled on Fedora 45, exported and imported on Linux Mint 27 (beta) (via `FPRINT_IMPORT` during install), verified on Mint — and still verified on Fedora afterwards (940XHA, 2026-10-24). Importing for a different username (exported by `dave`, imported for `daveb` on MX Linux) also verified (2026-10-25).

**On the install where the fingers are enrolled:**

```bash
sudo bash tools/export-fingerprint.sh          # writes ~/fingerprint-export.tgz (all your fingers)
```

**On the other install**, copy it to your home folder as `~/fingerprint-export.tgz`. The username there does not have to match — the fingerprints are imported for whoever imports them.

- **While installing the fix** (only when you have nothing enrolled on this install):
  - if `~/fingerprint-export.tgz` exists, it is **imported automatically**;
  - otherwise the installer asks `Do you have fingerprints exported from another install to import? [y/N]` (skipped after 30 seconds, or when run without a terminal, e.g. from the GUI app). Answer `y` and it asks for the path, with no time limit;
  - `FPRINT_IMPORT=/path/to/file.tgz` imports a file kept anywhere else without asking.
- **Before importing**, the fingerprints are checked against the sensor (fprintd is paused for a moment). An out-of-date export — made before re-enrolling, or before Windows wiped the sensor — is refused, so you never end up with a fingerprint that can't match. `--no-check` skips this.
- **With the fix already installed:**

  ```bash
  sudo bash tools/import-fingerprint.sh                           # uses ~/fingerprint-export.tgz
  sudo bash tools/import-fingerprint.sh /path/to/file.tgz         # a file kept elsewhere
  sudo bash tools/import-fingerprint.sh --user NAME               # for another user (their ~/fingerprint-export.tgz)
  sudo bash tools/import-fingerprint.sh --replace                 # replace fingerprints already on this install
  fprintd-verify
  ```

When the username differs from the one that exported them, each record's owner is rewritten for the new user (by the small `sensor-check` helper the installer builds). The template on the sensor is the same either way. Exports made under the older name `fprint-<user>.tgz` import the same way.

The import refuses records made on a different sensor, users who don't exist on this install, and archives containing anything other than fingerprint records. If the user already has fingerprints on this install it stops and changes nothing; `--replace` replaces them instead, after all the checks have passed. The old records are moved to `/var/lib/samsung-galaxybook/replaced-fingerprints/<date>/` (the last 5 are kept), and nothing is deleted from the sensor, so other installs sharing those fingerprints keep working. Don't use `fprintd-delete` to make room for an import — it deletes the fingerprints from the sensor too, breaking every install that shares them.

**Once installs share fingerprints:**

- **Do not enrol the same finger on any of them.** fprintd would delete the other installs' template.
- **Answer N to deleting fingerprints when uninstalling** on one of them, or the others lose them too.
- **Export again after deleting or re-enrolling** — an old export points at templates that no longer exist.

## Galaxy Book Fingerprint Manager

A small window for looking after the fingerprints on the sensor. The installer installs it for every user: open **Galaxy Book Fingerprint Manager** from the app menu (its description says it comes from Samsung Galaxy Book Fixes), or run:

```bash
galaxybook-fingerprint-manager           # as yourself, not with sudo
./fingerprint-manager.sh                 # or straight from this folder (e.g. while developing)
```

<p>
  <img src="images/fingerprint-manager.png" width="400" alt="Galaxy Book Fingerprint Manager: all ten fingers, four enrolled, with the right-click menu (Test, Remove from Fedora) open">
  <img src="images/fingerprint-manager-enrol.png" width="400" alt="Enrolling a finger: Lift and touch again, 3 of 5 touches">
</p>

Only one window runs at a time: starting it again brings the open window forward (or makes it flash in the taskbar, depending on the desktop). The installed copy is owned by root (`/usr/local/lib/libfprint-egismoc-sdcp/manager/`), because its helper runs as root: a copy in your home folder could be changed by any program running as you. ☰ → **About** shows where it came from and the fix build.

It asks for your password once per session; the prompt says "Galaxy Book Fingerprint Manager needs administrator access to read and manage the fingerprint sensor" (a polkit policy installed for the helper). At the top is a **Use fingerprint for login and sudo** switch and a line about the sensor and the fix build; below are two tabs:

- **Fingerprints** — your enrolled fingers on this install, and whether the sensor still has each one, as **cards** (all ten of your fingers, right hand then left, like Linux Mint's fingerprint settings; grey dashed = not enrolled, click one to enrol that finger) or as a **list** (a row per enrolled finger, for every user, with its own Test button; other users' fingers are only in the list). The buttons at the top right switch between them (on both tabs), and the choice is remembered. Click a card or row to select it (one at a time, on both tabs) and click it again to deselect it. Double-click one of your fingers to test it. Right-click a finger for a menu: **Test** and **Remove from <distro>** (e.g. "Remove from Fedora", the name from /etc/os-release), or for a red (dead) finger **Remove dead record…** and **Enrol this finger again…** (removes the dead record, then enrols that finger). Green = on the sensor; red = a dead record (its template was re-enrolled elsewhere or removed by Windows), which also shows a warning with a **Remove dead records** button.
- **Sensor** (hidden by default — turn it on with ☰ → **Show the Sensor tab (advanced)**; the choice is remembered) — how many of the sensor's 10 slots are used, and every template on it: green = used by this install (with the user and finger), grey = not used here, labelled "Another distro?" (usually another distro on the same laptop; it can also be Windows Hello's own templates — Windows wipes Linux's templates but keeps its own — or ones left over from a reinstall. One install can't tell which, so they are never deleted without a warning), dashed = free. Shown as cards or a list, like the Fingerprints tab; the Cards / List choice applies to both tabs.

| Where | Control | What it does |
|---|---|---|
| Top | Use fingerprint for login and sudo | Turns PAM fingerprint on or off with `fingerprint-pam.sh` (see below). Turning it off keeps your enrolled fingerprints |
| Fingerprints | Test all fingerprints (or double-click a finger) | The button checks your touch against all your fingers (as login and sudo do); double-clicking a finger tests just that one. Shows a clear Match / No match with the finger that matched. It asks the sensor directly (fprintd pauses for a moment), because fprintd doesn't report which finger matched |
| Fingerprints | Enrol a finger (a grey card, or the last row) | Enrols a new finger for you with `fprintd-enroll`, with a progress bar. It warns first that enrolling a finger already stored for another install or Windows Hello deletes it from there — useful on desktops without a fingerprint settings page, such as Xfce (MX Linux) |
| Fingerprints | Remove from <distro> (right-click a finger, or select it and press Delete) | Moves the record off this install; the template stays, so installs sharing it keep working |
| Sensor | Delete… | Deletes the selected templates from the sensor (and moves aside any record here that used them) |
| Sensor | Wipe sensor… | Deletes every template on the sensor (every Linux install and Windows Hello) after you type WIPE; moves every record here aside |
| ☰ menu | Export / Import fingerprints… | Runs `export-fingerprint.sh` / `import-fingerprint.sh` with all their checks; importing over your existing fingerprints uses `--replace` |
| ☰ menu | Restore removed records… | Lists records moved to `removed-fingerprints/` or `replaced-fingerprints/` and puts the chosen ones back — only if their template is still on the sensor and that finger hasn't been enrolled again here |

Results appear as a one-line message (the full script output is behind **Details…**); information messages disappear after 10 seconds.

Records are never deleted: removed ones go to `/var/lib/samsung-galaxybook/removed-fingerprints/<date>/` (the last 5 are kept). Each sensor job stops fprintd for a moment, as the sensor can only be used by one program at a time.

The installer installs the packages it needs. If any are missing later, the launcher lists them with the command to install them (from a terminal it offers to run it) — PyGObject with GTK 3, libfprint's GObject introspection data and pkexec:

- Fedora: `sudo dnf install python3-gobject python3-cairo gtk3` (introspection data comes with libfprint)
- Debian / Ubuntu / Mint / MX: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-fprint-2.0 pkexec`
- Arch / CachyOS: `sudo pacman -S python-gobject python-cairo gtk3` (introspection data comes with libfprint)

## Turning Fingerprint Login On or Off

`fingerprint-pam.sh` turns fingerprint for login, sudo and admin prompts on or off the way each distro expects — the installer and the Fingerprint Manager both use it, so it also puts things right if the PAM setting was lost:

```bash
bash tools/fingerprint-pam.sh status
sudo bash tools/fingerprint-pam.sh enable
sudo bash tools/fingerprint-pam.sh disable    # enrolled fingerprints are kept
```

| Distro | How |
| --- | --- |
| Fedora | `authselect enable-feature with-fingerprint` / `disable-feature` |
| Ubuntu, Debian, MX Linux | `pam-auth-update` profile `fprintd` (from `libpam-fprintd`) |
| Linux Mint | `pam-auth-update` profile `fingwit` (Mint's own; it conflicts with `fprintd`'s, which is turned off) |
| Arch-based | `arch-pam.sh` — sudo and polkit-1 (below) |

## Fingerprint for sudo and Admin Prompts on Arch-Based Distros

Arch, CachyOS, Manjaro, EndeavourOS and other Arch-based distros have no authselect or pam-auth-update, so the installer asks:

```
Enable fingerprint for sudo and admin prompts? [Y/n]
```

It waits for an answer (no time limit, because it changes how you log in to sudo) and is skipped when there is no terminal. `FPRINT_PAM=1` or `FPRINT_PAM=0` answers it in advance. The same is available any time with `fingerprint-pam.sh`, or directly with `arch-pam.sh`:

```bash
sudo bash tools/arch-pam.sh enable     # sudo + polkit-1 (pkexec, graphical admin prompts)
sudo bash tools/arch-pam.sh status
sudo bash tools/arch-pam.sh disable    # removes exactly what 'enable' added
```

What it does:

- Adds one `auth sufficient pam_fprintd.so` line, marked with a comment, above the first `auth` line of `/etc/pam.d/sudo` and `/etc/pam.d/polkit-1`. `polkit-1` normally lives only in `/usr/lib/pam.d`, so it is copied to `/etc/pam.d` first (that copy takes precedence).
- Keeps a backup of each file (`*.bak-samsung-galaxybook`), and checks the edited file still contains every original line.
- Leaves any file that already mentions `pam_fprintd` alone, so hand edits are never overwritten and running it twice changes nothing.
- Is safe before enrolling: with no finger enrolled, `pam_fprintd` reports "not available" and you are asked for your password as usual.
- Uninstalling the fix runs `arch-pam.sh disable`: only the marked lines are removed, and the `polkit-1` copy is deleted if it was created by the fix and not changed since.

**Not changed:** the **KDE lock screen** already uses the fingerprint through its own `kde-fingerprint` service, and the **login screen** is left password-only (with fingerprint, Plasma's login screen waits for the sensor after you type a password).

Test in a new terminal with `sudo -k; sudo true` and `pkexec true`. Keep a root terminal open (`sudo -i`) while testing PAM changes.

**Tested** on CachyOS (KDE): `enable`, `disable`, `enable` again, with sudo and pkexec both accepting the fingerprint (2026-10-25).

**If the lock screen locks you out after a few successful fingerprint unlocks** — a known KDE Plasma 6 bug where `pam_faillock` counts successful fingerprint scans as failures — copy `/usr/lib/pam.d/kde-fingerprint` to `/etc/pam.d/kde-fingerprint` and use:
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
- Arch-based, if you said yes: one marked line in `/etc/pam.d/sudo` and `/etc/pam.d/polkit-1` (plus `*.bak-samsung-galaxybook` backups, and `/var/lib/samsung-galaxybook/pam-polkit-1-created` if `polkit-1` was copied)
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh` — removes the fix once it is no longer needed
- `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-monitor.service`
- `~/.config/systemd/user/samsung-galaxybook-fprint-sdcp-user-check.{service,timer}`
- `/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules`
- `/etc/samsung-galaxybook-egismoc-sdcp.installed` — marker (commit, its date, source and install date)
- `/var/lib/samsung-galaxybook/libfprint-system.sha256` — distro libfprint hash, to spot updates
- `/usr/local/lib/libfprint-egismoc-sdcp/sensor-check` — boot-time sensor check program
- `/usr/local/lib/libfprint-egismoc-sdcp/manager/` — Galaxy Book Fingerprint Manager (root-owned copy of `fingerprint-manager.sh`, `lib/` Python files and `tools/`)
- `/usr/local/bin/galaxybook-fingerprint-manager` — link to start it
- `/usr/share/applications/io.github.david_bartlett.GalaxyBookFingerprintManager.desktop` and `/usr/local/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg` — its menu entry and icon
- `/usr/share/polkit-1/actions/io.github.david-bartlett.galaxybook-fingerprint-manager.policy` — its password prompt
- `/usr/local/bin/samsung-galaxybook-fprint-sdcp-boot-check.sh` and `/etc/systemd/system/samsung-galaxybook-fprint-sdcp-boot-check.service` — runs it at boot, before fprintd
- `/run/samsung-galaxybook/fprint-sdcp-boot-status` — boot check result (cleared at every boot)
- `/var/lib/samsung-galaxybook/removed-fingerprints/` — records cleared by the boot check (last 5 boots that cleared any)
- `/var/lib/samsung-galaxybook/replaced-fingerprints/` — records moved aside by `import-fingerprint.sh --replace` (last 5)
- `~/.cache/samsung-galaxybook/fprint-sdcp-boot-shown` — remembers the boot check message was shown this boot

## Credits

libfprint is LGPL-2.1-or-later. Egis protocol work and SDCP driver: Joshua Grisham. Shared SDCP core: Benjamin Berg, Joshua Grisham, Marco Trevisan. Port and hardening: Abdallah Alkanani. `05a5` finger-wait: Roman2K. ET171 fixes: Philip Walsh.
