# Keep removed records when moving to a package

PR #155 · Claude · 2026-11-03

## What changed
- `packaging/files/mgr-cleanup.sh.in` no longer deletes `removed-fingerprints/`.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding 4, confirmed on `d57a002`. The packages run this cleanup when they replace an `install.sh` copy, so records the user could still restore were deleted, while `replaced-fingerprints/` was kept. `docs/manager.md` says records are kept while they can be restored.

## Tested
- Rendered for both layouts, `bash -n`.
- The rendered `local` script run in the sandbox with stand-in records: both folders' records stayed, and the libfprint hash still went.
- Not here: a real package migration.

## For the next person
- A full `uninstall.sh` still deletes both folders, and so does a Debian purge. That's deliberate: it's removing everything.
- `uninstall.sh --manager-only` runs this script too, so it now keeps the records, as removing a package does.
- An `install.sh` copy keeps the cleanup it was installed with until it's run again, so older copies still delete them on migration.
