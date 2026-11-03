# Separate Arch files for each package

PR #148 · Claude · 2026-11-03

## What changed
- `packaging/arch/write-release-pkgbuilds.sh` writes `PKGBUILD`, `PKGBUILD-driver` and `PKGBUILD-manager` from `PKGBUILD.release.in`. The Manager's has no `build()`, driver source or makedepends.
- The release workflow runs it, and checks each with `makepkg --printsrcinfo`.
- `update_check.py`: `pick_asset()` picks the package's own files with one package installed, and `install_command()` runs `makepkg -si -p <file>` when that file is there. A release without them works as before.
- README, `docs/install-options.md`, `.github/release-install.md`, `packaging/README.md`, `packaging/arch/README.md`, `PLAN.md`.

## Why
- David wanted Arch to work like rpm and deb, with one set of files per package. It also stops a Manager-only install compiling the driver.

## Tested
- `pick_asset()` and `install_command()` with stand-in release files, for all three install types on new and old releases.
- The three PKGBUILDs read back in bash: package names, sources, checksums and functions.
- `bash -n`, `py_compile`, links by script.
- Not tested when this was written: `makepkg` itself, which isn't available here, and the workflow, which only runs on a tag.

## For the next person
- Keep the plain `PKGBUILD`. Earlier versions' Update looks for that name, and it's the one build that installs both.
- Change `PKGBUILD.release.in`, not the generated files. The script stops if its edits no longer fit.
- Updates with one package use the new files from the release after this one's, as the update code comes with the installed version.
