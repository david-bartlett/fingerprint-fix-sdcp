# Correct what the docs say about the PAM scripts

PR #140 · Claude · 2026-11-02

## What changed
- The README's safety list and `PLAN.md` §10 said the PAM scripts back up and verify what they change. Only `arch-pam.sh` keeps a backup. Both now say what the scripts do.

## Why
- Found by reading `tools/fingerprint-pam.sh` and `tools/arch-pam.sh`. Fedora and the Debian family use `authselect` and `pam-auth-update`, and the script checks the result afterwards.

## Tested
- Compared the wording with both scripts. Docs only, so nothing was run.

## For the next person
- `pam-auth-update --force` is used on the Debian family, so the promise that hand edits are left alone only applies to Arch.
- README and PLAN only, so no CHANGELOG line.
