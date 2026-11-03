# A failed import starts fprintd again

PR #160 · Claude · 2026-11-03

## What changed
- `tools/import-fingerprint.sh`: the `EXIT` trap starts fprintd again if the script stopped it and hasn't restarted it.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding (third pass), confirmed on `6646873`. fprintd is stopped for the sensor check, and its restart is at the end, so a failed `mkdir`, `mv` or `install` under `set -e` left it stopped.

## Tested
- The trap, sensor check and install block from the real script, with the system stood in: a normal run, `install` failing, `mkdir` failing, and `--no-check` with `install` failing (fprintd left alone).
- `bash -n`.
- Not here: a real import.

## For the next person
- A `--replace` that fails after moving the old records aside still leaves them in `replaced-fingerprints/`, where **Restore** can bring them back. Not changed here.
