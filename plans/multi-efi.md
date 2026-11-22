# Plan: one shared file on the drive's EFI partition

Status: **plan only, nothing built.** The idea is in PLAN.md §11. Answer the questions at the end before the first PR.

This replaces the first version of this plan (PR #180). That version kept a copy on every EFI partition in step, with merge rules, tombstones and a multi-file restore. After talking it through, David chose something simpler:

- **One file**, on one EFI partition, **on the drive this distro runs from.**
- The Galaxy Book3, Book4 and Book5 have **one NVMe slot**, so there's one drive.
  - If that drive is removed, the laptop doesn't boot.
  - If it's replaced, the new drive starts with no file, and **Back up & restore** puts the records back, as it does today.
- So there's no copying, no merging and nothing to do for other drives.

---

## 1. The problem

`shared_slots.esp_dir()` returns the first EFI partition **this distro has mounted**: `/boot/efi`, `/efi` or `/boot`, then any mounted vfat with an `EFI` folder.

That works when every distro mounts the same EFI partition. It breaks when a distro has its own, which is what David's laptop has now:

- Windows and Fedora share `nvme0n1p1`, and Fedora mounts it at `/boot/efi`.
- EndeavourOS made its own EFI partition on the same drive and mounts only that one.

So each writes a different `EFI/samsung-galaxybook/fingerprint-slots.json`, and neither sees the other:
- no import offer
- no multi-distro mode
- and the dangerous part: `used_elsewhere()` on EndeavourOS says no other distro uses a slot, so **Reset EndeavourOS would clear slots Fedora still logs in with.**

## 2. The rule

The shared file lives on an EFI partition **on the same drive as this distro's root filesystem**:

1. If one of that drive's EFI partitions already has `EFI/samsung-galaxybook/fingerprint-slots.json`, **use it.** If more than one has it, use the one with the **lowest partition number**, and ignore the others (§6).
2. If none has it, **create it on the drive's first EFI partition**: the lowest partition number (`p1` on David's laptop, the one Windows made).

Why it works:
- **Every distro on the drive picks the same partition,** without any of them storing a choice. Partition numbers are in the partition table, so they're the same from every distro, unlike `/dev/nvme0n1`, whose name the kernel picks at boot.
- **The file stays wherever it is.** Once it's there, the rule always finds it, even if it ended up on a partition that isn't the first (after a Move, §7).

**Why not keep the location in `~/.config/galaxybook-fingerprint-manager/settings`:** that file belongs to one user on one distro. The location has to be the same for every distro on the laptop, and the root helper writes the file for every user. If two distros' settings disagreed, there would be two files again. Letting the file mark its own location avoids storing anything.

## 3. Finding the drive's EFI partitions

New `shared_esp()` in `shared_slots.py`, replacing `esp_dir()`:

1. **This distro's drive:** the disk under the root filesystem, through LUKS and LVM. `here_location()` already walks `lsblk -s` from `findmnt /` to the partition; its parent disk is the drive.
2. **That drive's EFI partitions:**
   ```
   lsblk -J -o PATH,TYPE,PARTTYPE,FSTYPE,PARTUUID,UUID,RM,HOTPLUG,TRAN <disk>
   ```
   A partition counts when `PARTTYPE` is `c12a7328-f81f-11d2-ba4b-00a0c93ec93b` (GPT) or `0xef` (MBR) and `FSTYPE` is `vfat`.
3. **Partition number:** from `/sys/class/block/<name>/partition`. Every kernel has it, whatever the util-linux version.
4. **Removable drives are refused:** if the drive is `RM`, `HOTPLUG` or `TRAN=usb` (a distro running from a USB stick), the Manager doesn't share. It behaves as with no EFI partition today.
5. **Mounted already?** From `/proc/mounts`, matched by device.

It returns `{"dev", "partn", "partuuid", "mount": path or None, "has_file", "others": [other EFI partitions on the drive that have the file]}`, or `None`.

If the root filesystem's disk can't be found (an unusual setup), fall back to today's `esp_dir()`, so nothing gets worse.

