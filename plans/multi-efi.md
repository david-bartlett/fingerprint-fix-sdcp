# Plan: more than one EFI partition

Status: **plan only, nothing built.** The idea is in PLAN.md §11. The questions for David at the end need answers before the first PR.

This covers three things:
- finding every EFI partition on the laptop
- keeping the copies of `EFI/samsung-galaxybook/fingerprint-slots.json` on them in step, with clear rules for when they disagree
- backing up all of them, and restoring from one or more backup files with the same rules

---

## 1. The problem

`shared_slots.esp_dir()` returns the first EFI partition it finds: `/boot/efi`, `/efi` or `/boot`, then any mounted vfat with an `EFI` folder. Everything else (`share_slots`, `used_elsewhere`, `esp_records`, backup, restore, `--forget-here`) uses that one file.

That's fine with one EFI partition shared by every OS, which is how David's Book5 Pro is set up. It breaks when there are two:

- **Two drives, one EFI partition each.** For example, Windows and Fedora on the first drive, and Ubuntu installed to a second drive with its own EFI partition. Fedora mounts the first partition and Ubuntu the second. Each writes its own `fingerprint-slots.json`, so neither sees the other:
  - no import offer
  - no multi-distro mode
  - and the dangerous part: `used_elsewhere()` on Ubuntu says no other install uses a slot, so **Reset Ubuntu clears slots Fedora still logs in with.**
- **A distro that made its own EFI partition** on the same drive (some installers do, when asked to "use free space"). Same result.
- **A distro that mounts none at boot**, but whose partition is still there. Today it has no file at all, so `used_elsewhere()` returns `None` and Reset refuses. That's safe but unhelpful.

The single-partition case must keep working exactly as it does today.

## 2. Goals and limits

Goals:
1. Every install sees what every other install noted, whichever EFI partition each one mounts.
2. Copies that differ are merged by fixed rules, so the result doesn't depend on which partition or backup file was read first.
3. Nothing makes the Manager more willing to clear a slot. When in doubt, a slot counts as **used elsewhere**.
4. Nothing is written to a partition it shouldn't touch: USB sticks, SD cards, installer media, or a file that's damaged or from a newer version.
5. Older Managers on other distros keep working with the file. No version bump.

Not goals:
- Keeping a copy on every vfat partition. Only the rule in §4.2.
- Network or cloud copies.

## 3. Finding the EFI partitions

New `esp_list()` in `shared_slots.py`:

```
lsblk -J -o PATH,TYPE,PARTTYPE,FSTYPE,PARTUUID,UUID,PTUUID,RM,HOTPLUG,TRAN,PKNAME
```

A partition counts as an EFI partition when:
- `PARTTYPE` is `c12a7328-f81f-11d2-ba4b-00a0c93ec93b` (GPT) or `0xef` (MBR)
- and `FSTYPE` is `vfat`

and it's left out when any of these is true:
- `RM` (removable) or `HOTPLUG` is true
- `TRAN` is `usb`, or the parent disk's is
- its disk is a loop device, unless the test flag file in §11.2 exists

Each entry is `{"dev", "partuuid", "uuid", "ptuuid", "mount": path or None, "home": bool}`.
- `mount` comes from `/proc/mounts`, matched by device. That's more reliable than lsblk's `MOUNTPOINTS` and works with every util-linux we support.
- **home** is the partition today's `esp_dir()` would pick: the one this install mounts at `/boot/efi`, `/efi` or `/boot` (autofs included). There's at most one. Without one, `home` is `None`, and §4.2 says what happens then.

Each install also notes its home partition in its own entry: `installs[key].where.esp = <PARTUUID>`. Older Managers ignore it. The Other distros dialog can use it to say *Ubuntu (uses the EFI partition on the second drive)*, and §6 uses it to tell a disconnected drive from a missing copy.

## 4. Reading and writing the copies

### 4.1 Reading

`EspCopies` is a context manager for one helper request. For each entry from `esp_list()`:
1. **Mounted already** (`/boot/efi`, or a desktop automount in `/run/media/…`): read the file in place.
2. **Not mounted**: mount it read-only in the helper's own folder:
   ```
   mount -t vfat -o ro,nosuid,nodev,noexec,umask=0077 <dev> /run/samsung-galaxybook/esp/<PARTUUID>
   ```
   The folder is root's, mode 0700. Unmount on exit, `__exit__` included, even after an error.
