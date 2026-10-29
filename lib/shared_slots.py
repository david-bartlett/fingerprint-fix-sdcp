#!/usr/bin/env python3
"""Galaxy Book Fingerprint Manager — the slots file shared with the laptop's
other installs.

With SDCP the sensor only knows a template's ID (a MAC, no finger or name), so
each install notes what it knows about its templates in one small file on the
EFI system partition, which every OS on the laptop shares:
  <ESP>/EFI/samsung-galaxybook/fingerprint-slots.json
{"version": 1, "sensors": {SERIAL: {TEMPLATE: {"finger", "user", "enrolled",
  "enrolled_on", "record", "installs": {INSTALL: {"os", "state": used|removed, "seen"}}}}},
 "installs": {INSTALL: {"os", "seen", "where": {"partuuid", "uuid", "ptuuid", "dev", "size"}}}}
TEMPLATE is the short ID the Sensor slots tab shows; INSTALL a hash of the
install's machine-id. The helper updates it whenever the Manager reads the
sensor; best effort only.

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
import subprocess
import sys

SHARED_REL = os.path.join("EFI", "samsung-galaxybook", "fingerprint-slots.json")


def esp_dir():
    """The EFI system partition's mount point (FAT, with an EFI folder), or None."""
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
    esp = esp_dir()
    return os.path.join(esp, SHARED_REL) if esp else None


def _load(path):
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("version") == 1:
            return data
    except (OSError, ValueError):
        pass
    return {}


def _save(path, data, before):
    """Write data if it changed (atomically). True when written."""
    if json.dumps(data, sort_keys=True) == before:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".new"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


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


def share_slots(serial, templates, records_by_tid, forgotten=None):
    """Note this install's templates in the shared file and add what other
    installs noted to each template ("shared"). Returns the installs that
    share this sensor (see _installs), or None without the file. Installs
    that no longer exist are forgotten and added to forgotten. Never fails."""
    me, path = install_key(), _path()
    if not me or not path or not serial:
        return None
    data = _load(path)
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
        if tid not in on_chip or not isinstance(sensor[tid], dict):
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
    {"path": "/boot/efi/EFI/…/fingerprint-slots.json" or None, "records": n}."""
    path = _path()
    sensor = ((_load(path).get("sensors") or {}).get(serial) or {}) if path else {}
    n = sum(1 for e in sensor.values() if isinstance(e, dict) and e.get("record"))
    return {"path": path, "records": n}


def read_file():
    """The whole shared file, for a backup ({} without one)."""
    path = _path()
    return _load(path) if path else {}


def merge_backup(backup):
    """Merge a backup of the shared file into it: templates, records and
    installs it doesn't have are added; nothing already there is changed.
    Templates no longer on the sensor drop out the next time the Manager
    reads it. Returns how many records were added, or None without an EFI
    partition."""
    path = _path()
    if not path:
        return None
    if not isinstance(backup, dict) or backup.get("version") != 1 \
            or not isinstance(backup.get("sensors"), dict):
        raise ValueError("not a backup of fingerprint-slots.json")
    data = _load(path)
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
    _save(path, data, before)
    return added


def used_elsewhere(serial):
    """Templates on this sensor that another install still uses (state "used")."""
    me, path = install_key(), _path()
    sensor = ((_load(path).get("sensors") or {}).get(serial) or {}) if path else {}
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
