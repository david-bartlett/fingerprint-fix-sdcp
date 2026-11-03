# Explain installing only the driver on Arch

PR #147 · Claude · 2026-11-03

## What changed
- `docs/install-options.md` has a new *Only the driver on Arch* section, and the README's Install section points to it.

## Why
- David found it confusing: the README says to leave out the Manager's file, but Arch has no separate file, and `makepkg -si` installs both.

## Tested
- Links and anchors checked by script. The commands are the ones already in the guide. Not confirmed on EndeavourOS when this was written.
