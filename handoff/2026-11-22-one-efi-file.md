# One shared file on the drive's EFI partition

PR #185 · Claude · 2026-11-22

## What changed
- `lib/shared_slots.py`: `shared_esp()` picks the EFI partition for the shared file on the drive this install runs from: whichever already has it (lowest partition number if several), or else the first. That replaces `esp_dir()`, which is now only the fallback.
  - A partition this install doesn't mount is opened per read or write by `_child` (`--esp-read`/`--esp-write`/`--esp-rename`) through `unshare --mount`.
  - Before writing there: `fat_clean()` and an unchanged-since-read check.
  - Other copies are renamed to `fingerprint-slots.ignored.json` (`rename_others()`).
  - `_save`/`_load` go through `_Target`. Plain paths still work, for tests that replace `_path`.
- Helper status: `shared_renamed`, `shared_problem_dev`, and `esp` gains `dev`, `mounted`, `first` and `refused`.
- Window:
  - Back up & restore says which partition holds the file, and when a change couldn't be saved because another OS has it in use.
  - The warning for a damaged file on an unmounted partition gives mount, mv and umount commands.
  - A once-only message names renamed copies. It's joined to the "no longer on this laptop" message, as each message replaces the one before.
- Docs: `multi-distro.md` (new section), `troubleshooting.md`, `how-it-works.md`. PLAN.md §4, §6 and §10, and the §11 idea removed. `plans/multi-efi.md` is marked built.

## Why
- David's laptop: EndeavourOS has its own EFI partition, so it wrote a different file from Fedora's `/boot/efi` one. Neither saw the other, and EndeavourOS's Reset could have cleared Fedora's slots. Plan agreed in PR #184.

## Tested
- In a scratch folder outside the repo:
  - choice of partition with fake lsblk and sysfs (12 cases: one partition, file on an unmounted p1, on p9 only, none, unreadable p1, damaged p1, USB, removable, hotplug, no drive, MBR `0xef` through LUKS, not vfat), plus renaming and the 5 s cache
  - `fat_clean()` on real FAT12, FAT16 and FAT32 images, with Linux's flag and Windows' bit set by hand
  - `_child` read, write, changed, dirty, rename and wrong UUID, and `share_slots`, `used_elsewhere`, `esp_records`, `forget_installs` and a damaged file end to end through `unshare`, on an ext4 loop device standing in for FAT
  - the child refusing to run in its parent's namespace
  - nothing left mounted, and no folders left in `/run`
  - plain-path compatibility
- The window's dialog and messages under Xvfb.
- **Not tested:** a real vfat mount, because the sandbox kernel has no vfat driver. Also the real `blkid -p` PART_ENTRY_UUID of a GPT partition, `remount,rw` on vfat, the helper with the sensor, and package scriptlets. David's laptop steps are in the PR.

## For the next person
- Codex is to review this PR, especially `_child`, `fat_clean()` and the device checks.
- If a write is refused as `dirty` every time, a partition's Linux dirty flag may have been left set: Linux doesn't clear it on unmount if it was dirty when mounted. `fsck.vfat` at boot (most fstabs have pass 2 for `/boot/efi`) clears it.
