#!/usr/bin/env python3
"""Galaxy Book Fingerprint Manager — the slots file shared with the laptop's
other installs.

With SDCP the sensor only knows a template's ID (a MAC, no finger or name), so
each install notes what it knows about its templates in one small file on an
EFI system partition, which every OS on the laptop can reach:
  <ESP>/EFI/samsung-galaxybook/fingerprint-slots.json
{"version": 1, "sensors": {SERIAL: {TEMPLATE: {"finger", "user", "enrolled",
  "enrolled_on", "record", "installs": {INSTALL: {"os", "state": used|removed, "seen"}}}}},
 "installs": {INSTALL: {"os", "seen", "where": {"partuuid", "uuid", "ptuuid", "dev", "size"}}}}
TEMPLATE is the short ID the Sensor slots tab shows; INSTALL a hash of the
install's machine-id. The helper updates it whenever the Manager reads the
sensor; best effort only.

Which EFI partition (see shared_esp()): one on the drive this install runs
from (Galaxy Books have one NVMe slot), whichever of them already has the file
(the lowest partition number if several do; the others are renamed), or else
the first by partition number. Partition numbers are in the partition table,
so every install on the drive picks the same one without storing a choice. An
install that doesn't mount that partition (one with an EFI partition of its
own) opens it with a short-lived child process in its own mount namespace for
each read or write: see _child().

"installs" (top level) is every install that runs the Manager, fingers or not,
with where its root filesystem lives: the partition (PARTUUID), what's on it
(the filesystem's or LUKS container's UUID) and the disk (PTUUID). Each start
checks the others against the disks in the laptop: one whose partition is gone
from a disk that's there, or holds a different filesystem now (reinstalled,
formatted), no longer exists and is forgotten. A disk that isn't there (a
second drive taken out) proves nothing, so that one stays.

"record" is the fprintd record of that template (base64), from the first
install that noted it: what another install imports to use the same slot (the
Manager offers it). It only points to the slot (an ID and the sensor's MAC):
the fingerprint itself never leaves the sensor, and a record is no use without
this laptop's sensor and the finger. It goes with its template when the slot
is cleared.

Run as root when the Manager is removed (not upgraded), so the other installs
stop listing this one:
  shared_slots.py --forget-here
"""
import base64
import datetime
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time

