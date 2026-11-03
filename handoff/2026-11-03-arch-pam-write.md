# Arch: replace PAM files in one step

PR #159 · Claude · 2026-11-03

## What changed
- `tools/arch-pam.sh`: new `write_pam()` writes a copy beside the PAM file with the same owner, mode and SELinux label, checks it, then moves it into place. Enable, update and disable all use it.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding (third pass), confirmed on `6646873`. `cat "$tmp" > "$f"` empties the live file first, so a failed write left `sudo` or polkit with an empty or partial PAM file.

## Tested
- The real script with paths pointed at a temporary folder and its fprintd checks stood in: enable, disable (back to the original byte for byte), owner and mode kept, a write failing part way on enable and on disable (file unchanged, no leftover copy, warns), and `/etc/pam.d/sudo` being a link (stays a link, target updated).
- The old code under the same failure left a 5-byte file out of 97.
- `bash -n`, `shellcheck`.
- Not here: real PAM on Arch, and SELinux.

## For the next person
- The copy is a dot file in `/etc/pam.d` for a moment. PAM only reads files by service name, so it's ignored.
