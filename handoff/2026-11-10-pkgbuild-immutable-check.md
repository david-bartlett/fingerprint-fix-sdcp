# Fix the PKGBUILD's immutable check

PR #NUMBER · Claude · 2026-11-10

## What changed
- `packaging/arch/PKGBUILD.release.in`: `prepare()` checks `/usr`'s mount options with `findmnt` instead of `! -w /usr`.
- PLAN.md §10, CHANGELOG.

## Why
- 2.14.0 refused every Arch system: David's EndeavourOS update stopped with *this is an immutable system*. `makepkg` runs `prepare()` as the user, who can't write to `/usr` anywhere. PR #176 was meant to use `findmnt` here, but that edit was in a command that never ran, and the tests ran `prepare()` as root, so they missed it.

## Tested
- The generated `PKGBUILD`, `PKGBUILD-driver` and `PKGBUILD-manager`, with `prepare()` run **as a normal user** and a fake Samsung and reader: a normal system builds, `/run/ostree-booted` refuses, and a real read-only bind mount for `/usr` refuses.
- 2.14.0's released `PKGBUILD` under the same test refuses the normal system too, matching David's report.
- Not here: a real `makepkg -si`.

## For the next person
- The deb, rpm and Arch `.install` checks and `install.sh` run as root, so `-w /usr` is right there.
- Anything that runs as the user must not test `-w` on system paths.