## 4. Opening an EFI partition this distro hasn't mounted

EndeavourOS needs this on David's laptop: the file is on `p1`, which EndeavourOS doesn't mount.

1. **Mounted already** (Fedora's `/boot/efi`): use that mount, and never mount it a second time.
2. **Not mounted:** then nothing in the running distro is using it, so the helper can mount it briefly without affecting anything. The helper (root):
   - **Moves into its own mount namespace** when it starts: `os.unshare(os.CLONE_NEWNS)` (Python 3.12 or newer, which every supported distro has), then `mount --make-rslave /`.
     - Its mounts are **invisible to the rest of the system**: no drive appears in Files or Dolphin, and nothing else can start using it.
     - "Slave" rather than "private", so automounts outside (a systemd automount on `/boot/efi`, say) still reach the helper.
     - When the helper exits, or crashes, the kernel drops the mount. It can't be left mounted.
   - **Mounts read-only** the first time the file is needed:
     ```
     mount -t vfat -o ro,nosuid,nodev,noexec,umask=0077 <dev> /run/samsung-galaxybook/esp
     ```
     The folder is root's, mode 0700. Most status reads change nothing, so most sessions never mount read-write.
   - **Read-write only to save:**
     - check the partition is clean (below)
     - `mount -o remount,rw`
     - write `fingerprint-slots.json.new`, `fsync`, rename, `fsync` the folder (today's atomic write, plus the syncs)
     - `mount -o remount,ro`, which flushes the write and marks the partition clean again
   - **Unmounts** when the helper exits normally.
3. **Clean check before writing:** if another OS has the partition mounted and is hibernated, or didn't shut down cleanly, it may have its own cached copy. Writing under it could damage the partition when it resumes. FAT records this:
   - Linux marks the volume dirty while it's mounted read-write: the state byte in the boot sector (offset `0x41` on FAT32, `0x25` on FAT16), bit `0x01`.
   - Windows clears the clean-shutdown bit in the second FAT entry: bit `0x08000000` on FAT32, `0x8000` on FAT16.

   If either says dirty, the helper **reads but doesn't write**. Sharing still reads, but nothing new is noted until that OS is shut down properly.

   This check is skipped for a partition this distro has mounted itself, which is dirty because of that mount. Windows doesn't normally mount the EFI partition at all.
4. **`shared_slots.py --forget-here`** (package removal and `uninstall.sh`) does the same in its own process: unshare, mount, write, unmount. Each mount has a time limit, and it never fails a removal.

The window never sends a device path: the helper finds it with lsblk.

## 5. What changes in the code

`lib/shared_slots.py`:

| Function | Change |
| --- | --- |
| `esp_dir()` | Replaced by `shared_esp()` (§3). Kept only as the fallback. |
| `_path()` | Gives a usable path to the file: the existing mount, or the helper's read-only mount (§4). |
| `_save()` | Remounts read-write and back when the mount is the helper's; refuses on a dirty partition; adds the `fsync`s. |
| `share_slots`, `used_elsewhere`, `esp_records`, `esp_summary`, `problem_file`, `read_file`, `merge_backup`, `forget_installs` | Unchanged apart from going through `_path()` and `_save()`. |
| `esp_summary()` | Also returns which partition it is (`dev`, `partn`, mounted or not) and any `others` (§6). |
| New | `EspMount`: the namespace, mount and remount handling, used by the helper and `--forget-here`. |

`lib/fingerprint-manager-helper.py`:
- Unshares its mount namespace at start (§4), and unmounts on exit (in the same place `finish_test()` runs).
- Mount and remount only under `/run/samsung-galaxybook/esp`.

`lib/fingerprint-manager.py`: the Back up & restore dialog shows where the file is (§7).

Packaging: no new files.

## 6. Unusual cases

| Case | What happens |
| --- | --- |
| One EFI partition (most laptops) | Exactly as today. |
| Several on the drive, one has the file | That one. |
| Several have the file (like David's laptop today, before he deletes EndeavourOS's copy) | The lowest partition number. The others are left as they are, never read or written. Back up & restore names them, so they can be deleted. There's no joining: the files have to be sorted out by hand. |
| None has the file | Created on the first EFI partition. |
| The partition holding the file is dirty | Read, not written (§4). |
| The partition can't be mounted | As today when the EFI partition can't be read: `used_elsewhere()` returns `None`, so Reset and Clear refuse. |
| The file there is damaged or from a newer version | As today: left byte for byte, with the once-a-run warning. The fix command for a partition this distro hasn't mounted mounts it first, with both file names in full so it works in fish. |
| Drive replaced | No file on the new drive, so a new one is made. Back up & restore → Restore… puts the records back. |
| Distro running from a USB drive | Doesn't share (§3). |
| Second internal drive (no supported model has one) | Not looked at. Its distros don't share with this drive's. |

## 7. What the user sees

- **Back up & restore…** says where the file is, under **Now:**
  > 6 records in `EFI/samsung-galaxybook/fingerprint-slots.json` on the first EFI partition (`nvme0n1p1`, mounted at `/boot/efi`).

  or, from EndeavourOS:
  > … on `nvme0n1p1` (the drive's first EFI partition; this distro doesn't mount it, so the Manager opens it when needed).

  plus a line for any other copy that's being ignored.
- **Move…** (a later PR, question 2): moves the file to another EFI partition on the same drive. It writes the new file, checks it, then renames the old one to `fingerprint-slots.json.moved`. Every other distro finds the new one next time, because of rule 1.
- With one EFI partition, nothing visible changes apart from that line.

`docs/multi-distro.md` and `docs/troubleshooting.md` get a short section: distros with their own EFI partition, where the file goes, and how to remove an old copy.

## 8. Testing

### 8.1 Here, without the hardware

- **`shared_esp()`** with fake lsblk JSON and sysfs:
  - one EFI partition
  - two on the drive, with neither, one or both holding the file
  - MBR `0xef`
  - a removable drive
  - a root filesystem on LUKS and on LVM
  - a disk that can't be found (the fallback)
- **The clean check** on real vfat images made with `mkfs.vfat` in a scratch folder: clean, then with the Linux and Windows dirty flags set by hand, on FAT16 and FAT32. This needs no root.
- **`EspMount`** with `mount` replaced:
  - read-only first, read-write only to save, read-only again after
  - no write when dirty
  - unmounted on exit
- If the session has root and loop devices, a real mount in a namespace. Otherwise, say so in the PR.
- **Window:** Xvfb mock-ups of the Back up & restore dialog.

### 8.2 On the laptop (David)

1. On Fedora: open the Manager. The dialog says `nvme0n1p1`, mounted at `/boot/efi`. Nothing else changes.
2. Delete EndeavourOS's copy of `fingerprint-slots.json` (on its own EFI partition), or leave it, to check step 4.
3. On EndeavourOS: open the Manager.
   - It shows Fedora as another distro, and offers Fedora's fingers.
   - The dialog says `nvme0n1p1`, not mounted.
   - `findmnt` in a terminal shows no new mount, and nothing appears in the file manager.
4. With EndeavourOS's old copy still there, the dialog names it as ignored.
5. Close the Manager (and once, `sudo pkill -f fingerprint-manager-helper`). Then `sudo mount | grep esp` shows nothing.
6. Back on Fedora: Fedora sees EndeavourOS.
7. Remove the Manager on EndeavourOS. Fedora no longer lists it (`--forget-here` reached `p1`).

## 9. Order of PRs

1. **Find the shared file on this drive and open it safely.** §3 to §6, the dialog line, docs, and PLAN.md §6 and §10. That fixes the Reset danger.
2. **Move…** (if wanted).

## 10. Questions for David

1. **The helper's private mount** (§4): moving the helper into its own mount namespace, mounting the EFI partition read-only, and remounting read-write only to save, with the clean check first. OK?
2. **Move…:** wanted, or is "first EFI partition, or wherever the file already is" enough on its own? I'd leave it out of the first PR.
3. **Several copies on the drive:** ignore all but the lowest-numbered one and name them in the dialog (my suggestion), or also offer to delete them?
