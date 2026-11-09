# Galaxy Book4 Ultra confirmed on Ubuntu 26.04

PR #169 · Claude · 2026-11-09

## What changed
- `docs/supported-hardware.md` and README's *Supported Hardware*: Galaxy Book4 Ultra (960XGL, `05a1`) on Ubuntu 26.04 added as confirmed, with the details in the `05a1` row.

## Why
- A tester installed both 2.13.6 `.deb`s on that laptop on 9 Nov 2026: checksums matched, fprintd loaded the fix, enrol with the Manager, verify and the lock screen worked, and fingerprint login was switched on.

## Tested
- Docs only.

## For the next person
- That sensor had one more template than records, probably from an old stock-egismoc enrolment (a raw record under `egismoc/0/`) or from Windows, which is no longer on the disk. Expected, not a bug: the Sensor slots tab shows it in grey.
