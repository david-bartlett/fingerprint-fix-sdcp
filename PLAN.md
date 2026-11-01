# fingerprint-fix-sdcp: technical plan for contributors

This is the handover for anyone (people or coding agents such as Codex) working on this repository. It explains how the project works, what every file is for, and **how changes must be made**. Read the ground rules first, then the newest notes in `handoff/`; the rest is reference.

---

## 1. Ground rules (read first)

1. **Every change is a pull request.** Create a branch, commit, push the branch and open a PR against `main`. Never push to `main`, never merge, never force-push someone else's branch.
2. **David tests every PR on his laptop before merging.** Say in the PR description what to test and how (see §9). Say plainly what you could not test (anything touching the real sensor, PAM, packages or a real desktop session).
3. **Never make a release.** Don't change `VERSION`, don't create tags (`v*`), don't create GitHub releases, don't run the release workflow. David releases with his own tool (§8).
4. **One topic per PR.** Small, focused PRs are easier to test. Before pushing more commits to an existing PR's branch, check it hasn't been merged already (`gh pr view N --json merged` or the REST API); if it has, start a new branch from `main`.
5. **Every user-visible change gets a CHANGELOG line** under `## Unreleased` (§8.2), and a README update when the README describes the thing you changed.
6. **Don't touch `DRIVER`** (the tested driver commit) unless asked.
7. **Don't add files you didn't mean to.** Review `git status` before committing, and don't use `git add -A` blindly. Test scripts and their output belong outside the repository (a test once wrote `efi/…/fingerprint-slots.json` into it and it got committed; `.gitignore` now blocks that path).
8. **Wording:** British English (enrol, colour, licence). Plain words for users; say what happens and what to do. The app is **"Galaxy Book Fingerprint Manager"** in full the first time in a section and in headings, tables and links, then **"the Manager"**.
9. **Handoff notes.** Every PR adds one short note in `handoff/` (`YYYY-MM-DD-short-topic.md`: what changed, why, what was and wasn't tested, anything for the next person; template in `handoff/README.md`). Before starting, read the notes newer than your last session. When a PR changes how something works, update this file (PLAN.md) in the same PR, so it always describes the project as it is.
10. **Safety first.** The helper runs as root; the sensor holds the user's fingerprints. Read §10 before changing anything that writes files, touches the sensor or edits PAM.

---

## 2. What the project is

Makes the **Egis fingerprint reader** (USB `1c7a:05a5` and `1c7a:05a1`) of the **Samsung Galaxy Book4 and Book5** work on Linux: fingerprint login, the lock screen, `sudo` and admin prompts.

- These readers are Windows Hello sensors and need Microsoft's **SDCP** protocol. Released libfprint has no SDCP for the `egismoc` driver, so fingerprints aren't kept.
- The fix builds **only the egismoc driver** from a tested commit of [david-bartlett/libfprint-egismoc-sdcp](https://github.com/david-bartlett/libfprint-egismoc-sdcp) (a fork of Abdallah Alkanani's repo, based on libfprint-TOD v1.95.2 and Joshua Grisham's SDCP driver) and makes **only fprintd** load it, through a systemd drop-in that sets `LD_LIBRARY_PATH`. **The distro's libfprint is never replaced.**
- Supported: Galaxy Book4 and Book5, x86_64 only. The installers refuse on a Galaxy Book3 (untested; `FPRINT_SDCP_FORCE=1` overrides), on ARM (Book4 Edge) and on non-Samsung hardware.
- Distros: Fedora 44/45 (rpm), Ubuntu 24.04/26.04, Linux Mint 22/27, Zorin OS 18, Debian 13, MX Linux 25 (deb), Arch-based distros (PKGBUILD built with `makepkg`), anything else with `install.sh`.

### The sensor, in one paragraph

The sensor has **10 slots**. Each holds one enrolled fingerprint (a "template"); the fingerprint never leaves the sensor. With SDCP, the host only gets an ID and a MAC for each template. fprintd keeps a **record** per finger in `/var/lib/fprint/<user>/egismoc/<serial>/<finger>` (finger = `1`–`9`, `a` for the right little finger) that points to a slot. Several Linux installs can **share** a slot by having the same record. Windows Hello deletes templates it didn't create when it starts, unless its fingerprint device is disabled.

---

## 3. The two packages and the install methods

| Package | What's in it |
| --- | --- |
| `fingerprint-fix-sdcp` (the driver) | the built `libfprint-2.so.2` (egismoc only), fprintd's drop-in, `fprintd-env.sh` (run by the drop-in), `other-fix.sh`, the driver's own update check, the PAM scripts (`pam/`) for the first-install setup |
| `galaxybook-fingerprint-manager` (optional) | the Galaxy Book Fingerprint Manager (window + root helper), the monitor, the boot-time sensor check, the login check, the update check, the export/import/PAM tools, polkit policy and rule, menu entry and icon |

- Either package works alone. The driver **recommends** the Manager (rpm/deb `Recommends`, pacman `optdepends`).
- **Fingerprint login (PAM)** is turned on at the **first** install on a computer (driver or Manager, whichever comes first), recorded in `/var/lib/samsung-galaxybook/fingerprint-login-set-up`; updates leave it as the user set it. `FPRINT_PAM=0` at install leaves it off. Uninstalling never turns PAM off.
- **`install.sh` / `uninstall.sh`** install the same pieces under `/usr/local` from the repository folder (`--driver-only`, `--manager-only`). The packages replace an `install.sh` copy themselves (rpm/deb); on Arch, `uninstall.sh` first.

### Where things live (`lib/fixpaths.sh`)

`fix_layout package` and `fix_layout local` define every path. Summary:

| | Package | install.sh |
| --- | --- | --- |
| Driver library | `/usr/lib/fingerprint-fix-sdcp/` | `/usr/local/lib/libfprint-egismoc-sdcp/` |
| fprintd drop-in | `/usr/lib/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf` | `/etc/systemd/system/fprintd.service.d/…` |
| Manager | `/usr/lib/galaxybook-fingerprint-manager/` (Fedora keeps scripts in `/usr/libexec/…`) | `/usr/local/lib/galaxybook-fingerprint-manager/` |
| Markers | `/usr/lib/…/installed` files | `/etc/samsung-galaxybook-egismoc-sdcp.installed`, `/etc/galaxybook-fingerprint-manager.installed` |
| State | `/var/lib/samsung-galaxybook/` (PAM marker, removed/replaced records, libfprint hash) | same |
| Runtime | `/run/samsung-galaxybook/` (monitor and boot-check status for the login check) | same |

---

## 4. Repository map

### Top level

| File | Purpose |
| --- | --- |
| `README.md` | User documentation. Structure: install → updating → uninstall → supported hardware → the Manager → dual-boot → enrolling → PAM → monitor → boot check → **Multi-Distro Mode** (everything for several distros, at the end on purpose) → more details. Keep the top simple; big tables and detail in `<details>`. Images 700px wide files, shown at `width="350"`. |
| `CHANGELOG.md` | One section per release; new work under `## Unreleased` (§8.2). |
| `PLAN.md` | This file. |
| `AGENTS.md` | Short rules for coding agents; points here. |
| `VERSION` | The release number (David changes it when releasing). |
| `DRIVER` | The tested driver commit (full id) the release builds. |
| `LICENSE` | GPL-2.0-or-later. |
| `install.sh` | The from-source installer: checks hardware and distro, installs build deps, builds the driver commit from `DRIVER` (applying `lib/patches/` if needed), installs driver + Manager under `/usr/local`, PAM on first install, imports `~/fingerprint-export.tgz` if present, offers to open the Manager. Options: `--driver-only`, `--manager-only`; env `FPRINT_PAM`, `SDCP_COMMIT=latest`, `SDCP_REPO_URL`, `FORCE`, `FPRINT_SDCP_FORCE`, `FPRINT_IMPORT`, `FPRINT_OPEN_MANAGER`. |
| `uninstall.sh` | Removes an `install.sh` copy (`--driver-only`, `--manager-only`). Never deletes fingerprints; takes this install out of the shared slots file (`lib/shared_slots.py --forget-here`). |
| `fingerprint-manager.sh` | Launcher for the Manager: checks Python/GTK/libfprint-introspection/pkexec, lists missing packages, then `exec python3 lib/fingerprint-manager.py "$@"`. |
| `images/` | README screenshots. |

### `lib/`

| File | Purpose |
| --- | --- |
| `fingerprint-manager.py` | **The Manager's window** (GTK 3, runs as the user, ~4000 lines). Tabs, menus, dialogs, information panel, update flow. Talks to the helper (below). |
| `fingerprint-manager-helper.py` | **The root helper**, started once per session with `pkexec`. Reads JSON requests on stdin, answers one JSON line each (`{"ok": true, "result": …}` or `{"ok": false, "error": …}`). Opens the sensor with libfprint (stopping fprintd meanwhile), reads/moves fprintd records, runs the tools. Action table: `ACTIONS` at the bottom. |
| `shared_slots.py` | The **shared slots file** on the EFI partition (§6): finding the EFI partition, this install's key and location, writing/reading templates and records, detecting installs that no longer exist, forget, backup/restore merge. Also a CLI: `shared_slots.py --forget-here` (run as root by package removal). |
| `sensor-check.py` | Compares fprintd's records with the sensor's templates (boot check, import check); `--set-owner USER IN OUT` rewrites a record's owner (import for another user name). |
| `distro-driver-check.py` | Does the distro's own libfprint now have an SDCP driver for the reader, and is it the distro's unmodified package (or another fix's build)? Used by the monitor and the Manager's "Test your distro's driver". |
| `update_check.py` | Asks GitHub for the latest release (cached), notifies once per version (critical urgency, retries the network) and only once the release's `SHA256SUMS` is there (`release_assets`; the Manager's Update button likewise), used by the window's Update button and the hourly timers. Compares versions numerically. | Also the command's `update` (`--update`: the newest release installed in the user's own terminal via `install()`, `GBF_OWN_TERMINAL=1` so nothing waits to close a window) and `updates on|off|status|check` (`--updates`: `set_enabled` / `enabled`, the same timers as the Manager's switch; `check` asks GitHub now and calls `show_notification`).
| `notify-update.sh`, `notify-open-manager.sh`, `notify-dbus.py` | Notification helpers. New version (`notify-update.sh TITLE MESSAGE URL VERSION`): **Update now** (only when `update_check.py --can-update-now`: the Manager installed from a package, `terminal.py` and `update-in-terminal.sh` beside it, a terminal found; then `exec … --update-now VERSION URL` *becomes* the terminal (exec, not a child: the notification runs in a `systemd-run` service, which stops everything in it once its main process ends, so a terminal started alongside was closed at once) running `--install VERSION`, or opens URL if no terminal starts, which picks this system's packages with `pick_asset`, downloads and checks them into `/tmp/galaxybook-update-*`, and hands `install_command` to `update-in-terminal.sh`, as the Manager's Update does) and **What's new** (the release page, then the notification again 2 s later). With buttons the text is MESSAGE's first line (*You have X.Y.Z.*); without, all of it and the URL. While it's on screen it reads the installed `VERSION` (next to `lib/`) every 2 s and closes once it's VERSION or newer (updated another way): `notify-dbus.py` closes its own (`NOTIFY_WATCH_FILE` / `NOTIFY_WATCH_VERSION`), and for `notify-send` it's `--print-id` and `gdbus … CloseNotification ID` (`wait_notify_send`; desktops that refuse leave it). The driver alone gets only *What's new* (the release's packages are installed together). Login check (`notify-open-manager.sh`): **Open Fingerprint Manager**. On GNOME (not Budgie) both show it with `notify-dbus.py` (Python + PyGObject, straight over D-Bus, waiting for the button press, which GNOME sends only to the program that made it): `notify-send` 0.8.8 on Ubuntu 26.04 says *Actions are not supported* and drops the buttons, although GNOME lists `actions` and shows them. There a click on the notification is *What's new* (new version) or opens the Manager (login check) (`default` action, GNOME only). Same D-Bus helper as galaxybook-fan's. |
| `terminal.py` | Finds the user's terminal (desktop setting → `xdg-terminal-exec` → the desktop's own → `x-terminal-emulator` → known list). |
| `update-in-terminal.sh` | Runs the update command in that terminal, then signals the window (which offers Restart). Also the last step of the notification's **Update now** (`update_check.py --install`, with `TITLE_SHOWN=1`). |
| `fixpaths.sh` | All install paths, for both layouts (§3). Sourced by every shell script. |
| `other-fix.sh` | Finds another fingerprint fix's fprintd setup (moved aside at install). |
| `galaxybook-fingerprint-manager.svg` | The icon. |
| `patches/` | Build-time fixes for the driver source, applied only while needed (currently none). |

### `tools/`

| File | Purpose |
| --- | --- |
| `fingerprint-pam.sh` | Turn fingerprint login on/off the distro's way (Fedora authselect, Debian/Ubuntu/MX pam-auth-update `fprintd`, Mint `fingwit`, Arch `arch-pam.sh`). |
| `arch-pam.sh` | Adds/removes one marked `pam_fprintd` line in `/etc/pam.d/sudo` and `polkit-1` on Arch-based distros. |
| `pam-first-install.sh` | The "turn PAM on at the first install only" logic, shared by the packages. |
| `export-fingerprint.sh`, `import-fingerprint.sh` | Command-line export/import of fprintd records (`~/fingerprint-export.tgz`). For installs without the Manager; the Manager's own import builds a temporary archive and runs `import-fingerprint.sh`. Options are listed at the top of the script. |
| `test-latest-libfprint.sh` | Try upstream's newest driver. |
| `dev/` | Sensor debugging scripts for development only. |

### `packaging/`

| File | Purpose |
| --- | --- |
| `README.md` | Building packages locally, what install/removal do, a package test checklist, driver updates. |
| `build-driver.sh` | Builds the egismoc-only libfprint (`meson … -Ddrivers=egismoc -Dtod=false …`), applying `lib/patches/`. |
| `install-files.sh` | Installs the files of one package (`driver` or `manager`) into a staging root: used by all three package formats. **New Manager files must be added here** (and to `install.sh`'s file list and copy steps). |
| `render.sh` | Fills `@PLACEHOLDERS@` in `files/*.in` from `fixpaths.sh`. |
| `files/*.in` | Templates: systemd units (monitor, boot check, login check timer, update-check timers), the drop-in, `fprintd-env.sh`, polkit policy/rule, desktop entry, session helper (starts `graphical-session.target` on desktops that don't), `checks-off-hint.sh` (on Manager removal), cleanup scripts. |
| `make-sources.sh` | Source tarballs for rpm/deb builds. |
| `rpm/fingerprint-fix-sdcp.spec`, `rpm/build.sh` | Fedora: one spec, driver + Manager subpackage. `bash packaging/rpm/build.sh [REVISION]`. Scriptlets: `%post`/`%preun` (removal tidy-up only when `$1 == 0`). |
| `debian/*`, `debian/build.sh` | Debian/Ubuntu: `control` (two binary packages), maintainer scripts per package (`prerm remove` = real removal). `bash packaging/debian/build.sh [REVISION]`. |
| `arch/PKGBUILD` | Builds this checkout (`cd packaging/arch && makepkg -si`). |
| `arch/PKGBUILD.release.in` | Template for the PKGBUILD attached to each release (builds the release tarball). Keep `makedepends` in step with `PKGBUILD`. |
| `arch/*.install` | pacman hooks per package (`post_install`, `post_upgrade`, `pre_remove`). |

### `.github/`

| File | Purpose |
| --- | --- |
| `workflows/release-packages.yml` | Runs when a `v*` tag is pushed (David's release): checks the tag matches `VERSION`; builds rpms (Fedora 44, 45), debs (Debian 13, Ubuntu 24.04, 26.04); checks the Arch package builds with **only the PKGBUILD's makedepends** and writes the release PKGBUILD; creates the release **as a draft** with notes, attaches everything plus `SHA256SUMS`, then publishes it (`--latest`; only a release still in draft, so re-running for an old tag never makes it the latest). Drafts are hidden from `releases/latest`, so the update check never sees a release without its files. |
| `release-notes.sh` | Writes the release page: the box at the top of `release-install.md` (before its first `## `), then **What's new** (the CHANGELOG section's bold lines, and the whole section collapsed), then the rest of `release-install.md` (1. Install, 2. Update). The same layout as galaxybook-fan's. |
| `release-install.md` | The box, 1. Install and 2. Update of every release page (the box ends at the first `## `). |
| `ISSUE_TEMPLATE/` | Bug report and "it works on my laptop" forms. |

---

## 5. How it works at runtime

- **fprintd drop-in → `fprintd-env.sh`.** Each time fprintd starts, it checks the Galaxy Book reader is on USB and writes `/run/samsung-galaxybook/fprintd-sdcp.env` with `LD_LIBRARY_PATH` to the fix's library (empty otherwise). So only fprintd uses the fix, and only on this hardware.
- **Boot check** (`samsung-galaxybook-fprint-sdcp-boot-check.service`, Manager package): before fprintd starts, compares records with the sensor; records whose template is gone (Windows wiped them) are moved to `/var/lib/samsung-galaxybook/removed-fingerprints/<date>/` and reported at login.
- **Monitor** (root service, started by a user timer 10 s after login, allowed by a polkit rule): checks the fix is intact, whether the distro libfprint changed and now has SDCP, whether fprintd sees the sensor and runs this driver. Writes `/run/samsung-galaxybook/fprint-sdcp-status`.
- **Login check** (user timer): shows the monitor's and boot check's messages as notifications (app name "Samsung Galaxy Book Fixes"), once each.
- **Update checks** (user timers, 30 s after login then hourly): the driver's and the Manager's; only one runs (the driver's is skipped while the Manager is installed). Notification once per version; turning it off in the Manager masks the timers.
- **Session helper:** starts `graphical-session.target` on desktops that don't (Xfce and others), so the user timers run.
- **systemd gotcha:** in unit command lines systemd expands `$VAR`; inline scripts passed via `systemd-run` must write every `$` as `$$`.

---

## 6. The Galaxy Book Fingerprint Manager

### Architecture

- The window (`fingerprint-manager.py`) runs as the user. One window per session (`Gtk.Application`; a second start raises the first).
- The first time it needs the sensor it starts the helper with `pkexec` (one password per session; policy `io.github.david-bartlett.galaxybook-fingerprint-manager`). The helper re-executes itself with the fix's library in `LD_LIBRARY_PATH`.
- `run_job(action, done, **kw)` sends a request on a thread; `done(result, error)` runs on the GTK main loop. `self.busy` is true meanwhile. **Anything queued with `GLib.idle_add` that needs the helper must retry while busy** (the start-up import offer once got lost this way).
- After almost every job the window calls `refresh()`: the helper's `status` action reads the sensor, records, moved-aside records, the shared file, PAM state and the import offer, and the window redraws.

### Tabs and modes

- **Fingerprints tab:** cards (your ten fingers) or a list (every user). Click = select + details in the panel; double-click = test; right-click menu (test, enrol again, show on sensor, remove from <distro>, restore removed fingerprint…). Bottom: **Remove all from <distro>…** (restorable) and **Test any fingerprint**.
- **Sensor slots tab:** the sensor's slots as cards/list; Clear…, Clear all slots… (type CLEAR), **Other distros…** (multi mode), ⓘ dialog.
- **Single vs multi-distro mode** (`_apply_mode`, every refresh): multi when the shared file lists another install that still exists.
  - Single: header shows just "Fingerprints (N)"; ☰ has Restore <distro> fingerprints…, **Show sensor slots** (switch, setting `sensor_tab`), Check for new versions, Remind me about Windows, Test your distro's driver…, About. The Sensor slots tab appears only "for a visit" when something opens it (Show on sensor, sensor full).
  - Multi: both tabs always; ☰ adds **Import from other distros…**, **Back up & restore…**, **Reset <distro>…**. A one-time message names the other distros (setting `multi_known`).
  - `galaxybook-fingerprint-manager --single-distro` forces the single layout for testing (display only).
- **Information panel** (`MsgPanel`): alerts (warnings, errors, results of actions) **blink** (`MSG_BLINK_S`, `BLINK_MS`) and **stay** until × or a newer message; plain information (`alert=False`, e.g. finger/slot details, grey "OTHER" style) doesn't blink and goes after `PLAIN_MSG_S` or when leaving the tab, restoring any alert it covered. Tabs opened from a menu blink `BLINKS` times.
- **Settings** (`~/.config/galaxybook-fingerprint-manager/settings`, `key=value`): `view` (icons/list), `sensor_tab`, `windows_hint`, `offer_declined` (template IDs not to offer again), `multi_known`.

### Records, removal and restore

- **Remove** moves a record to `/var/lib/samsung-galaxybook/removed-fingerprints/<date>/…` (the slot stays). **Restore <distro> fingerprints…** (with Select all) or the right-click entry puts it back.
- `prune_moved` deletes a moved copy only when it can't be used again: its slot is gone from the sensor, or the same user has that slot again. **There is no "keep the last N folders" rule** (that lost copies once; don't bring it back).
- `import-fingerprint.sh --replace` moves records to `replaced-fingerprints/` the same way.

### The shared slots file (multi-distro)

`<EFI partition>/EFI/samsung-galaxybook/fingerprint-slots.json` (found at `/boot/efi`, `/efi`, `/boot`, or any vfat mount with an `EFI` folder):

```json
{"version": 1,
 "installs": {"<key>": {"os": "Fedora", "seen": "YYYY-MM-DD",
                        "where": {"partuuid": "…", "uuid": "…", "ptuuid": "…", "dev": "nvme0n1p8", "size": "…"}}},
 "sensors": {"<serial>": {"<template id>": {"finger": "right-index-finger", "user": "dave",
     "enrolled": "YYYY-MM-DD", "enrolled_on": "Fedora", "record": "<base64 fprintd record>",
     "installs": {"<key>": {"os": "Fedora", "state": "used|removed", "seen": "YYYY-MM-DD"}}}}}}
```

- `<key>` = first 12 hex of sha256(`/etc/machine-id`). Template id = first 10 hex of sha1 of the sensor's serialized template.
- Written at every status read (only if changed, atomically). Templates no longer on the sensor are pruned.
- **Install detection:** each start compares other installs' `where` with `lsblk`: partition gone from a present disk, or a different filesystem/LUKS UUID on it → **gone** (forgotten, message shown); disk absent or no `where` (older versions) → **unknown** (kept).
- **Import offer** (`import_offer`): records on the EFI partition whose slot is on the sensor, not used here, not removed here, and whose finger the user doesn't have working. Shown at start (not ones turned down or removed here) and from ☰ → Import from other distros… (all, except removed here).
- **Reset <distro>** (`reset_install`): deletes this install's records and moved copies, clears the slots no other install uses, forgets this install; the window then offers the kept ones back.
- **Back up & restore:** backup = the whole file as `.json`; restore = `merge_backup` (adds missing templates/records/installs, changes nothing existing).
- Package removal (not upgrade) runs `shared_slots.py --forget-here`.
- Records are not fingerprints (an ID and the sensor's MAC), useless without this sensor.

---

## 7. Coding conventions

- **Python:** the window and helper target the system Python 3 with PyGObject (GTK 3, libfprint `FPrint-2.0`). No extra pip dependencies. Keep `python3 -m py_compile lib/*.py` clean; don't commit `__pycache__`.
- **Shell:** bash, `set -euo pipefail` where the script already uses it; `bash -n` clean. Paths from `fixpaths.sh`, never hard-coded twice.
- **GTK details that have bitten before:** a widget with `set_no_show_all(True)` isn't shown by `show_all()` (show it and its children explicitly); GTK 3 CSS has no `transform`; a `FlowBox` reserves height for its narrowest layout (keep card labels one line).
- **Messages and dialogs:** say what happened and what the user can do; destructive buttons use the `destructive-action` style and are never the default; name fingers ("Right index finger"), not files.
- **Comments:** explain why, briefly. Match the existing style.

---

## 8. Releases (David only) and the CHANGELOG

### 8.1 How David releases

David releases with **`fingerprint-repo-gui.py`**, in his private repository `david-bartlett/samsung-galaxybook-dev-tools` (folder `fingerprint-fix-sdcp-github`). Its Release button sets `VERSION`, turns `## Unreleased` into `## X.Y.Z — date`, commits ("CHANGELOG: start Unreleased section" adds a fresh `## Unreleased`), tags `vX.Y.Z` and pushes. The tag starts `.github/workflows/release-packages.yml`, which builds and attaches the packages and writes the release page with `.github/release-notes.sh`.

**Contributors never do any of this.** Versioning (for David's information): fixes → `x.y.Z`, features → `x.Y.0`, a change users must act on → `X.0.0`.

### 8.2 CHANGELOG rules

- Add lines under `## Unreleased` at the top (create it if a release just happened and it's missing; never add lines to an already released section).
- Each change is a `- ` line. Group related lines; separate groups with a blank line.
- A **bold headline line** (`- **Short headline:** a few words`) for the release page's *What's new*. Keep it short.
- Then **plain lines** with the full detail (shown only under the collapsed *Full changelog*).
- **Every release needs at least one bold line.** Example:

```markdown
## Unreleased

- **Removed fingers can always be restored:** removing several one at a time lost the first ones' copies
- Removed and replaced records were kept in dated folders, only the newest 5. …
```

---

## 9. Testing

### 9.1 What you can do without the hardware

- `python3 -m py_compile lib/*.py`; `bash -n` every changed shell script (including `packaging/files/*.in`).
- **Logic:** import `lib/shared_slots.py` or the helper in a test script and replace `FPrint.Print` with a small stand-in class (`deserialize`, `serialize`, `equal`, `set_username`), `shared_slots._path`, `_lsblk`, `install_key`, `os_label`. Keep test scripts **outside the repository**.
- **Window:** load `fingerprint-manager.py` in a test script under `xvfb-run` and give it a fake status (replace `Helper.call`, `Helper.start` and `Helper.stop` so `status` returns a dict with `user`, `records`, `templates`, `features`, `installs`…). Screenshot with ImageMagick `import -window root`. Describe what you checked in the PR.
- The release workflow's builds run only on David's tag; a PR doesn't build packages.

### 9.2 What David tests (write the steps in the PR)

David has a Galaxy Book5 Pro (940XHA, reader `05a5`) that multi-boots **Fedora 45** (KDE; EFI partition at `/boot/efi`), **Ubuntu 26.04** (GNOME), **Linux Mint 22.3** (Cinnamon), **MX Linux 25** (Xfce) and **CachyOS** (KDE, Limine; EFI partition at `/boot`), with Windows. He builds a PR branch like this:

```bash
git fetch && git checkout <branch>
bash packaging/rpm/build.sh <N>                     # Fedora; N > the installed revision
sudo dnf install ./packaging/out/*<version>-<N>*.rpm
# Ubuntu / Mint / MX: bash packaging/debian/build.sh <N>, then sudo apt install ./packaging/out/*.deb
# Arch / CachyOS:     cd packaging/arch && makepkg -sif
```

Then he closes and reopens the Manager. Give him a short numbered list of what to click and what he should see. `packaging/README.md` has the full package checklist.

---

## 10. Safety and gotchas

- **The helper is root.** Never write into a user's home as root by following a path the user controls: write a new file with `O_CREAT | O_EXCL | O_NOFOLLOW` beside it, `fchown`, then `os.replace` (a link there is replaced, not followed). Validate user names (`[a-z_][a-z0-9_.-]*`), finger names (`[1-9a]`), template ids, and keys from requests.
- **Never delete `/var/lib/fprint` records by hand** and never use `fprintd-delete` to make room: it deletes the template from the sensor too, breaking every install sharing it. Records are moved aside, not deleted.
- **The sensor is exclusive:** the helper stops fprintd while it uses the sensor (`Sensor` context manager) and starts it again. Keep jobs short.
- **Clearing a slot can't be undone**, for every distro. Any new code path that clears slots needs a confirmation naming what's lost; keep slots other installs use (`used_elsewhere`).
- **Don't trust a failed sensor listing:** if the slots can't be listed, don't delete anything for being "gone".
- **PAM:** never leave a user locked out; changes go through `fingerprint-pam.sh`/`arch-pam.sh`, which back up and verify. Uninstalling never turns PAM off.
- **Package scriptlets:** tidy-up on **removal only**, not upgrade (rpm `$1 == 0`, deb `prerm remove`, Arch `pre_remove`). Never fail a removal.
- **fish:** CachyOS's default shell is fish; commands in the README must work there (no bash-only loops).
- **Dual-boot:** Windows Hello wipes Linux templates unless its fingerprint device is disabled; the Manager reminds users.

---

## 11. Ideas not done yet (ask David before starting)

- The helper's `export` action is no longer used by the window (Export left the menu); it could be removed.
- Finger cards still have a hover tooltip that overlaps the details now shown in the information panel.
- Sharing fingerprints from a driver-only install (would need the tools and Python bindings in the driver package).
- Offering to forget the old install automatically when a reinstalled distro imports its fingers.
- **Distro repositories, later:** a Fedora COPR, an Ubuntu PPA and an AUR package, so updates come through the distro's own updater. Not a priority until we're sure there are no bugs; for now each release attaches the rpm, deb and PKGBUILD files.
