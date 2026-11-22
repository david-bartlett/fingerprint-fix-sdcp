# Plan: one shared file on the drive's EFI partition

PR #184 · Claude · 2026-11-22

## What changed
- `plans/multi-efi.md` rewritten. The first version (PR #180) kept a copy on every EFI partition in step, with merge rules, tombstones and a multi-file restore. The new plan has one file instead:
  - It's on the drive the distro runs from, on whichever of the drive's EFI partitions already has it, or else the first by partition number.
  - A partition this distro doesn't mount is opened by a short-lived child process (`unshare --mount`) for each read or write, never held mounted. It's read-only to read; to write, there's a FAT clean check first, then read-write, write, unmount. David asked for the safest way.
  - No joining of existing copies; no other drives.
  - Other copies on the drive are renamed to `fingerprint-slots.ignored.json`. There's no Move button: someone changing their EFI partition moves everything across themselves (both David's decisions, 22 Nov).
- PLAN.md §11: the multi-EFI bullet now describes the new plan.

## Why
- David's call: the Galaxy Book3, Book4 and Book5 have one NVMe slot. A removed drive means no boot, and a replaced one is what Back up & restore is for. He'll delete the extra copy on EndeavourOS's EFI partition himself.
- Keeping the location in `~/.config/…/settings` was considered and dropped: it's per user and per distro, and the location has to be the same for all of them, so the file marks its own location.

## Tested
- Nothing to run: documents only. Checked that util-linux 2.39 lsblk gives the columns the plan uses.

## For the next person
- No questions left: the decisions are at the end of the plan. Ask David before starting the implementation PR.
- The notes in the PR #180 handoff note about merge rules and the older plan are out of date.