SHARED_REL = os.path.join("EFI", "samsung-galaxybook", "fingerprint-slots.json")
IGNORED_NAME = "fingerprint-slots.ignored.json"     # another copy on the drive, renamed
ESP_PARTTYPES = {"c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "0xef"}   # GPT, MBR
RUN_DIR = "/run/samsung-galaxybook"                 # the child's mount folders
CHILD_TIMEOUT = 10                                  # seconds for one child read or write
CACHE_S = 5                                         # one status read finds the partition once
MAX_FILE = 4 << 20


def esp_dir():
    """The mount point of an EFI system partition this install has mounted (FAT,
    with an EFI folder), or None. Only the fallback now: see shared_esp()."""
    def vfat_mounts():
        try:
            with open("/proc/mounts") as f:
                return [l.split()[1].replace("\\040", " ") for l in f
                        if len(l.split()) > 2 and l.split()[2] in ("vfat", "msdos")]
        except OSError:
            return []
    for mp in ["/boot/efi", "/efi", "/boot"] + vfat_mounts():
        try:
            if os.path.isdir(os.path.join(mp, "EFI")) and mp in vfat_mounts():   # (autofs mounts it)
                return mp
        except OSError:
            continue
    return None


# ── Which EFI partition holds the shared file ───────────────────────────────
def _truthy(v):
    return v is True or str(v).lower() in ("1", "true")


def _lsblk_esp(args):
    """lsblk's JSON with what's needed to find EFI partitions, [] if it can't
    run. Replaced in tests."""
    try:
        out = subprocess.run(["lsblk", "-J", "-o",
                              "PATH,TYPE,PARTTYPE,FSTYPE,PARTUUID,UUID,RM,HOTPLUG,TRAN"] + args,
                             capture_output=True, text=True, timeout=10).stdout
        return json.loads(out).get("blockdevices") or []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _partn(dev):
    """A partition's number in the partition table (the same from every
    install, unlike the disk's name), or None. Replaced in tests."""
    try:
        with open(f"/sys/class/block/{os.path.basename(dev)}/partition") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _vfat_mounts(trigger=True):
    """{device: (mount point, read-only)} for the FAT filesystems this install
    has mounted. trigger: look in the usual places first, so an automount
    (autofs) mounts; never from _child's own namespace, where it could hang.
    Replaced in tests."""
    for mp in ("/boot/efi", "/efi", "/boot") if trigger else ():
        try:
            os.path.isdir(os.path.join(mp, "EFI"))
        except OSError:
            pass
    out = {}
    try:
        with open("/proc/mounts") as f:
            for line in f:
                p = line.split()
                if len(p) > 3 and p[2] in ("vfat", "msdos") and p[0].startswith("/dev/"):
                    out.setdefault(os.path.realpath(p[0]),
                                   (p[1].replace("\\040", " "), "ro" in p[3].split(",")))
    except OSError:
        pass
    return out


def _root_disk():
    """The disk under this install's root filesystem (through LUKS and LVM), as
    lsblk gives it, or None."""
    src = _root_source()
    if not src.startswith("/dev/"):
        return None
    nodes = list(_flat(_lsblk_esp(["-s", src])))     # inverse: root fs → partition → disk
    if not any(n.get("type") == "part" for n in nodes):
        return None
    return next((n for n in nodes if n.get("type") == "disk" and n.get("path")), None)


def _removable(disk):
    return _truthy(disk.get("rm")) or _truthy(disk.get("hotplug")) or disk.get("tran") == "usb"


def drive_esps():
    """This install's drive and its EFI partitions, by partition number: (disk,
    [_Target]). (None, []) when the drive can't be found."""
    disk = _root_disk()
    if not disk:
        return None, []
    mounts = _vfat_mounts()
    esps = []
    for n in _flat(_lsblk_esp([disk["path"]])):
        if n.get("type") != "part" or (n.get("fstype") or "") != "vfat" \
                or (n.get("parttype") or "").lower() not in ESP_PARTTYPES or not n.get("path"):
            continue
        m = mounts.get(os.path.realpath(n["path"]))
        esps.append(_Target(dev=n["path"], partn=_partn(n["path"]),
                            partuuid=n.get("partuuid") or "", uuid=n.get("uuid") or "",
                            mount=m[0] if m else None, readonly=bool(m and m[1])))
    esps.sort(key=lambda t: (t.partn is None, t.partn or 0, t.dev))
    return disk, esps


def shared_esp():
    """Where the shared file is, or goes: a _Target, or None (no EFI partition
    to keep it on, or this install runs from a removable drive).

    On this install's drive: the EFI partition that already has the file (the
    lowest partition number if several do: the others are in .others, to be
    renamed), or else the first. A partition that can't be read counts as
    having it, so a copy that can't be read is never passed over for another
    one. Without the drive (an unusual setup): the EFI partition this install
    has mounted, as before."""
    disk, esps = drive_esps()
    if disk is not None and _removable(disk):
        return None
    if not esps:
        mp = esp_dir()
        return _Target(path=os.path.join(mp, SHARED_REL)) if mp else None
    with_file = [t for t in esps if t.read()[0] != "missing"]
    chosen = with_file[0] if with_file else esps[0]
    chosen.others = [t for t in with_file if t is not chosen]
    chosen.first = chosen is esps[0]
    return chosen


# ── Reading and writing it ──────────────────────────────────────────────────
_reads = {}                 # dev → (when, state, text): one status read opens a partition once
_found = None               # (when, _Target) from shared_esp()


def _forget_cache():
    global _found
    _found = None
    _reads.clear()


class _Target:
    """The shared file on one EFI partition. Mounted by this install (path):
    read and written there. Not mounted (dev): opened for each read or write
    by a short-lived child process (_child) in its own mount namespace."""

    def __init__(self, dev="", partn=None, partuuid="", uuid="", mount=None, readonly=False,
                 path=None):
        self.dev, self.partn, self.partuuid, self.uuid = dev, partn, partuuid, uuid
        self.mount, self.readonly = mount, readonly
        self.path = path or (os.path.join(mount, SHARED_REL) if mount else None)
        self.mounted = self.path is not None
        self.others = []                            # other copies on the drive (shared_esp)
        self.first = False                          # the drive's first EFI partition
        self.raw = None                             # the text last read (None: no file)
        self.refused = None                         # why the last write didn't happen ("dirty"…)
        self._state = None

    def label(self):
        """For messages: the file's path, or where it is on a partition this
        install doesn't mount."""
        return self.path if self.mounted else f"{SHARED_REL} on {self.dev}"

    def __str__(self):
        return self.label()

    def state(self):
        if self._state is None:
            self.read()
        return self._state

    def read(self):
        """("ok", text) | ("missing", None) | ("error", None)."""
        if self.mounted:
            try:
                with open(self.path, "rb") as f:
                    res = ("ok", f.read(MAX_FILE).decode("utf-8", "replace"))
            except FileNotFoundError:
                res = ("missing", None)
            except OSError:
                res = ("error", None)
        else:
            hit = _reads.get(self.dev)
            if hit and time.monotonic() - hit[0] < CACHE_S:
                res = hit[1:]
            else:
                r = _run_child("read", self)
                res = (r.get("state"), r.get("text")) if r.get("state") in ("ok", "missing") \
                    else ("error", None)
                _reads[self.dev] = (time.monotonic(),) + res
        self._state, self.raw = res[0], res[1]
        return res

    def write(self, text):
        """Write the file atomically. True when written, False when it couldn't
        be (a full or read-only partition; one that isn't clean; a file that
        changed since it was read)."""
        if self.mounted:
            try:
                d = os.path.dirname(self.path)
                os.makedirs(d, exist_ok=True)
                tmp = self.path + ".new"
                with open(tmp, "w") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
                _fsync_dir(d)
                self._state, self.raw = "ok", text
                return True
            except OSError:
                return False
        r = _run_child("write", self, json.dumps({"text": text, "expect": self.raw}))
        _reads.pop(self.dev, None)
        self.refused = None if r.get("state") == "ok" else r.get("state") or "error"
        if r.get("state") == "ok":
            self._state, self.raw = "ok", text
            return True
        return False

    def rename_ignored(self):
        """Rename this copy (one another partition's copy takes precedence over)
        out of the way. The new name, or None."""
        if not self.mounted:
            r = _run_child("rename", self)
            _reads.pop(self.dev, None)
            return r.get("name") if r.get("state") == "ok" else None
        try:
            d = os.path.dirname(self.path)
            name = _free_name(d)
            os.rename(self.path, os.path.join(d, name))
            _fsync_dir(d)
            return name
        except OSError:
            return None


def _fsync_dir(d):
    try:
        fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _free_name(d):
    """fingerprint-slots.ignored.json, or -2, -3… if that's taken."""
    name, n = IGNORED_NAME, 1
    while os.path.lexists(os.path.join(d, name)):
        n += 1
        name = IGNORED_NAME.replace(".json", f"-{n}.json")
    return name


def _t(p):
    """A _Target for p (tests may give _path() a plain path)."""
    return p if isinstance(p, _Target) else _Target(path=p)


def _run_child(op, t, stdin=None):
    """Run _child() for op on t's partition, in a mount namespace of its own;
    its JSON answer, or {"state": "error"}."""
    unshare = shutil.which("unshare") or "/usr/bin/unshare"
    argv = [unshare, "--mount", "--propagation", "private", sys.executable or "python3", "-I",
            os.path.abspath(__file__), f"--esp-{op}", t.dev, t.partuuid or "-", t.uuid or "-"]
    try:
        r = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                           timeout=CHILD_TIMEOUT)    # killed when it runs out: the mount goes too
        lines = r.stdout.strip().splitlines()
        res = json.loads(lines[-1]) if lines else {}
        return res if isinstance(res, dict) else {"state": "error"}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"state": "error"}


