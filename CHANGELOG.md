# Changelog

<!-- Release pages (.github/release-notes.sh): lines that start with a bold
     headline, "- **Two packages:** …", are listed under What's new; the whole
     section is under "Full changelog" (collapsed).
     Bold lines: short, so What's new stays brief.
     Plain lines: the full detail, shown only in Full changelog.
     Every release, even a small one: at least one bold line. -->

## Unreleased

- **Arch / CachyOS: builds on a fresh install:** `makepkg -si` failed with *Dependency "gusb" not found* when fprintd wasn't installed yet
- The PKGBUILD's build dependencies now include `libgusb` and `openssl` (the driver links them; before, they only came with fprintd). The release workflow's Arch check installs only the PKGBUILD's build dependencies, as a fresh system has, so a missing one fails there

- **The import offer shows on a fresh install:** it could be skipped when the Manager opened
- The Manager looks for fingers to offer as it reads the sensor at start, but on a new install it straight away also checks the distro's own driver, and the offer, finding the Manager busy, was dropped. It now waits until that check is done

- **After Reset <distro>…, import again or start empty:** if your fingers' slots are still on the sensor, you're asked straight away
- Reset forgets which fingers were turned down on this distro, then asks **Import your fingerprints again?** with **Import** or **Start empty** (they can still be imported later from ☰). With nothing to offer, it just says what was reset. The Reset dialog says which fingers can be imported again (those in slots kept for other distros) and which can't (cleared slots)

