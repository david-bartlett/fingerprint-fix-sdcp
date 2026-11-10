# One list of accepted readers, checked at release

PR #177 · Claude · 2026-11-10

## What changed
- `lib/fixpaths.sh`: `FPRINT_READERS="05a5 05a1 0582"`, the list every reader check must match.
- New `tools/dev/check-readers.sh`: finds every reader check in its four forms and fails if one accepts different readers, or if one of the 16 files that should have a check has none.
- The release workflow's `check` job runs it, before anything is built.
- The `=~ ^(05a[15]|0582)$` checks are written out as `^(05a5|05a1|0582)$`, so the script can read them.
- PLAN.md §10, `tools/dev/README.md`.

## Why
- Adding `0582` (PR #175) meant 17 copies in 16 files. Missing one fails silently, as Ralf's manual install showed with the drop-in. David asked for one list without a single point of failure. Generating the copies would change four build routes and the release assets, so each copy stays, and this checks them.

## Tested
- On the repo: OK, 17 checks in 16 files.
- On a copy: a copy missing `0582` fails, naming the line; a reader added only to the list fails, naming all 17; a check rewritten as `in READERS` fails, naming the file; the list deleted fails; and it works from another folder.
- `shellcheck`, `bash -n`, the workflow parses as YAML. Not here: a real workflow run.

## For the next person
- Messages and docs that name the readers aren't checked: update them by hand.
- A new check in a fifth form won't be seen. Write it in one of the four, or add a pattern to the script.
- No CHANGELOG line: nothing users see changes.