def fat_clean(dev):
    """Whether a FAT filesystem was left clean: True; False when Linux's dirty
    flag is set or Windows' clean-shutdown bit is clear (an OS has it mounted
    read-write - hibernated, say - or didn't unmount it cleanly); None when it
    can't be told. Read from the partition itself, before it's mounted."""
    try:
        with open(dev, "rb") as f:
            bs = f.read(512)
            if len(bs) < 512 or bs[510:512] != b"\x55\xaa":
                return None
            bps, = struct.unpack_from("<H", bs, 0x0B)
            spc, rsv, nfats = bs[0x0D], struct.unpack_from("<H", bs, 0x0E)[0], bs[0x10]
            root_ents, tot16, fatsz16 = struct.unpack_from("<HHxH", bs, 0x11)
            tot32, = struct.unpack_from("<I", bs, 0x20)
            if bps not in (512, 1024, 2048, 4096) or not spc or not rsv or not nfats:
                return None
            fat32 = fatsz16 == 0
            if bs[0x41 if fat32 else 0x25] & 0x01:     # Linux: FAT_STATE_DIRTY
                return False
            f.seek(rsv * bps)
            fat = f.read(8)
            if fat32:
                return bool(struct.unpack_from("<I", fat, 4)[0] & 0x08000000)
            data = (tot16 or tot32) - rsv - nfats * fatsz16 - (root_ents * 32 + bps - 1) // bps
            if data // spc < 4085:                  # FAT12 has no clean-shutdown bit
                return True
            return bool(struct.unpack_from("<H", fat, 2)[0] & 0x8000)
    except (OSError, struct.error, IndexError):
        return None


