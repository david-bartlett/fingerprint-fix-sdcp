# Add a guide for using the driver on its own

PR #139 · Claude · 2026-11-02

## What changed
- New guide `docs/driver-only.md`, first in the README's Documentation table: what you get without the Manager, enrolling, fingerprint login, updating, Windows, other distros, adding the Manager and removing the driver.
- `PLAN.md`'s list of guides includes it.

## Why
- David wanted a guide for people who install only the driver. Those steps were spread across the other guides.

## Tested
- Checked what the driver package ships in `packaging/install-files.sh`, the rpm spec and `lib/fixpaths.sh`, including the path `/usr/lib/fingerprint-fix-sdcp/pam/fingerprint-pam.sh`.
- Links and anchors checked by script. One anchor, `../README.md#with-only-the-driver`, only exists once #138 is merged.
- Not tested: any of the guide's commands on a driver-only install.

## For the next person
- This repeats a few facts from other guides, so a change to what the driver package ships may need a change here too.
- README and docs only, so no CHANGELOG line.
