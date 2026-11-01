# Release page: What's new at the top, 1. Install, 2. Update

PR #<n> · Claude · 2026-11-01

## What changed
- `.github/release-notes.sh`: the box at the top of `.github/release-install.md` (before its first `## `), then *What's new* (+ *Full changelog* collapsed), then the rest. Was: all of `release-install.md`, then *What's new*.
- `.github/release-install.md`: the box keeps what the two packages are, and *Already installed? See 2. Update*; its update-notification and Manager-Update paragraphs moved to a new **2. Update** (`galaxybook-fingerprint-manager update`, the Manager's Update, `updates check`, driver only; the command table and the driver-only timer commands collapsed), *Install* became **1. Install**, and a `SHA256SUMS` line at the end, as galaxybook-fan's.
- PLAN.md §4 (.github rows), CHANGELOG.

## Why
- David: *What's new* up the top, and both repos' release pages alike (galaxybook-fan's has numbered sections and an Update section; its PR does the same reordering).

## Tested
- `bash .github/release-notes.sh 2.10.4`: box, What's new, Full changelog, 1. Install, 2. Update (with the command table), SHA256SUMS.

## For the next person
- Keep the box first and start each section with `## `: the script splits on the first `## `.
