# Refuse immutable distros

PR #NUMBER · Claude · 2026-11-10

## What changed
- Every hardware check (rpm `%pre` for both packages, both deb preinsts, both Arch `.install` files, the PKGBUILD `prepare()`, `install.sh`) refuses when `/run/ostree-booted` exists or `/usr` isn't writable. The PKGBUILD reads the mount options, as makepkg runs as the user. `FPRINT_SDCP_FORCE=1` overrides it, as for the other checks.
- Docs: Supported hardware and the untested-hardware guide. PLAN.md §10, CHANGELOG.

## Why
- Issue #174 was on Fedora Silverblue, where the packages don't fit: `/usr` is read-only and rpm-ostree layers packages into an image. David chose not to support immutable distros.

## Tested
- Each check with a fake Samsung and reader: a normal system installs, `/run/ostree-booted` refuses, and a real read-only bind mount standing in for `/usr` refuses.
- `bash -n`, `sh -n`, the release PKGBUILDs generated.
- Not here: a real Silverblue or SteamOS.

## For the next person
- rpm-ostree runs package scripts in a sandbox while building the image, so `/run/ostree-booted` may not be visible and `/usr` may be writable there. The RPM's check may not fire under `rpm-ostree install`. Someone with Silverblue would need to confirm it.
