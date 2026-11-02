# Make the README's Updating section clear for both installs

PR #138 · Claude · 2026-11-02

## What changed
- The README's *Fingerprint Manager Updating* section is now *Updating*, with a table comparing the driver alone with the driver and Manager, then a section for each, and one for `install.sh` copies.
- The note saying a driver-only install gets no notifications is gone, as the driver has its own update check.
- `PLAN.md`'s file map follows the README's order.

## Why
- David asked for it to be clearer which update steps apply to which install.

## Tested
- Read the packaging, `lib/update_check.py` and `lib/notify-update.sh` for what each install does.
- Links and anchors checked by script.
- Not tested: a driver-only install on real hardware.

## For the next person