- **Your fingerprints follow you between distros:** a new or reset distro offers the fingers the others already use, from the EFI partition, with nothing to copy
- Each install keeps its fingers' fprintd records in `fingerprint-slots.json` on the EFI partition (only an ID and the sensor's signature; a record goes when its slot is cleared). When the Manager opens, it offers the fingers this install could use straight away, in one list with a tick box each and the distros it's from (another user name is shown and, with more than one, left unticked). One turned down isn't asked about again until **Reset**; ☰ → **Import from other distros…** lists them all again, and fingers removed here too (marked *removed here*; the automatic offer leaves those out), with **Choose a file…** for an export file; with nothing to offer it says so. ☰ → **Back up & restore…** explains the file and how many records it has: **Back up…** saves a copy as `.json`, **Restore…** merges one back (adds what's missing, changes nothing there) should the EFI partition be formatted. ☰ → **Export fingerprints…** is gone (`tools/export-fingerprint.sh` still makes an export file, e.g. for an install with only the driver)
- Importing a file with the right little finger in it failed ("Unexpected entry in archive"): fprintd's name for it is `a`, which the check read as a number

- **New messages blink and stay:** the information panel at the bottom blinks for 5 seconds when a message appears, and keeps it until you close it
- A message stays until × is pressed or a newer one replaces it (information used to go after 10 seconds). The panel blinks like the tabs, for about 5 seconds (`MSG_BLINK_S`). Both blink more slowly than the tabs did in 2.8.1: plain for 0.4 s each time, 0.8 s per blink (`BLINK_MS`)

## 2.8.1 — 2026-10-29

- **The open tab stands out:** Fingerprints / Sensor slots, and it blinks twice when a menu switches tabs
- The tab you're on is filled with the theme's accent colour. **Show on sensor**, **Show finger** and the sensor-full dialog's **Open Sensor slots** switch tabs and the new tab blinks twice, so the switch is noticed

## 2.8.0 — 2026-10-29

- **Updating with install.sh no longer turns fingerprint login back on:** if you turned it off, it stays off
- `install.sh` on Fedora, Ubuntu, Mint, Debian and MX turned fingerprint login on every time it ran, so updating with `git pull` and `sudo bash install.sh` undid turning it off in the Manager. Now, like the packages, it only turns it on at the first install on the computer, and `sudo FPRINT_PAM=0 bash install.sh` leaves it off there too. README: how to pass `FPRINT_PAM=0` with each install method (with Arch's `makepkg -si` it can't be: `makepkg -s`, then `sudo FPRINT_PAM=0 pacman -U`)

- **Removing a distro tidies up its sensor slots:** the other distros stop listing it, and a wiped one can be forgotten
- Removing the Galaxy Book Fingerprint Manager (dnf / apt / pacman remove, or `uninstall.sh`; not an update) takes this install out of `fingerprint-slots.json` on the EFI partition, so the other distros no longer show its slots as used by it. A distro that was wiped or reinstalled without that can be forgotten from another one: **Other distros…** at the bottom of the Sensor slots tab (also in the ⓘ dialog) lists every distro in the file with the date it last opened the Manager and how many slots it uses; select one → **Forget…**. A distro listed twice (a reinstall) is pointed out. Slot tooltips say when another distro hasn't been seen for a month or more ("CachyOS last seen 1 Jul 2026"). The shared-file code moved to `lib/shared_slots.py`

- **Forgetting a wiped distro can clear its slots too**, and the ☰ menu has icons like the right-click menus
- **Reset this distro:** ☰ → Reset <distro>… deletes its fingerprints, frees the slots only it uses and takes it out of the shared file, before a reinstall or to start again
- Distros sharing the sensor… → Forget… now lists the slots only that distro used (not this install's, and no other distro still using them) and offers **Forget and clear N slots**, which erases them from the sensor as well, or **Forget only**. ☰ → **Reset <distro>…** (e.g. Reset CachyOS…) starts this distro again: every user's fingerprint records here are deleted for good, with those moved aside earlier; the slots only it uses are cleared from the sensor; ones other distros also use are kept; and it's taken out of `fingerprint-slots.json`. The ☰ menu's options have icons and the same style as the right-click menus; its two on/off options have a switch on the right instead of a tick box, so nothing is indented

## 2.7.0 — 2026-10-28

- **Tidier window:** no empty space under the slots, and short, readable hover text
- The window shrinks to fit its contents once the sensor has been read and when the Windows reminder is shown or hidden (a GTK window grows but never shrinks by itself, so it could keep empty space under the slots); not when maximised or tiled
- Card names (*Right middle*, *Left thumb*…) stay on one line. GTK measures the card grid at its narrowest, where a name would wrap, so it kept a second line's height in every row: the empty space under the Sensor slots cards, larger with bigger fonts or scaling
- Sensor slots tab: the hover text over a slot is in short lines — who it is, where it is used, its template ID — instead of one long line

- **What is a slot?** The *Sensor* tab is now *Sensor slots*, with an ⓘ button that explains what a slot holds, and the difference between removing a finger (only from this Linux) and clearing a slot (erased from the sensor for every install)

- Sensor tab: slots are listed in the same hand order as the Fingerprints tab (right index, middle, ring, little, thumb, then the left hand) within each group (used here, removed here, used by other distros, unknown), instead of by template ID
- Sensor slots tab, cards: a slot used here and by other distros says so in its green label: *Used here / + 4 distros*

- **Simpler README:** what matters first (which laptops, the Windows and multi-install warnings, install, enrol, update, uninstall), with the details and big tables in collapsible sections. The driver is presented as what you need and the Manager as optional; the maintainer's release steps moved to packaging/README.md; outdated bits (Arch updating, messages, installed files) brought up to date

## 2.6.1 — 2026-10-28

- **Shorter notification titles:** e.g. *fingerprint-fix-sdcp 2.6.0 is available*, which fits on one line
- Notification titles no longer start with "Samsung Galaxy Book — ": the desktop already shows the app name, *Samsung Galaxy Book Fixes*, above each one, and on GNOME the update notification's title was cut off
- Sensor tab: a slot's tooltip reads *Right ring finger (dave) — also used by Fedora*, not *used by dave right-ring-finger*
- **Restart after an update works every time:** the new Fingerprint Manager waits until the old one has fully closed. It used to start after a fixed second and, if closing took longer (it stops its helper first), found the old one still running and quit, so on Cinnamon and CachyOS's KDE, for two, nothing came back. The new one is also started by the user's systemd (`systemd-run --user`), outside the old app, so a desktop that cleans up after an app that quits can't stop it

## 2.6.0 — 2026-10-28

- **Slots shared between installs say whose finger they are:** the Sensor tab shows which finger a slot holds and which other distro uses it
- With SDCP the sensor only knows a template's ID, so each install now notes its templates (finger, user, enrolment date, distro, and whether it still uses each one or removed it) in a small shared file on the EFI system partition, which every OS on the laptop shares: `EFI/samsung-galaxybook/fingerprint-slots.json`. A slot this install doesn't use then shows e.g. *Right little · Fedora* (list: *dave · used by Fedora · enrolled 28 Oct*, or *removed on Fedora*), and one it uses says *also used by Ubuntu*. Slots no install has noted (Windows Hello's, or a distro that hasn't run this Manager yet) stay *Unknown*. The file updates whenever the Manager reads the sensor, and forgets slots that are no longer on it (cleared, or wiped by Windows)
- With several distros sharing a slot it stays short: *also used by Fedora and Ubuntu*, or *also used by 4 other distros* (cards: *Fedora +3*); the tooltip names them all

## 2.5.4 — 2026-10-28

- **Update check at login always asks GitHub:** a release made while you were logged out is noticed straight after login
- The update check reuses GitHub's answer for an hour, but no longer one saved before the current login: the first check after logging in always asks GitHub. Before, an answer from up to an hour earlier could hide a release made since (2.5.3, released 2 minutes before logging in, went unnoticed)

- **Clear all slots:** the Sensor tab's *Wipe sensor…* is now *Clear all slots…*, matching *Clear…* for selected slots
- *Wipe sensor…* is renamed *Clear all slots…*; its confirmation asks *Clear all slots on the sensor?* and you type CLEAR (was WIPE)

- **Sharing fingers after Enrol again:** a fresh export from one install now replaces that finger on the others
- *Enrol again* says up front (not under Details) that other Linux installs sharing the finger lose it, and to export and import afterwards
- A record whose template is gone from the sensor (the finger was re-enrolled on another install) now counts as missing: the automatic offer from `~/fingerprint-export.tgz` includes it, and *Import fingerprints… → Add the missing ones* replaces it (the dead record is moved to /var/lib/samsung-galaxybook/replaced-fingerprints/). Before, it was kept and the new fingerprint skipped, so only *Replace all* worked. `import-fingerprint.sh` gains `--dead` for this
- Sensor tab: *Delete…* and *Delete from sensor…* are now **Clear…** and **Clear slot…**, and their confirmation says *Clear this slot?* / *Clear 2 slots?*: it's the sensor's slot that is freed

## 2.5.2 — 2026-10-28

- **Update notification right after login:** the first check for a new release is 30 seconds after login, not 10 minutes
- The hourly update check (both packages' user timers) first runs 30 seconds after login instead of 10 minutes, without the random delay. If the network isn't up yet, it tries again every 30 seconds for up to 3 minutes. GitHub is still asked at most once an hour

## 2.5.1 — 2026-10-28

- **Window opens centred:** the Fingerprint Manager opens in the middle of the screen on Xfce, Cinnamon and MATE
- The Manager asks to open in the middle of the screen. Window managers on X11 (Xfce, Cinnamon, MATE) follow that; Xfce placed it off to the bottom right before. GNOME and KDE on Wayland place windows themselves, as before

## 2.5.0 — 2026-10-28

- **Tidier right-click menus:** a heading with the finger, an icon for each option, and removing set apart in red
- The right-click menus on both tabs start with what was clicked (e.g. *Right index finger · On the sensor*, or *Unknown template*), give each option an icon from your theme instead of a › mark, keep Remove / Delete apart at the bottom in red, and have rounded corners with a softer highlight. *Remove from …* now ends in "…", as it asks first

- **Information panel:** the Manager's messages now appear in a panel at the bottom of the window
- Messages (what was done, warnings, errors, Restart after an update) are in a rounded panel at the very bottom of the window, tinted blue, amber or red by kind, with their buttons and a × to close them. With nothing to say it shows *Information panel*. The space they used to keep free between the page and its buttons is gone, so the Sensor tab's buttons sit right under the slots
- Fingerprints tab: the finger cards sit in the middle of the space the taller Sensor tab leaves, instead of at the top with a gap below, and *Test any fingerprint* is on the right, like the Sensor tab's *Wipe sensor…*
- A finger you remove in the Manager is no longer offered back straight away from `~/fingerprint-export.tgz` (*Import … from another install?*): fingers removed here are left out of that file's offer. Other fingers in it are still offered once, and a new export file is offered afresh. ☰ → *Restore removed records* still brings a removed finger back

## 2.4.2 — 2026-10-28

- **No password prompt on the login screen:** the login check no longer runs for the login screen itself
- The login check and the hourly update check are enabled for every user, and on Ubuntu 26.04 the login screen runs a desktop session of its own (GDM's `gdm-greeter` user). There, the login check tried to start the fingerprint monitor and, as that user isn't an admin, an *Authentication Required* prompt for samsung-galaxybook-fprint-sdcp-monitor.service appeared before anyone had logged in. Both checks now only run for people's accounts (UID_MIN to UID_MAX in /etc/login.defs). The login check also starts the fingerprint monitor with `systemctl start --no-ask-password` now, so it never asks for a password: for a user outside the wheel / sudo groups (whom the polkit rule doesn't cover) the check is skipped instead

- **Release builds updated:** no more Node.js 20 warnings, and a stuck build stops after 45 minutes
- Release builds: GitHub Actions updated to their Node.js 24 versions (checkout v6, upload-artifact v6, download-artifact v7), and each job stops after 45 minutes instead of hanging for hours on a stuck package mirror

- The *Update* dialog names the terminal it opens when that is the system's default (`xdg-terminal-exec`, as on Ubuntu 26.04, or `x-terminal-emulator`), e.g. "in a Ptyxis window"; when it can't tell, "in your terminal" (it said "in a a terminal window")

## 2.4.0 — 2026-10-28

- **Update installs in a terminal:** the Manager's **Update** opens your terminal and installs the new version there
- The Manager's **Update** now downloads the new files to a folder of their own in `/tmp` (removed once installed, and emptied at restart, so `~/Downloads` stays tidy) and opens your terminal to install them: it shows the command, `sudo` asks for your fingerprint or password, dnf / apt / pacman ask you to confirm, and the window closes itself 10 seconds after it's done (it stays open if something went wrong). Once it's installed and the terminal window has closed, the Manager asks in a window of its own whether to restart into the new version (before, only a bar at the bottom said so). The terminal is the one your desktop is set to use (KDE, Xfce, Cinnamon, MATE), else `xdg-terminal-exec`, the desktop's own (Ptyxis, GNOME Terminal, Console, Konsole…), `x-terminal-emulator`, or any other known one. With none found, or if it can't be started, it works as before: the files go to `~/Downloads` with the command to paste

## 2.3.2 — 2026-10-28

- **Removing the Manager with update checks off:** a notification offers to turn them back on for the driver
- If you turned *Check for new versions* off in the Manager, the driver's check stays off after the Manager is removed, and there's no switch left to turn it back on. Removing the Manager now says so: a notification with a **Turn on** button for each logged-in user it applies to, and a line in the terminal (dnf / apt / pacman, `uninstall.sh --manager-only`) with the command to run
- Release pages: the note at the top now says what each package does, that either works alone, and how to turn update notifications on or off; its *Already have the fix?* part says the Manager's **Update** downloads the files for what you have installed (not always both), and how to update the driver when it's installed without the Manager

## 2.3.1 — 2026-10-28

- **Update notification stays on screen:** until you click a button or close it
- The new-release notification is sent as critical, so desktops such as Ubuntu keep it on screen instead of shrinking it away after a moment, and its buttons keep working however long it waits (they stopped after an hour)

## 2.3.0 — 2026-10-28

- **Hourly update check:** a notification for each new release, with *Open GitHub* and, with the Manager, *Open Fingerprint Manager*
- New releases are checked for about every hour while you're logged in (10 minutes after login, then hourly), not only at login, and with either package installed: each package has its own user timer, and the driver's is skipped while the Manager is installed, so only one runs. The notification comes once per version, with **Open GitHub** (that release's page) and, when the Manager is installed, **Open Fingerprint Manager**. The Manager's *Check for new versions* still turns it off
- The on / off switch for update checks is the timers themselves, per user, instead of a line in the Manager's settings: *Check for new versions* masks or unmasks both timers (or disables / enables them for an `install.sh` copy), and with only the driver `systemctl --user mask` / `unmask fingerprint-fix-sdcp-update-check.timer` does it. A choice made with the old setting is carried over once

## 2.2.0 — 2026-10-28

- **Install either part on its own:** the driver no longer needs the Fingerprint Manager, and the Manager never needed the driver
- The driver package *recommends* the Fingerprint Manager instead of requiring it (deb and rpm `Recommends`, Arch `optdepends`): installed from the release files, name both to get both (the release page's command does), or just one. The driver alone works with your desktop's fingerprint settings; it has no Manager window, monitor or boot check. Both packages turn fingerprint login on at the first install on a computer, whichever comes first, and only once (`/var/lib/samsung-galaxybook/fingerprint-login-set-up`), so the driver alone gets it too. `install.sh --driver-only` / `--manager-only` and `uninstall.sh --manager-only` (next to `--driver-only`) do the same for `install.sh` copies. The Manager's **Update** updates what is installed: both packages, or only the Manager
## 2.1.0 — 2026-10-27

- **Sensor tab always shown:** see how full the sensor's 10 slots are, next to your fingerprints
- Fingerprint Manager: the Sensor tab (every template on the sensor, its 10 slots, delete and wipe) is always shown next to Fingerprints; the menu option to show it is gone, and messages that pointed to that option now point to the tab
- **Full sensor warning:** enrolling when all 10 slots are taken says so, with an *Open Sensor tab* button
- Fingerprint Manager: enrolling a finger when all of the sensor's 10 slots are in use now warns before starting — *The sensor is full*, with **Open Sensor tab** to delete fingerprints you no longer need — instead of failing after the first touch. Re-enrolling a finger whose own template is still on the sensor isn't blocked (the sensor replaces it). If the sensor still reports full during enrolment, the same warning appears
- **New fingerprint icon:** a more detailed print, which fills blue as you enrol and when you test a finger
- Fingerprint Manager: a new, more detailed fingerprint drawing on the finger cards and list (a simpler one at small sizes). Enrolling shows it filling blue from the centre outwards with each accepted touch, flashing amber when a touch can't be used, and green when done; testing shows it grey while waiting, filling blue when the finger is read, then green for a match or red for no match. It replaces the pointing-hand symbol
- **Intel/AMD only:** nothing installs on ARM laptops such as the Galaxy Book4 Edge
- `install.sh`, the `.rpm`, the `.deb` and the Arch release `PKGBUILD` refuse to install on a computer whose processor isn't 64-bit Intel/AMD (`x86_64`), saying so — e.g. the Snapdragon (ARM) Galaxy Book4 Edge, which this fix has never been tested on. The Fingerprint Manager package is architecture-independent, so it could install there before; the driver package never could. `FPRINT_SDCP_FORCE=1` installs anyway

## 2.0.1 — 2026-10-27

- The "Fingerprint Login Is Off" notification named a switch the Fingerprint Manager doesn't have ("Use fingerprint for login and sudo"); it now points to the switch at the top of the Manager, whatever your distro calls it
- Turning fingerprint login on during a package install no longer prints colour codes like `[0;32m[INFO][0m` in the install output

## 2.0.0 — 2026-10-27

- **Two packages:** the driver (`fingerprint-fix-sdcp`) and the Galaxy Book Fingerprint Manager (`galaxybook-fingerprint-manager`, with the monitor and the boot and login checks), built from one source with the same version. The driver needs the Manager of its own version; the Manager works without the driver, so once your distro's libfprint handles the reader with SDCP you can remove just the driver (`sudo dnf remove fingerprint-fix-sdcp`, `apt remove`, `pacman -R`, or `sudo bash uninstall.sh --driver-only`) and keep the Manager, its checks and fingerprint login. Each release has both packages for each distro (the Manager as `noarch` / `all`), and the Arch `PKGBUILD` builds both. To upgrade from 1.x, install both packages together, or use the Manager's **Update** (from 1.5.0): the units stay enabled and fingerprints are kept
- The Manager lives in `/usr/lib/galaxybook-fingerprint-manager/` (packages) or `/usr/local/lib/galaxybook-fingerprint-manager/` (`install.sh`), with its own install marker and cleanup script; the driver keeps its folder
- Packages turn fingerprint login on (lock screen, sudo, admin prompts) on the first install on a system, as `install.sh` does — on Arch too, where `install.sh` asks. `FPRINT_PAM=0` skips it. Upgrades and reinstalls keep what you set in the Manager
- Removing the fix never turns fingerprint login off, on any distro: the Arch package and `uninstall.sh` no longer take out the sudo / polkit-1 lines. Once your distro's libfprint has SDCP and you switch to it, fingerprint login keeps working

- Boot-time sensor check: rewritten in Python (`lib/sensor-check.py`, replacing the C program), using whichever libfprint drives the reader, so it keeps working with your distro's driver
- Fingerprint Manager: without the driver, the info line says *Driver: your distro's libfprint* and *Test your distro's driver* is hidden; **Remove the driver** keeps the Manager open
- Fingerprint Manager: with Ubuntu's libfprint (libfprint-tod), e.g. after removing the driver, its helper no longer crashes when reading the sensor (libfprint-tod aborts if a program sets it up twice); and if the helper ever does crash, the Manager says so, with what it printed under **Details…**, instead of "Expecting value: line 1 column 1"

- Fingerprint Manager: testing fingerprints repeats by itself — after a match or no match, the result stays up for 2 seconds ("Testing again in 2…"), then it waits for the next touch, until you press **Close**. The **Test again** button is gone. After no touch for 60 seconds it stops. **Test all fingerprints** is now called **Test any fingerprint**, and a match names the finger as *Right ring finger*
- Fingerprint Manager: the test window keeps one size (440 × 320) while it waits for a touch, shows the result and counts down, so its button doesn't move

- `install.sh` stopped without a word at Step 3 (checking the distro's libfprint) on most systems — whenever the check's answer wasn't `sdcp` — since 1.4.1. It now carries on with the install

## 1.5.1 — 2026-10-27

- Fingerprint Manager: the text in its dialogs is aligned left instead of centred, so lists of fingers and paragraphs line up

- Fingerprint Manager: shorter dialogs — each says what matters in a line or two, with paths, how it works and caveats under **More details**; *Details…* on a message is titled with that message

## 1.5.0 — 2026-10-27

- Fingerprint Manager: **Update** is ready for releases with two packages — the driver (`fingerprint-fix-sdcp`) and the Manager (`galaxybook-fingerprint-manager`), planned for 2.0.0 — and downloads both into `~/Downloads/fingerprint-fix-sdcp-<version>/` to install together (`sudo dnf install ./*.rpm`, `sudo apt install ./*.deb`, or `makepkg -si`), or only the Manager once the driver has been removed. Releases with one package work as before. Update to this version before 2.0.0 comes out: older Managers can't install a two-package release by themselves

- Notifications whose next step is in the Fingerprint Manager — **Your Distro Now Supports the Fingerprint Reader**, **Fingerprints From Another Driver** and **Fingerprint Removed From Sensor** — have an **Open Fingerprint Manager** button, on desktops whose notifications support buttons
- Fingerprint Manager: when *Test your distro's driver* matches, **Remove fingerprint-fix-sdcp** removes the fix the way it was installed (`dnf` / `apt-get` / `pacman`, or an `install.sh` copy's own cleanup), keeping your fingerprints, and closes the Manager; **Copy command** gives the command instead. When it doesn't match, it explains how to delete your fingers first so they don't stay on the sensor after switching

- The Galaxy Book3 isn't supported: it can have the same `1c7a:05a1` reader as the Book4, but hasn't been tested. `install.sh`, the `.rpm`, the `.deb` and the Arch release `PKGBUILD` refuse to install on a Book3 (pacman's install script warns), recognised by its model name or model code (`…XF…` / `…QF…`); `FPRINT_SDCP_FORCE=1` installs anyway. README, package descriptions and the Fingerprint Manager say Book4 and Book5

- Distro-driver check: when libfprint's Python bindings are missing (e.g. Ubuntu without `gir1.2-fprint-2.0`), the `error` answer says what to install; its description no longer suggests it's purely read-only (libfprint opens the reader while listing it, and may set its USB power "persist" setting). Confirmed on a Galaxy Book4 (`1c7a:05a1`, Ubuntu 26.04, libfprint 1.95.1+tod1): Ubuntu's own driver answers `plain` — it handles the reader without SDCP — thanks to Andy

- Another fingerprint fix's fprintd setup is moved aside when installing — most often a manual install of Abdallah's libfprint-egismoc-sdcp from its README, which uses the same `/usr/local/lib/libfprint-egismoc-sdcp/` folder as `install.sh` (so `install.sh` overwrote its library and `uninstall.sh` deleted it, leaving its drop-in pointing at nothing), or any admin fprintd drop-in that sets `LD_LIBRARY_PATH` / `LD_PRELOAD` or replaces `ExecStart`. It goes to `/var/lib/samsung-galaxybook/other-fingerprint-fix/<date>/` with `RESTORE.txt`; fingerprints are kept. `install.sh`, the `.rpm`, `.deb` and Arch package all do this; another package's drop-in is only reported
- Monitor: notifies when fprintd isn't running this fix's driver, naming any other fix's setting that overrides it

- Distro-driver check: finds which package manager owns libfprint by asking each one, instead of guessing from which are installed — on Fedora with `dpkg` also installed (e.g. for building `.deb`s) it asked `dpkg`, and called Fedora's own libfprint "not part of any package"
- Distro-driver check: when the reader is on USB but libfprint doesn't list it, it says `unknown` instead of `none` — some libfprint builds open the reader while listing it, which needs root. The Fingerprint Manager now asks its root helper for the check instead of running it as you

- README: the Fingerprint Manager section covers the **Other driver** fingers, the Windows reminder, *Test your distro's driver* and the no-reader message; *Files Installed* lists the new status files and says what the cleanup script is for now

## 1.4.1 — 2026-10-26

- Fingerprint Manager: no lines between the options of the right-click menus
- The distro-driver check now also asks the package manager where the library came from (`rpm`, `dpkg` / `apt-cache`, `pacman`). Only the distro's own, unmodified libfprint package counts as "your distro now supports the reader". An SDCP build from another fix — copied over the distro's file, not owned by any package, or from a COPR, PPA, the AUR or a local package — gets "Another fingerprint fix is installed — keep this fix" from the monitor, the Fingerprint Manager and `install.sh`, and the Manager doesn't offer to remove the fix

## 1.4.0 — 2026-10-26

- When a distro libfprint update brings an SDCP driver for the reader, the monitor says so once and points to the Fingerprint Manager's new **Test your distro's driver** (menu), which checks one of your enrolled fingers with the distro's driver through fprintd — the way login would work without the fix — and gives the remove command if it matches. The Manager also shows this when it opens. The fix no longer removes itself (an `install.sh` copy did, without checking your fingerprints still worked)
- The check for that is new (`lib/distro-driver-check.py`): it asks the distro's libfprint whether its driver for the reader is an SDCP driver, without stopping fprintd or touching the sensor. The monitor used to stop fprintd for up to 10 seconds and test only whether the sensor was listed — which the distro's older, non-SDCP egismoc driver passes on `1c7a:05a1`
- `install.sh` Step 3 uses the same check, so it no longer stops with "probably not needed" on `1c7a:05a1` laptops, where the distro's egismoc driver lists the reader but can't keep prints
- Fingerprint Manager: when Windows is installed on the laptop, a reminder at the bottom of the window to disable the fingerprint reader in Windows (Windows Hello deletes Linux fingerprints when it starts with the reader enabled), with the steps in its tooltip. Found from the UEFI boot entries and Windows' partitions, without a password; **Got it** hides it, *Menu → Remind me about Windows* brings it back
- Fingerprints enrolled with another driver (e.g. the distro's own egismoc driver before this fix, which saves non-SDCP prints) are recognised: the Fingerprint Manager marks them **Other driver** with a warning and a *Delete them* button, and right-click → *Delete and enrol again* deletes the old template from the sensor (freeing its slot) and starts enrolling. They used to show as *Gone from sensor*
- Boot check: no longer moves those fingerprints aside as "removed from the sensor" with a message blaming Windows; the login check says once which fingers were enrolled with another driver

## 1.3.5 — 2026-10-26

- Packages are only for a Samsung with the Galaxy Book's Egis reader (`1c7a:05a5` / `1c7a:05a1`): on other hardware the `.rpm` and `.deb` stop before installing anything, saying why (`FPRINT_SDCP_FORCE=1` installs anyway, e.g. for a system image), and pacman warns
- fprintd uses the fix's driver only while that reader is present: the drop-in checks each time fprintd starts, so on any other hardware (a moved disk, a forced install) fprintd keeps the distro libfprint and its drivers, and other fingerprint readers keep working
- Fingerprint Manager: without that reader, explains that the app is for the Galaxy Book's reader and how to remove the fix, instead of asking for a password and failing
- `install.sh`: the Samsung check also accepts `board_vendor`, like the packages
- Arch-based distros: releases have a `PKGBUILD` (with `fingerprint-fix-sdcp.install`) to build with `makepkg -si`, and no longer a ready-made `.pkg.tar.zst` — built on your laptop against Arch's current libraries, so an Arch library update can't break it between releases. It stops before building on hardware without the Galaxy Book's reader (`FPRINT_SDCP_FORCE=1` builds anyway)
- Fingerprint Manager on Arch-based distros: **Download** fetches the new release's `PKGBUILD` into `~/Downloads/fingerprint-fix-sdcp-<version>/` and gives the `makepkg -si` command. Managers from 1.3.4 and earlier don't find a package in the new release and point to the release page instead

## 1.3.4 — 2026-10-26

- Fingerprint Manager: the hints on both tabs sit in a rounded card like the one above, so their text lines up; on the Sensor tab the slot count, bar and key share it

## 1.3.3 — 2026-10-26

- Fingerprint Manager: the sensor line is labelled — *Sensor · Serial · Driver commit*, with the version at the end
- Fingerprint Manager: clearer hints under the tabs — *Test: double-click · Enrol: click a grey finger · More: right-click*, and on the Sensor tab what green, grey, *Removed here* and dashed mean
- Fingerprint Manager: the fingerprint switch says what it covers on this system — *login, the lock screen and sudo* (GNOME, Mint), *the lock screen and sudo* (KDE, whose login screen can't take fingerprints), or *sudo and admin prompts* (Arch-based); the tooltip has the details
- Fingerprint Manager: shorter Update and Downloaded dialogs — the file to download, then what *Open folder* does and the install command (shown in a fixed-width font); *Open folder* is the default

## 1.3.2 — 2026-10-26

- Fingerprint Manager on Arch: when the fix was installed with `install.sh`, the install command after **Download** removes that copy first (pacman refused to install over its files), keeping fingerprints and fingerprint login
- `install.sh`: the Fingerprint Manager's icon goes in `/usr/share/icons` like its menu entry, so Cinnamon's menu shows it straight away (it didn't notice an icon added under `/usr/local/share/icons` until Cinnamon restarted); the old `/usr/local` copy is removed

## 1.3.1 — 2026-10-26

- Moving from an `install.sh` copy to the `.rpm` or `.deb`: the Manager's icon is no longer shown as a broken image (the old copy's icon cache in `/usr/local` is refreshed — by the package for copies installed before 1.3.1, and by their own cleanup from 1.3.1 on)
## 1.3.0 — 2026-10-26

- `install.sh` no longer looks for or migrates the old `fingerprint-fix` (nobody has it installed); its steps are renumbered
- Fingerprint Manager: notices when a new version is installed while it is open — from a software centre, `dnf` / `apt` / `pacman` or `install.sh` — and offers **Restart**; the download dialog says the file can also be installed by opening it
- Fingerprint Manager: after a download, **Open folder** and **Quit Manager** copy the install command and close the Manager, ready for the new version to be installed; Open folder brings an already open (or minimised) file manager to the front
- Fingerprint Manager: the *Update* button stands out more, with a red ring and a soft glow

## 1.2.1 — 2026-10-26

- README: Credits link to Abdallah Alkanani's libfprint-egismoc-sdcp; "Version built" describes the pinned `DRIVER` commit (it still described building the fork's newest commit)
- Fingerprint Manager and the login notification no longer use GitHub's API, which allows only 60 requests an hour per internet connection without a login (a used-up limit hid new releases). The newest version comes from the releases page, and Download finds and checks the package with the `SHA256SUMS` file now attached to each release

## 1.2.0 — 2026-10-26

- `uninstall.sh` always keeps enrolled fingerprints; it no longer offers to delete them (an accidental *y* also wiped the templates on the sensor). Delete fingers in the Fingerprint Manager instead
- `.deb`: removing the package and installing it again turns the boot check and login check back on
- README: installing and removing the packages comes first; `install.sh` for other distros and testing
- Fingerprint Manager: checks for a new version each time it starts (instead of at most once a day). *Update* offers **Download**, which saves the package for this distro and release in Downloads, checks it against GitHub's checksum and shows the command to install it, and **View on GitHub**

## 1.1.2 — 2026-10-26

**Driver:** unchanged, libfprint-egismoc-sdcp `3b0ee1f`.

### Releases

- Packages are built and the GitHub release is made automatically when a version tag is pushed
- Fedora packages build again (they needed `gcc-c++`)
- Arch: no separate debug package in the downloads
- Galaxy Book 4 with the `1c7a:05a1` sensor confirmed working (firmware 9050.1.2.33) on Zorin OS 18.1 (Ubuntu 24.04 base)

### Packages

- `.rpm` (Fedora 44 / 45), `.deb` (Ubuntu 24.04 / 26.04 and Mint, Debian 13 and MX) and Arch, installed under `/usr` — one per distro release, built and attached to each GitHub release automatically, with a PKGBUILD for building from source (`packaging/README.md`)
- Scripts and units that `install.sh` used to write inline are now real files in `packaging/files/`, shared by `install.sh` and the packages; their paths are in `lib/fixpaths.sh`. `install.sh` writes the same files as before
- The Manager, its helper and the export / import tools find the fix whether it was installed by `install.sh` or as a package

### Notifications

- New releases: at login, one notification per newer release on GitHub; in the Fingerprint Manager, an *Update* button with how to update for the way the fix was installed. One check a day shared by both (`lib/update_check.py`); menu → *Check for new versions* turns both off
- Hints at login, once each, with an *Open Fingerprint Manager* button: enrol a finger (none enrolled yet), or turn on fingerprint login (fingers enrolled but login still asks for the password). The packages show them right after installing too

### Fingerprint Manager and tools

- Larger, clearer text in the top card and tips; a › before right-click menu options; more right-click options, and a right-click menu on the Sensor tab
- The Sensor tab recognises templates of fingers removed on this install (shown as that finger, *Removed here*, with *Restore*), and the Sensor list uses the same wording for unknown templates as the cards
- When administrator access is refused, it says so and offers to try again or close
- Import adds what's missing: fingers you already have are kept and only the missing ones are imported (`--replace` still replaces all); fingers no longer on the sensor are left out instead of refusing the whole file; `--fingers` imports only some. The Manager asks *add the missing ones* or *replace all*, and offers on start-up to import fingers from `~/fingerprint-export.tgz` that this install lacks (once per export file)

### Fingerprint login

- Arch: admin dialogs (pkexec, graphical password prompts) take a typed password after at most 10 seconds instead of 30 (`arch-pam.sh`: polkit-1 gets `timeout=10`; package upgrades update existing lines)
- Fingerprint login check: commented-out `pam_fprintd` lines no longer count as enabled (Arch status and enable, Debian status)

## 1.0.0 — 2026-10-25

First release as its own repository (previously `extras/fingerprint-fix-sdcp` in Samsung Galaxy Book Fixes).

**Driver:** libfprint-egismoc-sdcp `3b0ee1f` (25 October 2026), which includes the SDCP key-derivation fix for OpenSSL 3.0/3.1 (Ubuntu 24.04 and its derivatives, e.g. Linux Mint 22).

- Builds only the egismoc SDCP driver and points fprintd at it; the distro's libfprint is not replaced
- Each release builds one tested driver commit (`DRIVER`); `VERSION` and the driver commit are recorded at install and shown in the Fingerprint Manager
- Galaxy Book Fingerprint Manager: ten-finger view, test / enrol / remove with right-click menu and Undo, sensor view (optional), export / import, fingerprint login on/off
- Monitor and boot-time check that notice when the sensor loses a fingerprint (e.g. after booting Windows)
- Sharing one enrolment between several Linux installs (export / import)
- Tested on a Galaxy Book 5 Pro 14" (940XHA, `1c7a:05a5`): Fedora 45, Ubuntu 26.04, Linux Mint 22.3 and 27 (beta), MX Linux, CachyOS
