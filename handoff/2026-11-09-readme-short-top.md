# README top: the two packages, no multi-distro warning

PR #168 · Claude · 2026-11-09

## What changed
- `README.md`: the Important note lost its multi-distro bullet and now explains the two packages (driver, Galaxy Book Fingerprint Manager) the way the release page does, then says the software can also be installed by cloning the repo and running `install.sh` (links to `docs/install-options.md`).
- `README.md`: the Install section no longer repeats the two-package explanation; the Multi-Distro Mode row in the Documentation table now says to enrol a finger once.
- `docs/multi-distro.md`: starts with the "don't enrol the same finger on each distro" warning, which used to be in the README.

## Why
- David wants someone visiting the repo to see what it is quickly, and the multi-distro detail belongs in its own guide.

## Tested
- Checked the rendered Markdown structure and that the new anchors (`#other-distros-installsh`, `#only-one-package-on-arch`, `#sharing-fingerprints`) exist.
- Not seen in a browser.

## For the next person
- The README is about the same length as before (the package explanation moved up rather than going). Updating and Uninstall are the bulk left; moving them to `docs/` is David's call.
- `docs/install-options.md` now has a section for Fedora, Ubuntu, Debian and derivatives (download the two files, the command per distro, `FPRINT_PAM=0`, updating, removing). It only had Arch, one package and `install.sh`.
