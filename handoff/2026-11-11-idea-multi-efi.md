# Idea: more than one EFI partition

PR #180 · Claude · 2026-11-11

## What changed
- PLAN.md §11 (Ideas not done yet): multi-EFI partition support, with conflict resolution for the `EFI/samsung-galaxybook/` copies on each.

## Why
- David asked for it on the to-do list. Nothing is built yet; ask him before starting.

## Tested
- Nothing to test: PLAN.md only.

## For the next person
- `shared_slots.esp_dir()` is the one place that picks the EFI partition today. `merge_backup` already merges a backup into the file without changing what's there, which may be a starting point, but it doesn't resolve conflicts.
