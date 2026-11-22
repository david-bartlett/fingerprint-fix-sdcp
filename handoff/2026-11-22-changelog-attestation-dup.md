# CHANGELOG: one "Release files are attested" line

PR #188 · Claude · 2026-11-22

## What changed
- `CHANGELOG.md` Unreleased: the conflict resolution when merging PRs #185 to #187 left two **Release files are attested** lines, the corrected one (with `--signer-workflow` and `--source-ref`) and the old one (`-R` only). There's one now, the corrected text, in its own group, with blank lines between the groups again.

## Tested
- Read the Unreleased section; nothing else changed.
