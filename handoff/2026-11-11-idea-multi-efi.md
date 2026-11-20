# Idea and plan: more than one EFI partition

PR #180 · Claude · 2026-11-11 (plan added 2026-11-17)

## What changed
- PLAN.md §11 (Ideas not done yet): multi-EFI partition support, with conflict resolution for the `EFI/samsung-galaxybook/` copies on each.
- `plans/multi-efi.md` (new): the full plan. It covers finding every EFI partition, which copies are read and written, the merge rules (newest `seen_at` wins, tombstones for forgotten installs, each install the authority on its own entries), damaged, unreachable and disconnected copies, backing up the merged view, and restoring from several backup files with a preview. It also covers testing with a loop-device EFI partition, the order of PRs, and six questions for David.
- PLAN.md §4: a `plans/` row in the top-level file map.

## Why
- David asked for it on the to-do list, then for the plan. Nothing is built yet. Get answers to the questions at the end of the plan before starting.

## Tested
- Nothing to run: documents only. Checked that `lsblk` (util-linux 2.39) gives every column the plan uses (`PARTTYPE`, `RM`, `HOTPLUG`, `TRAN`, `PKNAME`).

## For the next person
- `shared_slots.esp_dir()` is the one place that picks the EFI partition today. The plan's first PR (merge rules, `seen_at`, tombstones) changes nothing for users and can land before the multi-partition parts.
