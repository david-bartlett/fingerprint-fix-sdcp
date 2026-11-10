# Guide for testing on unconfirmed hardware

PR #NUMBER · Claude · 2026-11-10

## What changed
- New `docs/untested-hardware.md`: an own-risk warning, what to check first, which checks refuse an install and how `FPRINT_SDCP_FORCE=1` turns them off for each install method, how to check it works, and reporting back.
- README's guide table, PLAN.md's list of guides.

## Why
- David wants people who choose to test on unconfirmed hardware to have one place to read, and to make clear he isn't responsible if they force it.

## Tested
- Checked against the code: the packages' `fix_hardware_problem()`, `install.sh`'s `check_hardware` and reader check (no override for "not a Samsung" or "no reader"), and the Arch `prepare()` and `pre_install()`.
- Docs only.

## For the next person
- `docs/supported-hardware.md` should link to this guide in its Book3 paragraph. Not done here, as PR #171 changes that paragraph.
- On Arch, `pre_install` only warns, so `FPRINT_SDCP_FORCE=1 makepkg -si` is enough even though `sudo` drops the variable.
