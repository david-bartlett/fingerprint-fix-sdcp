# Update now and a command with only the driver

PR #143 · Claude · 2026-11-03

## What changed
- A driver installed from a package without the Manager now gets **Update now** in its notification. It downloads just the driver's file (on Arch it builds both packages and installs just the driver).
- New command `fingerprint-fix-sdcp` (`packaging/files/fix-command.sh.in`): `update` and `updates on|off|status|check`. With the Manager installed it changes nothing and names the Manager's command.
- The driver's update folder now also ships `terminal.py`, `update-in-terminal.sh` and the Manager's icon. `notify-update.sh` uses that icon by its path when the icon theme doesn't have it.
- `update_check.py`: `manager_installed()`; `installed_package()` looks at the driver's package when there's no Manager; `pick_asset()` and `install_command()` have a driver-only case; `enabled()` reads the driver's timer with no Manager; messages name `GBF_COMMAND`.
- README, `docs/driver-only.md`, `docs/how-it-works.md`, `.github/release-install.md`, `PLAN.md` and the CHANGELOG.

## Why
- David asked why a driver-only install couldn't update itself, as it only needs one file.

## Tested
- With stand-ins for `rpm`, `systemctl`, the terminal and the release files: the file picked for rpm, deb and Arch, `--can-update-now`, the whole of `install()` with and without the Manager, an `install.sh` copy being refused, the command's output with and without the Manager, and `updates off` and `status` with the driver's timer.
- `pick_asset()` and `install_command()` give the same results as `main` when the Manager is installed.
- `install-files.sh` run with a stand-in driver build: the command and helpers land where expected.
- `bash -n`, `py_compile`, links by script.
- Not tested: a real rpm, deb or Arch package (this repo's workflow only builds on a tag), real `dnf`, `apt` or `makepkg` runs, or the real notification.

## For the next person
- A `Recommends` on the Manager doesn't stop the driver's file installing alone, but `.github/workflows/release-packages.yml`'s header still says the driver requires the Manager, which isn't so.
- The `install.sh` layout has no command, so `FIX_BIN` is only set for the package layout.
- Driver-only installs on 2.11.4 or older have to update by hand once to get this.