3. Each copy gets a state:
   - `ok` (read and usable)
   - `missing` (no file on that partition)
   - `unusable` (there but damaged, unreadable or from a newer version: today's `_unusable()`)
   - `unreachable` (the mount failed, or a read error)

Read-only first matters. A read-write vfat mount marks the volume dirty until it's unmounted, and most status reads change nothing. Mounting is cheap next to what a status read already does (stopping fprintd and opening the sensor), so every request that touches the shared file reads all the partitions. There's no cache to go stale.

### 4.2 Which copies get written

After merging (§5) and this install's own changes, the result is written to:
1. the **home** partition (the file is created if it's not there, as today), and
2. **every other partition whose copy is `ok`**, meaning it already holds the file.

No other partition gets a new file. That's enough to bring every install together:
- Fedora (partition A) and Ubuntu (partition B). Fedora runs first and writes A.
- Ubuntu reads A and B, merges, then writes B (its home) and A (it has the file).
- From then on each sees the other, whichever runs.

It also means a partition no install uses (Windows' own on a second drive, say) never gets a file. If the home partition is formatted (reinstalling Windows can do that), the next start writes it again from the other copy, with no restore needed.

**Writing to a partition that isn't mounted read-write:** `mount -o remount,rw`, then write `fingerprint-slots.json.new`, `fsync`, rename, `fsync` the folder, and unmount. That's today's atomic write plus the syncs, because the partition is unmounted straight after.

A partition mounted read-only somewhere else is read but not written.

**`share_slots()` with no home partition, but other copies there:** read them all, and write only the `ok` ones. Today that returns `None`. After this, a distro that doesn't mount its EFI partition still shares.

### 4.3 Who calls what

- `share_slots`, `used_elsewhere`, `esp_records`, `esp_summary`, `problem_file`, `read_file` and `forget_installs` all use one merged view, not `_path()`.
- The helper's `status` builds the view once and passes it on, so one refresh mounts each partition once, not five times.
- `shared_slots.py --forget-here` (package removal and `uninstall.sh`) forgets this install on every copy it can write. It stays best effort and never fails a removal. Each mount has a time limit, so a stuck drive can't hang `dnf remove`.

## 5. Merging copies: the conflict rules

One pure function, `merge_copies(copies) -> dict`, used for EFI partition copies **and** backup files (§8). It never reads the sensor, disks or clock. That keeps it easy to test with plain dicts.

Order of `copies`: the home partition, then other partitions by PARTUUID, then backups (newest `backup.made` first). Order only settles exact ties.

### 5.1 Two small additions to the file (still version 1)

- **`seen_at`**: an ISO time in UTC (`2026-11-17T07:30:12Z`), written next to `seen` in `installs[key]` and in each `sensors[…][tid].installs[key]`. `seen` (the date) stays for older Managers.
  - Comparisons use `seen_at` when it's there, else `seen` at `T00:00:00Z`.
  - Older Managers rewrite their own entries without `seen_at`. That's fine: it falls back to the date.
- **`forgotten`**: `{key: ISO time}` at the top level. These are tombstones for installs that were deliberately forgotten (§5.3).

Older Managers keep both: `share_slots` loads the whole dict and saves it back.

### 5.2 Rules

| What | Rule |
| --- | --- |
| `version` | 1. A copy without version 1 is `unusable` and isn't merged (§6). |
| `forgotten[key]` | Union; the latest time per key wins. |
| `installs[key]` | The entry with the newest `seen_at`/`seen` wins whole. If it has no `where` (older version), take `where` from the newest entry that has one. |
| Forgotten install | Dropped, here and in every slot's `installs`, when `forgotten[key]` is later than its newest entry. If the entry is later (the Manager was installed again), it's kept and the tombstone dropped. |
| Templates (`sensors[serial][tid]`) | Union. Templates no longer on the sensor are pruned afterwards by `share_slots`, as today, and only when the sensor could be listed. |
| `enrolled`, `enrolled_on` | From the copy with the earliest `enrolled` (the first install to note it). |
| `record` | From the same copy as `enrolled`; if that copy has none, the first copy that has one. Any record for that slot works: they all point to the same slot, and the import rewrites the owner. |
| `finger`, `user` | From the copy whose entry for that template has the newest `seen_at`/`seen` in its `installs` (the last install to touch it). |
| `…[tid].installs[key]` | Newest `seen_at`/`seen` wins whole, so `used` versus `removed` is settled by whichever happened last. Tie: `used`. |
| Missing in one copy, there in another | Kept. A copy that lacks an entry doesn't delete it. Deletions come only from the sensor (pruning) and from tombstones. |

### 5.3 Why tombstones, and why only for whole installs

Without them, merging brings forgotten installs back:
1. Ubuntu is removed (`--forget-here`), or forgotten in **Other distros…**, while partition B's drive is out.
2. B still lists Ubuntu. The drive goes back in, B is merged, and Ubuntu returns.
3. Install detection won't catch it if Ubuntu's partition is still there (only the package was removed).

So `forget_installs()` writes `forgotten[key] = now`, and the merge respects it. `share_slots()` deletes `forgotten[me]` whenever it notes this install, which covers removing the Manager and putting it back.

**Per-slot entries get no tombstones.** When an install stops using a slot (its record deleted by Reset or pruning), `share_slots` pops its entry, and a stale copy can bring it back as `used`. That errs on the safe side: the slot looks used elsewhere and isn't cleared. It also fixes itself, because **each install is the authority on its own entries.** At every status read it rewrites its own `installs[me]` in every slot from its real records, after the merge. Stale `used` entries from other installs go the next time that install runs with the partition there.

`installs` entries of an install found **gone** (partition deleted or reformatted) don't need tombstones either. `_check_installs` finds them gone again on every start.

### 5.4 Clocks

`seen_at` is UTC from each install's clock. Distros sync with NTP, and Windows' local-time RTC doesn't matter, since only Linux installs write here. If a clock is wrong, the worst case is that an older `used` beats a newer `removed`: the safe direction. An older `removed` beating a newer `used` is fixed the next time that install runs (§5.3).

## 6. Damaged, newer, missing and unreachable copies

| Copy state | Read | Written | `used_elsewhere()` | Shown |
| --- | --- | --- | --- | --- |
| `ok` | merged | yes | — | Back up & restore lists it |
| `missing` | — | only if it's the home partition | — | — |
| `unusable` | **not merged** | **never** (left byte for byte, as today) | `None` (can't tell) | today's warning, once a run, naming the partition |
| `unreachable` (mount or read failed) | — | — | `None` (can't tell) | Back up & restore: *couldn't be read* |
| drive not connected (in `where.esp` of a known install, not in lsblk) | — | — | unchanged | Back up & restore: *on a drive that isn't connected* |

Notes:
- **One `unusable` copy doesn't stop sharing through the others** (question 5). Today, with one file, an unusable file means no sharing at all. With two, the usable copy keeps working, but Reset and Clear refuse (`used_elsewhere()` returns `None`) until the bad copy is sorted, because it may list installs still using slots.
- **The warning's fix command** names the partition. For one that isn't mounted:
  ```
  sudo mount /dev/nvme1n1p1 /mnt
  sudo mv /mnt/EFI/samsung-galaxybook/fingerprint-slots.json /mnt/EFI/samsung-galaxybook/fingerprint-slots.json.bad
  sudo umount /mnt
  ```
  Both names are written out in full, so the command works in fish (CachyOS) too.
- **Disconnected drive:** its copy is stale until it's back, then merged by the rules above. Installs on that drive stay **unknown** (kept), as today. No `None`, because their entries are on the other copies too, as long as both drives were in at some start.

## 7. What changes in each function

`lib/shared_slots.py`:

| Function | Change |
| --- | --- |
| `esp_dir()` | Kept, renamed `home_esp()`: it finds the home partition. |
| `esp_list()` | New (§3). |
| `EspCopies` | New context manager (§4.1): mount read-only, read, give copies and states, remount read-write and write the §4.2 set, unmount. |
| `merge_copies()` | New, pure (§5). |
| `_load`, `_unusable`, `_save` | Work on one copy (a path). `_save` adds the `fsync`s. |
| `share_slots()` | Merge, `_check_installs`, rewrite own entries (plus `seen_at`, `where.esp`, drop `forgotten[me]`), prune, write the set. |
| `used_elsewhere()` | Merged view; `None` if any copy is `unusable` or `unreachable`, or there's no partition at all. |
| `esp_records()`, `esp_summary()` | Merged view. `esp_summary` also returns the copies: `[{"dev", "mount", "home", "state", "records"}]`. |
| `problem_file()` | Becomes `problem_files()`, a list. The status keeps `shared_problem` as the first entry for an older window during an update, and adds `shared_problems`. |
| `forget_installs()` | Every writable copy, plus `forgotten`. |
| `read_file()` | The merged view plus `backup` details (§8). |
| `merge_backup()` | Becomes `restore_backups(list)` (§9). |

`lib/fingerprint-manager-helper.py`:
- `status` builds one view per request.
- `backup_slots` is unchanged on the outside.
- `restore_slots` takes `datas` (a list), or `data` for one.
- New `restore_preview`.
- Mount and unmount only ever use paths under `/run/samsung-galaxybook/esp/`. Device paths come from lsblk, never from the window.

`lib/fingerprint-manager.py`:
- the Back up & restore dialog (§10)
- Restore with several files and a preview
- `_warn_shared_problem` with a list

Packaging: no new files (it's still `shared_slots.py`). The removal scriptlets already run `--forget-here`.

## 8. Backup

**Back up…** saves the **merged** view of every readable copy, not just the home partition's file. It's the same version 1 format, so an older Manager's Restore still accepts it, plus details older versions ignore:

```json
"backup": {"made": "2026-11-17T07:40:00Z", "by": "Fedora",
           "from": [{"dev": "nvme0n1p1", "partuuid": "…", "state": "ok", "records": 6},
                    {"dev": "nvme1n1p1", "partuuid": "…", "state": "ok", "records": 6}]}
```

`forgotten` goes in too, so restoring an old backup later doesn't bring back installs forgotten since.

The button works when the merged view has any records. If a copy is `unusable` or `unreachable`, the backup still saves what could be read, and the saved message says which partition was left out.

## 9. Restoring from one or more backup files

### 9.1 Choosing

**Restore…** opens the file chooser with **several files allowed** (`set_select_multiple(True)`). Each one:
- is read by the window as today: at most 1 MiB, JSON
- has to pass the existing check (version 1, `sensors` a dict)

If one fails, nothing is restored and the error names that file.

### 9.2 Preview, then confirm

New helper action `restore_preview(datas)`. It computes `merge_copies(current copies + backups)` without writing, and returns what would change:
- records added (fingers, with the distro that noted them)
- distros added
- entries a backup has newer than the EFI partition (per distro: *Ubuntu: removed → used, 12 Nov*)
- forgotten distros a backup still lists, which **won't** come back
- templates for a different sensor (another laptop), which **aren't** restored (question 4)
- the partitions it would write to

The window shows that as a confirmation (*Restore from 2 backups?*), with **Restore** and **Cancel**. Cancel is the default, matching other dialogs that change shared state. If nothing would change, it just says *Nothing new: the EFI partitions already have everything in those backups*, as today.

### 9.3 Writing

`restore_backups(datas)`:
1. Read the copies again; the preview's view could be stale.
2. Merge with the backups, current copies first so they win exact ties.
3. Keep only this laptop's sensor (serial from USB, as the helper's other actions do).
4. Write the §4.2 set. If no partition has the file (formatted), it goes on the home partition.

If a copy is `unusable`, restore refuses (`SharedFileProblem`, as today) and names it. Then the window refreshes and offers the fingers this install can use, as now.

### 9.4 What this changes from today

Today's restore changes nothing already there; it only adds. With several backups and several copies, "first one wins" would make the result depend on the order of files. **Newest wins** gives the same result whatever the order (question 3).

The safety rules still hold:
- Restore never clears a slot.
- An entry can only go from `removed` to `used` if that really happened later.
- This install's own entries are rewritten from its records at the next refresh anyway.

## 10. What the user sees

- **One EFI partition:** nothing visibly different. Same dialogs and words, the same file.
- **Back up & restore…** lists each copy under **Now:**
  > 6 records, kept in step on 2 EFI partitions:
  > • `/boot/efi` (this distro's)
  > • `nvme1n1p1` on the second drive (not mounted: read when needed)
  > • `sda1`: on a drive that isn't connected

  and a line for any `unusable` or `unreachable` copy.
- **Other distros…** can add which partition each distro uses (from `where.esp`) when there's more than one. Optional; it could be left for a later PR.
- **No new notifications.** The only one is today's once-a-run warning for an unusable copy, now naming the partition.

`docs/multi-distro.md`, `docs/how-it-works.md` and `docs/troubleshooting.md` get a short section each: two EFI partitions, what's kept in step, and the fix for a bad copy on a partition that isn't mounted.

## 11. Testing

### 11.1 Here, without the hardware

- **`merge_copies()`:** a table of cases in a scratch script outside the repo:
  - order doesn't change the result (every ordering of 3 copies)
  - tombstone beats an older entry, and loses to a newer one
  - `used` versus `removed` by `seen_at`, with ties going to `used`
  - an old-format entry (no `seen_at`) against a new one
  - earliest `enrolled` keeps its record
  - a missing entry doesn't delete
  - garbage entries are skipped
  - a different sensor is left out on restore
- **`esp_list()`:** fake lsblk JSON:
  - one partition
  - two drives
  - MBR `0xef`
  - a USB stick, an SD card and a loop device (all left out)
  - a vfat partition that isn't an EFI partition
- **`EspCopies`:** with `mount`/`umount` replaced, check:
  - read-only first
  - read-write only when writing
  - always unmounted, also after an exception
  - nothing written to `unusable` or read-only copies
- **Real vfat images:** if the session has root and loop devices, use two loop-backed FAT images (§11.2). Otherwise, say so in the PR.
- **Window:** Xvfb mock-ups of the Back up & restore dialog (one, two, and a bad copy) and the restore preview.

### 11.2 On the laptop (David)

A second EFI partition without repartitioning, using a loop device. It only counts while the flag file exists. The flag is a file, not an environment variable, because `pkexec` clears the environment. It's in `/run`, so a reboot removes it.

```bash
truncate -s 100M /tmp/esp2.img
sudo sfdisk /tmp/esp2.img <<< 'label: gpt
type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B'
LOOP=$(sudo losetup -fP --show /tmp/esp2.img)
sudo mkfs.vfat -F 32 "${LOOP}p1"
sudo touch /run/samsung-galaxybook/allow-loop-esp
```

(Written for bash; the PR will give a fish version too, for CachyOS.)

Each implementation PR will have its own numbered steps. Roughly:
1. One partition: nothing changes (Fedora, then Ubuntu).
2. Loop partition with no file: nothing is written to it.
3. Copy the real file onto it, then forget a distro in **Other distros…**. Both copies drop it; put the old copy back on the loop partition, and it stays forgotten.
4. A newer `removed` on one copy beats an older `used` on the other.
5. Put garbage in the loop copy: the warning names it, Reset refuses, and sharing via `/boot/efi` keeps working.
6. Back up with two copies, then restore from two backup files (one older): check the preview and the result.
7. `sudo losetup -d $LOOP` mid-session: the copy shows as not connected, and nothing fails.

## 12. Order of PRs

Each is one topic, testable on its own, and leaves things working:

1. **Merge rules, `seen_at` and tombstones.** `merge_copies()` plus its tests; `share_slots` writes `seen_at` and drops `forgotten[me]`; `forget_installs` writes tombstones. Still one partition. No user-visible change; no CHANGELOG line, or a plain one.
2. **Read every EFI partition.** `esp_list()`, `EspCopies` (read-only), the merged view for `used_elsewhere`, import offers and `esp_summary`. Writes still go to the home partition only. Reset becomes safe on two-partition laptops here. Back up & restore lists the copies.
3. **Keep the copies in step.** The §4.2 write set, read-write remount, `--forget-here` on every copy, the problem list and warning.
4. **Back up all, restore several.** Merged backup with `backup` details, multi-file restore with preview, newest-wins.
5. **Docs and PLAN.md §6 and §10**, or folded into each PR as it lands (AGENTS.md asks for the docs in the same PR, so this is the default).

## 13. Questions for David

1. **Mounting partitions that aren't mounted:** OK for the root helper to mount another EFI partition read-only in `/run/samsung-galaxybook/esp/`, remount it read-write only to write, then unmount? Without that, the two-drive case can't work, because each distro usually mounts only its own.
2. **USB and removable drives left out:** that means a distro installed on an external SSD won't take part. I think that's right: it keeps installer sticks and Ventoy drives safe.
3. **Restore becomes newest-wins, with a preview,** instead of "never changes what's there"?
4. **Restore only this laptop's sensor:** skip templates for any other sensor serial in a backup? Today they're added.
5. **One unusable copy:** keep sharing through the others (my suggestion, with Reset and Clear refusing), or stop all sharing, as with one file today?
6. **Write rule:** the home partition plus partitions that already have the file (my suggestion), or every internal EFI partition?
