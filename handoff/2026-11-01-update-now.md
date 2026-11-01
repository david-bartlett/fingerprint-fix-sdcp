# The new-version notification's Update now

PR #124 · Claude · 2026-11-01

## What changed
- `lib/update_check.py`: `installed_package()` (the Manager package's format and distro from dpkg / rpm / pacman: `2.10.2-1~ubuntu26.04` → deb ubuntu26.04, release `1.fc45` → rpm fc45), `can_update_now()`, `update_now(VERSION)` (opens `terminal.find_terminal()` running `update_check.py --install VERSION`), `install(VERSION)` (prints the title, `pick_asset` with the driver markers, downloads and checks each file into `/tmp/galaxybook-update-VERSION-*`, then `exec update-in-terminal.sh` with `install_command`; on a problem it says why, points to the release page and waits for Enter). New CLI options `--can-update-now`, `--update-now VERSION`, `--install VERSION`. `notify_once()` passes the version, and a text whose first line is *You have X.Y.Z.*
- `lib/notify-update.sh`: buttons **Update now** (when `--can-update-now`) and **What's new**; re-shown after What's new; GNOME click = What's new; with buttons only the first line of the text. *Open Fingerprint Manager* removed from it.
- `lib/update-in-terminal.sh`: skips printing the title when `TITLE_SHOWN` is set (`--install` printed it before the downloads).
- README (Updating), PLAN.md §4, CHANGELOG.

## Why
- David: galaxybook-fan's **Update now** goes straight to a terminal; fingerprint-fix-sdcp's notification opened the Manager, then Update. He agreed to the mock-up: Update now / What's new, driver alone and install.sh copies get only What's new.

## Tested
- `installed_package()` with stand-ins for dpkg / rpm / pacman (Ubuntu, Fedora, Arch, none). `install("2.10.3")` with stand-in assets and downloads on Fedora: both fc45 packages, `cd /tmp/galaxybook-update-2.10.3-…/fingerprint-fix-sdcp-2.10.3 && sudo dnf install ./*.rpm` handed to `update-in-terminal.sh`.
- `notify-update.sh` with stand-ins: KDE (What's new → page, re-shown; Update now → `--update-now 2.10.3`), GNOME (helper, click line, click → What's new), no Update now when `--can-update-now` fails. shellcheck, `bash -n`, `py_compile`.
- David on Fedora 45 KDE: --can-update-now 0; What's new and Update now from the notification (Konsole, downloads checked, dnf) work; the branch built and installed.

## For the next person
- Installed copies get this from the release after the one with it, as the notification is drawn by the installed version.