def _probe(dev):
    """blkid's low-level probe of a partition: {"TYPE", "UUID", "PART_ENTRY_UUID", …}
    read from the partition itself, not udev's cache. {} if it can't run."""
    try:
        out = subprocess.run(["blkid", "-p", "-o", "export", dev], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(l.split("=", 1) for l in out.splitlines() if "=" in l)


def _child(op, dev, partuuid, uuid):
    """--esp-read|--esp-write|--esp-rename DEV PARTUUID UUID, run by _run_child
    inside `unshare --mount --propagation private`. Prints one JSON line.

    The partition isn't mounted by this install, so nothing here uses it. The
    mount is in this process's own mount namespace: nothing else on the system
    sees it, and the kernel drops it when this process ends, however it ends.
    Read-only to read. To write: the partition must be clean (fat_clean) and
    the file what the parent read; only then remounted read-write, written
    (atomically, fsync'd) and unmounted. Never repairs anything."""
    def done(**kw):
        print(json.dumps(kw))
        sys.exit(0)

    def run(*argv):
        try:
            return subprocess.run(argv, capture_output=True,
                                  timeout=CHILD_TIMEOUT - 2).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    if os.geteuid() != 0:
        done(state="error", why="not root")
    try:
        # unshare execs this, so the parent is the helper (or --forget-here): its
        # namespace is the system's, and must not be this one.
        if os.readlink("/proc/self/ns/mnt") == os.readlink(f"/proc/{os.getppid()}/ns/mnt"):
            done(state="error", why="not in a mount namespace of its own")
        st = os.stat(dev)
    except OSError as e:
        done(state="error", why=str(e))
    if not stat.S_ISBLK(st.st_mode):
        done(state="error", why="not a block device")
    info = _probe(dev)                              # what's on the partition itself, now
    if info.get("TYPE") != "vfat" or (info.get("PART_ENTRY_UUID") or "-").lower() != partuuid.lower() \
            or (info.get("UUID") or "-").lower() != uuid.lower():
        done(state="error", why="not the partition expected")
    if os.path.realpath(dev) in _vfat_mounts(trigger=False):
        done(state="error", why="mounted already")
    if op in ("write", "rename") and fat_clean(dev) is not True:
        done(state="dirty")
    req = {}
    if op == "write":
        try:
            req = json.loads(sys.stdin.read(MAX_FILE * 2))
            if not isinstance(req, dict) or not isinstance(req.get("text"), str):
                raise ValueError
        except ValueError:
            done(state="error", why="bad request")
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    mp = tempfile.mkdtemp(prefix="esp-", dir=RUN_DIR)
    mounted = False
    res = {"state": "error", "why": "couldn't mount"}
    try:
        if not run("mount", "-t", "vfat", "-o", "ro,nosuid,nodev,noexec,umask=0077", dev, mp):
            return done(**res)
        mounted = True
        if os.stat(mp).st_dev != st.st_rdev:
            res = {"state": "error", "why": "mounted something else"}
            return done(**res)
        path = os.path.join(mp, SHARED_REL)
        try:
            with open(path, "rb") as f:
                cur = f.read(MAX_FILE).decode("utf-8", "replace")
        except FileNotFoundError:
            cur = None
        except OSError:
            res = {"state": "error", "why": "unreadable"}
            return done(**res)
        if op == "read":
            res = {"state": "ok", "text": cur} if cur is not None else {"state": "missing"}
        elif op == "write":
            if cur != req.get("expect"):
                res = {"state": "changed"}
            elif not run("mount", "-o", "remount,rw", mp):
                res = {"state": "error", "why": "couldn't mount read-write"}
            else:
                d = os.path.dirname(path)
                os.makedirs(d, exist_ok=True)
                with open(path + ".new", "w") as f:
                    f.write(req["text"])
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(path + ".new", path)
                _fsync_dir(d)
                res = {"state": "ok"}
        elif op == "rename":
            if cur is None:
                res = {"state": "missing"}
            elif not run("mount", "-o", "remount,rw", mp):
                res = {"state": "error", "why": "couldn't mount read-write"}
            else:
                d = os.path.dirname(path)
                name = _free_name(d)
                os.rename(path, os.path.join(d, name))
                _fsync_dir(d)
                res = {"state": "ok", "name": name}
    except OSError as e:
        res = {"state": "error", "why": str(e)}
    finally:
        if mounted and not run("umount", mp):       # the namespace going takes it anyway
            run("umount", "-l", mp)
        try:
            os.rmdir(mp)
        except OSError:
            pass
    done(**res)


def install_key():
    try:
        with open("/etc/machine-id") as f:
            return hashlib.sha256(f.read().strip().encode()).hexdigest()[:12]
    except OSError:
        return None


def os_label():
    """This install's distro, as the Manager names it (Fedora, Ubuntu, Linux Mint…)."""
    if os.path.exists("/etc/mx-version"):
        return "MX Linux"
    fields = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                fields[k] = v.strip("\"'")
    except OSError:
        pass
    name = fields.get("NAME") or fields.get("ID", "").capitalize()
    for suffix in (" GNU/Linux", " Linux"):
        if name.endswith(suffix) and name != suffix.strip():
            name = name[: -len(suffix)]
    return name.strip() or "Linux"


# ── Where installs live, and whether they still exist ────────────────────────
def _lsblk(args):
    """lsblk's JSON (blockdevices), [] if it can't run. Replaced in tests."""
    try:
        out = subprocess.run(["lsblk", "-J", "-o", "PATH,TYPE,PARTUUID,UUID,PTUUID,SIZE"] + args,
                             capture_output=True, text=True, timeout=10).stdout
        return json.loads(out).get("blockdevices") or []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _flat(nodes):
    for n in nodes or []:
        yield n
        yield from _flat(n.get("children"))


def _root_source():
    try:
        src = subprocess.run(["findmnt", "-no", "SOURCE", "/"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return src.split("[")[0]                        # btrfs: /dev/nvme0n1p8[/@]


def here_location():
    """Where this install's root filesystem lives: the partition under it (through
    LUKS or LVM), as {"partuuid", "uuid", "ptuuid", "dev", "size"}, or None."""
    src = _root_source()
    if not src.startswith("/dev/"):
        return None
    part = next((n for n in _flat(_lsblk(["-s", src])) if n.get("type") == "part"), None)
    if not part or not part.get("partuuid"):
        return None
    return {"partuuid": part["partuuid"], "uuid": part.get("uuid") or "",
            "ptuuid": part.get("ptuuid") or "", "dev": os.path.basename(part.get("path") or ""),
            "size": part.get("size") or ""}


def install_state(where, disks=None):
    """Whether an install still exists: ("present"|"gone"|"unknown", why)."""
    if not isinstance(where, dict) or not where.get("partuuid"):
        return "unknown", "its location isn't known"
    devs = list(_flat(disks if disks is not None else _lsblk([])))
    if not devs:
        return "unknown", "the disks couldn't be listed"
    part = next((n for n in devs if n.get("partuuid") == where["partuuid"]), None)
    if part is None:
        if where.get("ptuuid") and any(n.get("ptuuid") == where["ptuuid"] for n in devs):
            return "gone", "its partition has been deleted"
        return "unknown", "its disk isn't connected"
    if where.get("uuid") and part.get("uuid") and part["uuid"] != where["uuid"]:
        return "gone", "its partition has been reformatted (reinstalled)"
    return "present", ""


def _path():
    """Where the shared file is (a _Target), or None. Found once per status
    read (CACHE_S), not once per function that uses it."""
    global _found
    if _found and time.monotonic() - _found[0] < CACHE_S:
        return _found[1]
    t = shared_esp()
    _found = (time.monotonic(), t)
    return t


class SharedFileProblem(Exception):
    """The shared file is there but can't be used, so it mustn't be written."""


def _target():
    """_path() as a _Target (tests may give _path() a plain path), or None."""
    p = _path()
    return _t(p) if p else None


def _load(path):
    """The shared file's contents; {} when it's missing or can't be used.
    Before writing, tell the two apart with _unusable()."""
    state, text = _t(path).read()
    if state == "ok":
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("version") == 1:
                return data
        except ValueError:
            pass
    return {}


def _unusable(path, data):
    """Whether _load gave nothing for a file that's there: damaged, unreadable
    or from a newer version. Writing would destroy what the other installs
    noted, and turn used_elsewhere()'s "can't tell" into "no other install"."""
    return not data and _t(path).state() != "missing"


def problem_file():
    """Where the shared file is (_Target.label()) if it's there but can't be
    used, otherwise None."""
    t = _target()
    return t.label() if t and _unusable(t, _load(t)) else None


def problem_dev():
    """The partition holding a shared file that can't be used, when this
    install doesn't mount it (so the fix needs mounting it first), else None."""
    t = _target()
    return t.dev if t and not t.mounted and _unusable(t, _load(t)) else None


def _save(path, data, before):
    """Write data if it changed (atomically). True when written, None when
    nothing changed, False when the write failed (a full or read-only EFI
    partition; one another OS left mounted; the file changed since it was
    read)."""
    if json.dumps(data, sort_keys=True) == before:
        return None
    return _t(path).write(json.dumps(data, indent=1, sort_keys=True))


def _installs(sensor, me, top=None):
    """Every install that noted a template on this sensor, or runs the Manager
    with none yet (top-level "installs"): [{key, os, seen, slots, here,
    where}], this install first, then the most recently seen."""
    seen = {}
    for k, v in (top or {}).items():
        if isinstance(v, dict):
            seen[k] = {"key": k, "os": v.get("os", "?"), "seen": str(v.get("seen", "")),
                       "slots": 0, "here": k == me, "where": v.get("where") or {}}
    for e in sensor.values():
        if not isinstance(e, dict):
            continue
        for k, v in (e.get("installs") or {}).items():
            if not isinstance(v, dict):
                continue
            i = seen.setdefault(k, {"key": k, "os": v.get("os", "?"), "seen": "", "slots": 0,
                                    "here": k == me, "where": {}})
            i["slots"] += 1
            if str(v.get("seen", "")) > i["seen"]:
                i["seen"], i["os"] = str(v.get("seen", "")), v.get("os", i["os"])
    out = sorted(seen.values(), key=lambda i: i["seen"], reverse=True)
    return sorted(out, key=lambda i: not i["here"])          # stable: this install first


def _check_installs(data, me, here, today):
    """Note this install (and where it lives) in the top-level "installs", and
    forget the others that no longer exist. Returns the forgotten ones:
    [{"key", "os", "why"}]."""
    installs = data.setdefault("installs", {})
    mine = {"os": here, "seen": today}
    where = here_location()
    if where:
        mine["where"] = where
    elif isinstance(installs.get(me), dict) and installs[me].get("where"):
        mine["where"] = installs[me]["where"]       # keep what an earlier run found
    installs[me] = mine
    disks = _lsblk([])
    gone = []
    for k, v in list(installs.items()):
        if k == me or not isinstance(v, dict):
            continue
        state, why = install_state(v.get("where"), disks)
        if state == "gone":
            gone.append({"key": k, "os": v.get("os", "?"), "why": why})
    if gone:
        keys = {g["key"] for g in gone}
        for k in keys:
            installs.pop(k, None)
        for sensor in (data.get("sensors") or {}).values():
            for e in (sensor or {}).values():
                if isinstance(e, dict) and isinstance(e.get("installs"), dict):
                    for k in keys & set(e["installs"]):
                        del e["installs"][k]
    return gone


def share_slots(serial, templates, records_by_tid, forgotten=None, listed=True):
    """Note this install's templates in the shared file and add what other
    installs noted to each template ("shared"). Returns the installs that
    share this sensor (see _installs), or None without a usable file (one
    that's there but can't be used is left as it is). Installs that no longer
    exist are forgotten and added to forgotten. listed False: the driver can't
    list the sensor, so templates says nothing about what's on it and no entry
    is dropped for being missing from it. Never fails."""
    me, path = install_key(), _path()
    if not me or not path or not serial:
        return None
    data = _load(path)
    if _unusable(path, data):
        return None
    before = json.dumps(data, sort_keys=True)
    data["version"] = 1
    sensor = data.setdefault("sensors", {}).setdefault(serial, {})
    today = datetime.date.today().isoformat()
    here = os_label()
    try:
        gone = _check_installs(data, me, here, today)
    except Exception:
        gone = []
    if forgotten is not None:
        forgotten.extend(gone)
    on_chip = {t["id"] for t in templates}
    for tid in list(sensor):
        if not isinstance(sensor[tid], dict) or (listed and tid not in on_chip):
            del sensor[tid]                         # cleared from the sensor
    for t in templates:
        e = sensor.get(t["id"], {})
        installs = e.setdefault("installs", {})
        r = records_by_tid.get(t["id"])
        if r is not None:
            if "enrolled_on" not in e:              # the first install to note it
                e.update(enrolled_on=here, enrolled=r["enrolled"])
            e.update(finger=r["name"], user=r["user"])
            if "record" not in e:                   # for the other installs to import
                try:
                    with open(r["path"], "rb") as f:
                        raw = f.read()
                    if len(raw) <= 65536:
                        e["record"] = base64.b64encode(raw).decode()
                except (OSError, KeyError):
                    pass
            installs[me] = {"os": here, "state": "used", "seen": today}
        elif t.get("removed"):
            rm = t["removed"]
            e.setdefault("finger", rm["name"])
            e.setdefault("user", rm["user"])
            installs[me] = {"os": here, "state": "removed", "seen": today}
        else:
            installs.pop(me, None)
        if e.get("finger"):
            sensor[t["id"]] = e
            others = [{"key": k, "os": v.get("os", "?"), "state": v.get("state", "used"),
                       "seen": v.get("seen", "")}
                      for k, v in sorted(installs.items()) if k != me and isinstance(v, dict)]
            t["shared"] = {"finger": e["finger"], "user": e.get("user", ""),
                           "enrolled": e.get("enrolled", ""), "enrolled_on": e.get("enrolled_on", ""),
                           "others": others}
    _save(path, data, before)
    return _installs(sensor, me, data.get("installs") or {})


def esp_records(serial):
    """Records the installs noted for templates on this sensor: {template:
    {"finger", "user", "data" (bytes), "os": [distros using it]}}."""
    path = _path()
    sensor = ((_load(path).get("sensors") or {}).get(serial) or {}) if path else {}
    out = {}
    for tid, e in sensor.items():
        if not isinstance(e, dict) or not e.get("record") or not e.get("finger"):
            continue
        try:
            data = base64.b64decode(e["record"], validate=True)
        except (ValueError, TypeError):
            continue
        oses = sorted({v.get("os", "?") for v in (e.get("installs") or {}).values()
                       if isinstance(v, dict) and v.get("state", "used") == "used"})
        out[tid] = {"finger": e["finger"], "user": e.get("user", ""), "data": data, "os": oses}
    return out


def esp_summary(serial):
    """Where the shared file is and how many records it has for this sensor:
    {"path": "/boot/efi/EFI/…/fingerprint-slots.json" (or "EFI/… on /dev/…")
    or None, "records": n, "dev": the partition, "mounted": whether this
    install mounts it, "first": whether it's the drive's first EFI partition,
    "refused": why this run's last change couldn't be saved there ("dirty":
    another OS left it in use), or None}."""
    t = _target()
    sensor = ((_load(t).get("sensors") or {}).get(serial) or {}) if t else {}
    n = sum(1 for e in sensor.values() if isinstance(e, dict) and e.get("record"))
    return {"path": t.label() if t else None, "records": n, "dev": t.dev if t else "",
            "mounted": bool(t and t.mounted), "first": bool(t and t.first),
            "refused": t.refused if t else None}


def rename_others():
    """Rename the other copies of the shared file on this drive (shared_esp()
    uses the one with the lowest partition number) to fingerprint-slots.
    ignored.json, so no install picks them up again. Only when the one in use
    can be read: if it can't, the other may be the good one, so nothing is
    renamed. Returns [{"dev", "name"}] for what was renamed."""
    t = _target()
    if not t or not t.others or not _load(t):
        return []
    out = []
    for o in t.others:
        name = o.rename_ignored()
        if name:
            out.append({"dev": o.dev or o.label(), "name": name})
    _forget_cache()
    return out


def read_file():
    """The whole shared file, for a backup ({} without one)."""
    path = _path()
    return _load(path) if path else {}


def merge_backup(backup):
    """Merge a backup of the shared file into it: templates, records and
    installs it doesn't have are added; nothing already there is changed.
    Templates no longer on the sensor drop out the next time the Manager
    reads it. Returns how many records were added, or None without an EFI
    partition. Raises OSError when the merged file couldn't be written, and
    SharedFileProblem when the file there can't be used (it's left as it is)."""
    path = _path()
    if not path:
        return None
    if not isinstance(backup, dict) or backup.get("version") != 1 \
            or not isinstance(backup.get("sensors"), dict):
        raise ValueError("not a backup of fingerprint-slots.json")
    data = _load(path)
    if _unusable(path, data):
        raise SharedFileProblem(_t(path).label())
    before = json.dumps(data, sort_keys=True)
    data["version"] = 1
    added = 0
    for k, v in (backup.get("installs") or {}).items():
        if isinstance(v, dict):
            data.setdefault("installs", {}).setdefault(str(k), v)
    for serial, tpls in backup["sensors"].items():
        if not isinstance(tpls, dict):
            continue
        sensor = data.setdefault("sensors", {}).setdefault(str(serial), {})
        for tid, e in tpls.items():
            if not isinstance(e, dict):
                continue
            cur = sensor.setdefault(str(tid), {})
            for k in ("finger", "user", "enrolled", "enrolled_on", "record"):
                if k in e and k not in cur and isinstance(e[k], str):
                    cur[k] = e[k]
                    added += k == "record"
            inst = cur.setdefault("installs", {})
            for k, v in (e.get("installs") or {}).items():
                if isinstance(v, dict) and k not in inst:
                    inst[k] = v
    if _save(path, data, before) is False:
        raise OSError(f"couldn't write {_t(path).label()}")
    return added


def used_elsewhere(serial):
    """Templates on this sensor that another install still uses (state "used").
    None when that can't be told - no EFI partition, or a shared file that
    can't be read - so a caller never takes it as "no other install": that
    would clear slots other distros still log in with. No shared file yet on
    the EFI partition is an empty set: no install has noted any template."""
    me, path = install_key(), _path()
    if not path:
        return None
    data = _load(path)
    if _t(path).state() == "missing":
        return set()
    if not data:                                    # unreadable or not ours
        return None
    sensor = (data.get("sensors") or {}).get(serial) or {}
    return {tid for tid, e in sensor.items() if isinstance(e, dict)
            and any(k != me and isinstance(v, dict) and v.get("state", "used") == "used"
                    for k, v in (e.get("installs") or {}).items())}


def forget_installs(keys, serial=None):
    """Take installs (by key) out of the shared file, on one sensor or all.
    Their templates' finger and user stay, so the others can still say whose
    they were. Returns how many entries went."""
    path = _path()
    keys = {k for k in keys if k}
    if not path or not keys:
        return 0
    data = _load(path)
    if not data:
        return 0
    before = json.dumps(data, sort_keys=True)
    gone = 0
    for k in keys & set(data.get("installs") or {}):
        del data["installs"][k]
        gone += 1
    for sid, sensor in (data.get("sensors") or {}).items():
        if serial and sid != serial or not isinstance(sensor, dict):
            continue
        for e in sensor.values():
            installs = e.get("installs") if isinstance(e, dict) else None
            if isinstance(installs, dict):
                for k in keys & set(installs):
                    del installs[k]
                    gone += 1
    _save(path, data, before)
    return gone


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] in ("--esp-read", "--esp-write", "--esp-rename"):
        _child(sys.argv[1][6:], *sys.argv[2:5])
    if sys.argv[1:] != ["--forget-here"]:
        sys.exit(f"Usage: {sys.argv[0]} --forget-here")
    if os.geteuid() != 0:
        sys.exit("Run as root.")
    try:
        n = forget_installs([install_key()])
    except Exception:                               # never fail a removal
        n = 0
    if n:
        print(f"Took this {os_label()} out of the fingerprint slots file shared with the "
              "laptop's other installs.")
