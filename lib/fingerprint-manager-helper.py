#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Fingerprint Manager helper
# =============================================================================
# The root half of fingerprint-manager.py. The window runs as the user and
# starts this once with pkexec (one password prompt per session); after that
# it sends one JSON request per line on stdin and reads one JSON reply per
# line on stdout.
#
# Talking to the sensor needs root, the fix's SDCP library and fprintd stopped
# for a moment, so every sensor job stops fprintd, does its one job and starts
# fprintd again. Import and export use import-fingerprint.sh and
# export-fingerprint.sh from ../tools, with all their checks.
#
# Records are never deleted: anything removed from /var/lib/fprint is moved to
# /var/lib/samsung-galaxybook/removed-fingerprints/<date>/ (last 5 kept), the
# same folder the boot check uses.
# =============================================================================
import os
import sys

# Each way the fix is installed: (driver marker, driver library folder, fprintd
# drop-in, Manager marker) — a package first, then install.sh. Keep in step
# with lib/fixpaths.sh. The driver (fingerprint-fix-sdcp) can be removed while
# the Manager stays (once the distro's libfprint has SDCP), so the layout is
# the driver's if it is installed, else the one this Manager belongs to.
LAYOUTS = [
    ("/usr/lib/fingerprint-fix-sdcp/installed",
     "/usr/lib/fingerprint-fix-sdcp",
     "/usr/lib/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf",
     "/usr/lib/galaxybook-fingerprint-manager/installed"),
    ("/etc/samsung-galaxybook-egismoc-sdcp.installed",
     "/usr/local/lib/libfprint-egismoc-sdcp",
     "/etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf",
     "/etc/galaxybook-fingerprint-manager.installed"),
]
MARKER, LIBDIR, DROPIN, MGR_MARKER = next(
    (l for l in LAYOUTS if os.path.isfile(l[0])),
    next((l for l in LAYOUTS if os.path.isfile(l[3])), LAYOUTS[-1]))

# pkexec clears the environment. Re-run with the fix's library first in the
# search path, before anything loads libfprint.
if (os.path.isfile(os.path.join(LIBDIR, "libfprint-2.so.2"))
        and os.environ.get("LD_LIBRARY_PATH") != LIBDIR):
    env = dict(os.environ, LD_LIBRARY_PATH=LIBDIR)
    os.execve(sys.executable, [sys.executable, os.path.realpath(__file__)] + sys.argv[1:], env)

import datetime
import glob
import hashlib
import json
import pwd
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")    # import/export/PAM scripts
STORE = "/var/lib/fprint"
EXPORT_NAME = "fingerprint-export.tgz"      # where export-fingerprint.sh writes it
REMOVED_DIR = "/var/lib/samsung-galaxybook/removed-fingerprints"
REPLACED_DIR = "/var/lib/samsung-galaxybook/replaced-fingerprints"
FINGERS = ["unknown", "left-thumb", "left-index-finger", "left-middle-finger",
           "left-ring-finger", "left-little-finger", "right-thumb",
           "right-index-finger", "right-middle-finger", "right-ring-finger",
           "right-little-finger"]
ANSI = re.compile(r"\x1b\[[0-9;]*m")

import threading

FPrint = Gio = GLib = None
GI_ERROR = None
try:
    import gi
    gi.require_version("FPrint", "2.0")
    from gi.repository import FPrint, Gio, GLib
except (ImportError, ValueError) as e:
    GI_ERROR = str(e)

OUT_LOCK = threading.Lock()
TEST = {"cancellable": None, "proc": None}   # the fingerprint test that is running, if any


class Fail(Exception):
    pass


# ── Who and what ──────────────────────────────────────────────────────────────
def calling_user():
    for var in ("PKEXEC_UID", "SUDO_UID"):
        uid = os.environ.get(var)
        if uid and uid.isdigit() and int(uid) != 0:
            return pwd.getpwuid(int(uid)).pw_name
    raise Fail("Could not tell which user started this (no PKEXEC_UID).")


def sensor_usb():
    """(product id, serial) of the Egis 05a5/05a1 sensor, or (None, None)."""
    for d in glob.glob("/sys/bus/usb/devices/*"):
        try:
            with open(f"{d}/idVendor") as f:
                if f.read().strip() != "1c7a":
                    continue
            with open(f"{d}/idProduct") as f:
                pid = f.read().strip()
            if pid not in ("05a5", "05a1"):
                continue
            with open(f"{d}/serial") as f:
                return pid, f.read().strip()
        except OSError:
            continue
    return None, None


def read_marker(path):
    try:
        with open(path) as f:
            return f.read().strip() or None
    except OSError:
        return None


def fix_state():
    """(driver installed and complete, driver marker or None)."""
    marker = read_marker(MARKER)
    ok = bool(marker) and os.path.isfile(os.path.join(LIBDIR, "libfprint-2.so.2")) \
        and os.path.isfile(DROPIN)
    return ok, marker


# fprintd names each record file by the finger's number in hex: 1-9, then
# "a" for the right little finger (10).
FINGER_FILE = r"[1-9a]"


def finger_name(n):
    return FINGERS[int(n, 16)] if re.fullmatch(FINGER_FILE, n) else n


def short_id(p):
    data = p.serialize()
    if isinstance(data, tuple):          # PyGObject may return (ok, data)
        data = next(x for x in data if not isinstance(x, bool))
    return hashlib.sha1(bytes(data)).hexdigest()[:10]


# Slots shared with the laptop's other installs: see shared_slots.py.
from shared_slots import (share_slots, forget_installs, install_key, used_elsewhere,  # noqa: E402
                          esp_records, read_file, merge_backup, esp_summary)
import io  # noqa: E402


def enroll_date(p):
    try:
        d = p.get_enroll_date()
        if d and d.valid():
            return f"{d.get_year():04d}-{int(d.get_month()):02d}-{d.get_day():02d}"
    except Exception:
        pass
    return ""


# The kind of print a record holds, from its serialized header: libfprint
# writes "FP3" then a GVariant "(issbymsmsia{sv}v)" whose first field is the
# print type (1 raw, 2 nbis, 3 sdcp). This driver enrols "sdcp"; "raw" ones were
# enrolled with the distro's (pre-SDCP) egismoc driver or another non-SDCP
# build, and can never match here.
PRINT_KINDS = {1: "raw", 2: "nbis", 3: "sdcp"}


def print_kind(data):
    if len(data) >= 7 and data[:3] == b"FP3":
        return PRINT_KINDS.get(int.from_bytes(data[3:7], "little"), "unknown")
    return "unknown"


def read_records(serial):
    """Every fprintd record for this sensor, for every user on this install."""
    out = []
    for path in sorted(glob.glob(f"{STORE}/*/egismoc/{serial}/*")):
        if not os.path.isfile(path) or os.path.islink(path):
            continue
        user, finger = os.path.relpath(path, STORE).split("/")[0], os.path.basename(path)
        rec = {"user": user, "finger": finger, "name": finger_name(finger),
               "path": path, "print": None}
        try:
            with open(path, "rb") as f:
                data = f.read()
            rec["kind"] = print_kind(data)
            rec["print"] = FPrint.Print.deserialize(data)
        except Exception as e:
            rec["error"] = str(e)
        out.append(rec)
    return out


# ── The sensor (fprintd stopped meanwhile) ────────────────────────────────────
_CONTEXT = None


def fp_context():
    """The one libfprint context of this process. libfprint-tod (Ubuntu's
    libfprint) aborts the whole program when a second context is created, and
    this helper serves many requests: so it is made once and kept. Later calls
    first handle pending USB events, so a sensor that went away and came back
    (fprintd stopping, a USB reset) is listed afresh."""
    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = FPrint.Context()
        _CONTEXT.enumerate()
    else:
        main = GLib.MainContext.default()
        while main.pending():
            main.iteration(False)
    return _CONTEXT


class Sensor:
    def __enter__(self):
        subprocess.run(["systemctl", "stop", "fprintd"], capture_output=True)
        last = None
        for _ in range(3):
            ctx = fp_context()
            devs = [d for d in ctx.get_devices() if d.get_driver() == "egismoc"]
            if not devs:
                last = "No egismoc sensor found by libfprint."
                time.sleep(0.5)
                continue
            try:
                devs[0].open_sync(None)
                self.dev, self.ctx = devs[0], ctx
                return devs[0]
            except Exception as e:
                last = str(e)
                subprocess.run(["systemctl", "stop", "fprintd"], capture_output=True)
                time.sleep(0.7)
        subprocess.run(["systemctl", "start", "fprintd"], capture_output=True)
        if last.startswith("No egismoc") and not fix_state()[0]:
            # Without the driver, the distro's own libfprint drives the reader.
            # The last line is the one the window shows; Details… has it all.
            raise Fail("Your fingerprints have been kept safe, and will work once the driver "
                       "has been installed.\n\n"
                       "Install the fingerprint-fix-sdcp package, or run sudo ./install.sh if you "
                       "installed from the fingerprint-fix-sdcp GitHub folder.\n"
                       "Your distro's driver can't use the reader — reinstall "
                       "fingerprint-fix-sdcp's driver.")
        raise Fail(f"Could not open the fingerprint sensor: {last}")

    def __exit__(self, *exc):
        try:
            self.dev.close_sync(None)
        except Exception:
            pass
        subprocess.run(["systemctl", "start", "fprintd"], capture_output=True)
        return False


def move_records(paths):
    """Move records out of /var/lib/fprint into a dated safety folder."""
    if not paths:
        return []
    dest_root = f"{REMOVED_DIR}/{datetime.datetime.now():%Y-%m-%d_%H%M%S}"
    moved = []
    for path in paths:
        real = os.path.realpath(path)
        if not real.startswith(STORE + "/") or not os.path.isfile(real):
            continue
        dest = os.path.join(dest_root, os.path.relpath(real, STORE))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(real, dest)
        moved.append(dest)
    subprocess.run(["chmod", "-R", "go-rwx", REMOVED_DIR], capture_output=True)
    dirs = sorted(glob.glob(f"{REMOVED_DIR}/*/"), key=os.path.getmtime, reverse=True)
    for old in dirs[5:]:
        shutil.rmtree(old, ignore_errors=True)
    return moved


# ── Requests ──────────────────────────────────────────────────────────────────
def _print_bytes(p):
    data = p.serialize()
    return bytes(data[0] if isinstance(data, tuple) else data)


def _for_user(data, user):
    """A record's bytes with its owner set to user (as import does), or None."""
    try:
        p = FPrint.Print.deserialize(data)
        p.set_username(user)
        return _print_bytes(p)
    except Exception:
        return None


def import_offer(user, serial, chip, records, moved):
    """Fingers this install could use, from the records the installs keep on
    the EFI partition: their slot is on the sensor, this install doesn't use
    it, and the user has no working record for that finger. [{"tid", "finger",
    "name", "user", "from": [distros using it], "removed": True if removed
    here}], or None. The window's own offer leaves out the removed ones (taken
    off on purpose); ☰ → Import from other distros… lists them too."""
    mine = [r for r in records if r["user"] == user and r["print"] is not None]
    have = {r["finger"] for r in mine if any(r["print"].equal(c) for c in chip)}
    taken = [r["print"] for r in records if r["print"] is not None]
    gone_here = [m["print"] for m in moved if m["print"] is not None]
    cands = []
    try:
        num = {name: f"{i:x}" for i, name in enumerate(FINGERS) if i}
        cands += [(num[e["finger"]], e["data"], e["user"], e["os"])
                  for e in esp_records(serial).values() if e["finger"] in num]
    except Exception:
        pass
    out, seen = [], set()
    for finger, data, owner, src in cands:
        if finger in have or finger in {o["finger"] for o in out}:
            continue
        try:
            p = FPrint.Print.deserialize(data)
        except Exception:
            continue
        c = next((c for c in chip if p.equal(c)), None)
        if c is None or any(p.equal(q) for q in taken):
            continue                                # gone, or used here
        tid = short_id(c)
        if tid in seen:
            continue
        seen.add(tid)
        out.append({"tid": tid, "finger": finger, "name": finger_name(finger),
                    "user": owner, "from": src,
                    "removed": any(p.equal(q) for q in gone_here)})
    out.sort(key=lambda o: int(o["finger"], 16))
    return out or None


def do_import_offer(req):
    """Import the offered fingers chosen ("tids"): their records from the EFI
    partition, made the user's, through import-fingerprint.sh like any import."""
    user = calling_user()
    _, serial = sensor_usb()
    wanted = {str(t) for t in req.get("tids") or []}
    records, moved = read_records(serial), moved_records(serial)
    with Sensor() as dev:
        chip = dev.list_prints_sync(None)
    offer = [o for o in import_offer(user, serial, chip, records, moved) or [] if o["tid"] in wanted]
    if not offer:
        raise Fail("Nothing to import: those fingerprints are no longer on the sensor.")
    esp = esp_records(serial)
    entries = {}
    for o in offer:
        raw = (esp.get(o["tid"]) or {}).get("data")
        mine = _for_user(raw, user) if raw else None
        if mine:
            entries[o["finger"]] = mine
    if not entries:
        raise Fail("Could not read the records to import.")
    tmpdir = tempfile.mkdtemp(prefix="galaxybook-import-")
    try:
        path = os.path.join(tmpdir, EXPORT_NAME)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            base = f"{user}/egismoc/{serial}"
            for d in (user, f"{user}/egismoc", base):
                ti = tarfile.TarInfo(d)
                ti.type, ti.mode = tarfile.DIRTYPE, 0o700
                tar.addfile(ti)
            for finger, raw in entries.items():
                ti = tarfile.TarInfo(f"{base}/{finger}")
                ti.size, ti.mode = len(raw), 0o600
                tar.addfile(ti, io.BytesIO(raw))
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        return do_import({"file": path, "fingers": sorted(entries), "dead": req.get("dead")})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def do_status(req):
    pid, serial = sensor_usb()
    ok, marker = fix_state()
    st = {"user": calling_user(), "usb_id": f"1c7a:{pid}" if pid else None,
          "serial": serial, "fix_installed": ok, "marker": marker,
          "mgr_marker": read_marker(MGR_MARKER),
          "records": [], "templates": [], "features": {}}
    if not pid:
        raise Fail("EgisTec fingerprint sensor (1c7a:05a5 / 1c7a:05a1) not found.")
    if marker and not ok:
        raise Fail("fingerprint-fix-sdcp's driver is incomplete here — files are missing.\n"
                   "Reinstall fingerprint-fix-sdcp.")
    if FPrint is None:
        raise Fail(f"Python can't load libfprint ({GI_ERROR}).\n"
                   "Install your distro's libfprint GObject introspection package "
                   "(e.g. gir1.2-fprint-2.0 on Debian/Ubuntu/Mint/MX).")
    with Sensor() as dev:
        st["device_id"] = dev.get_device_id()
        st["device_name"] = dev.get_name()
        for f in ("STORAGE_LIST", "STORAGE_DELETE", "STORAGE_CLEAR"):
            feat = getattr(FPrint.DeviceFeature, f, None)
            st["features"][f] = bool(feat is not None and dev.has_feature(feat))
        try:
            st["enroll_stages"] = int(dev.get_nr_enroll_stages())
        except Exception:
            st["enroll_stages"] = 0
        chip = dev.list_prints_sync(None) if st["features"]["STORAGE_LIST"] else []
    records = read_records(serial)
    try:                                            # removed copies of fingers back in use
        prune_moved(serial, records)
    except Exception:
        pass
    # Records this install moved aside (Remove, dead records, import --replace),
    # newest first: an unused template that matches one is "removed here",
    # not an unknown template from another distro.
    moved = sorted((m for m in moved_records(serial) if m["print"] is not None),
                   key=lambda m: m["date"], reverse=True)
    for p in chip:
        users = [r for r in records if r["print"] is not None and p.equal(r["print"])]
        tpl = {"id": short_id(p), "used_by": [f"{r['user']} {r['name']}" for r in users],
               "keys": [[r["user"], r["finger"]] for r in users]}
        if not users:
            m = next((m for m in moved if p.equal(m["print"])), None)
            if m:
                here = os.path.exists(f"{STORE}/{m['user']}/egismoc/{serial}/{m['finger']}")
                tpl["removed"] = {"user": m["user"], "name": m["name"], "kind": m["kind"],
                                  "date": m["date"][:10], "path": m["path"],
                                  "restorable": not here}
        st["templates"].append(tpl)
    for r in records:
        on = None if r["print"] is None else any(r["print"].equal(p) for p in chip)
        tid = next((short_id(p) for p in chip
                    if r["print"] is not None and r["print"].equal(p)), None)
        st["records"].append({"user": r["user"], "finger": r["finger"], "name": r["name"],
                              "path": r["path"], "on_sensor": on, "template": tid,
                              "enrolled": enroll_date(r["print"]) if r["print"] else "",
                              "print_kind": r.get("kind", "unknown"),
                              "error": r.get("error")})
    st["templates"].sort(key=lambda t: (not t["used_by"], t["id"]))
    try:                                            # what other installs know of them
        st["installs"] = share_slots(serial, st["templates"],
                                     {r["template"]: r for r in st["records"]
                                      if r["template"] and r["on_sensor"]})
    except Exception:
        st["installs"] = None
    st["pam"] = pam_state()
    try:
        st["esp"] = esp_summary(serial)
    except Exception:
        st["esp"] = {"path": None, "records": 0}
    if req.get("export"):
        try:
            st["import_offer"] = import_offer(st["user"], serial, chip, records, moved)
        except Exception:
            st["import_offer"] = None
    return st


def do_remove_records(req):
    """Move this install's records aside. The sensor is not touched."""
    _, serial = sensor_usb()
    wanted = {(r["user"], r["finger"]) for r in req.get("records", [])}
    paths = [f"{STORE}/{u}/egismoc/{serial}/{f}" for u, f in wanted
             if re.fullmatch(r"[a-z_][a-z0-9_.-]*", u) and re.fullmatch(FINGER_FILE, f)]
    moved = move_records(paths)
    subprocess.run(["systemctl", "restart", "fprintd"], capture_output=True)
    return {"moved": moved}


def do_delete_other_driver(req):
    """Records enrolled with another driver: delete their templates from the
    sensor (the driver can still delete these old prints, which frees the
    slot), then move the records aside."""
    wanted = {(r["user"], r["finger"]) for r in req.get("records", [])}
    _, serial = sensor_usb()
    records = [r for r in read_records(serial) if (r["user"], r["finger"]) in wanted
               and r.get("kind") not in (None, "sdcp") and r["print"] is not None]
    deleted, left = 0, 0
    with Sensor() as dev:
        for r in records:
            try:
                dev.delete_print_sync(r["print"], None)
                deleted += 1
            except Exception:
                left += 1            # not on the sensor any more: only the record goes
    moved = move_records([r["path"] for r in records])
    return {"deleted": deleted, "moved": moved}


def do_delete_templates(req):
    """Delete templates from the sensor, and move aside any record using them."""
    ids = set(req.get("ids", []))
    _, serial = sensor_usb()
    deleted = []
    with Sensor() as dev:
        if not dev.has_feature(FPrint.DeviceFeature.STORAGE_DELETE):
            raise Fail("This driver cannot delete single templates.")
        chip = dev.list_prints_sync(None)
        records = read_records(serial)
        dead = []
        for p in chip:
            if short_id(p) in ids:
                dev.delete_print_sync(p, None)
                deleted.append(short_id(p))
                dead += [r["path"] for r in records
                         if r["print"] is not None and p.equal(r["print"])]
    moved = move_records(dead)
    return {"deleted": deleted, "moved": moved}


def do_wipe(_req):
    """Delete every template on the sensor and move every record aside."""
    _, serial = sensor_usb()
    with Sensor() as dev:
        chip = dev.list_prints_sync(None)
        if dev.has_feature(FPrint.DeviceFeature.STORAGE_CLEAR):
            dev.clear_storage_sync(None)
        else:
            for p in chip:
                dev.delete_print_sync(p, None)
        left = len(dev.list_prints_sync(None))
    moved = move_records([r["path"] for r in read_records(serial)])
    return {"deleted": len(chip), "left": left, "moved": moved}


def do_reset_install(_req):
    """Start this install again (before reinstalling it, say): clear the slots
    only it uses, delete every user's fingerprint records here for good (and
    the ones moved aside, so nothing shows as "Removed here"), and take it out
    of the shared slots file. Slots another distro still uses stay."""
    _, serial = sensor_usb()
    keep = used_elsewhere(serial)
    records = read_records(serial)
    moved = moved_records(serial)
    prints = [r["print"] for r in records + moved if r["print"] is not None]
    deleted, kept = [], []
    with Sensor() as dev:
        can_delete = dev.has_feature(FPrint.DeviceFeature.STORAGE_DELETE)
        for p in dev.list_prints_sync(None):
            if not any(p.equal(q) for q in prints):
                continue                            # not this install's
            if short_id(p) in keep or not can_delete:
                kept.append(short_id(p))
            else:
                dev.delete_print_sync(p, None)
                deleted.append(short_id(p))
    for r in records + moved:
        try:
            os.remove(r["path"])
        except OSError:
            pass
    for root in (REMOVED_DIR, REPLACED_DIR):        # empty dated folders
        for d in sorted(glob.glob(f"{root}/**/", recursive=True), key=len, reverse=True):
            try:
                os.rmdir(d)
            except OSError:
                pass
    forget_installs([install_key()])
    return {"deleted": deleted, "kept": kept, "records": len(records)}


def do_test(req):
    """Touch test against the user's fingers, reporting WHICH finger matched.

    fprintd only says match / no match when checking all fingers, so this
    asks the sensor directly (identify — the same check login does), with
    fprintd stopped meanwhile. req["finger"] limits it to one finger number.
    Cancelled by a {"action": "cancel"} request, or after 60 seconds."""
    _, serial = sensor_usb()
    user = calling_user()
    only = req.get("finger")
    recs = [r for r in read_records(serial)
            if r["user"] == user and r["print"] is not None
            and (only is None or r["finger"] == str(only))]
    if not recs:
        raise Fail("No fingerprints to test for you on this install.")
    gallery = [r["print"] for r in recs]
    cancel = Gio.Cancellable()
    TEST["cancellable"] = cancel
    timer = threading.Timer(60, cancel.cancel)
    timer.start()
    try:
        with Sensor() as dev:
            for _ in range(3):                  # retry on a poor touch
                try:
                    res = dev.identify_sync(gallery, cancel, None, None)
                except GLib.Error as e:
                    if e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                        return {"result": "cancelled" if timer.is_alive() else "timeout"}
                    if "retry" in str(e.domain):     # fp-device-retry-quark: poor touch
                        last_retry = e.message
                        continue
                    raise
                items = list(res) if isinstance(res, tuple) else [res]
                if items and isinstance(items[0], bool):
                    items = items[1:]
                match = items[0] if items else None
                if match is None:
                    return {"result": "no-match"}
                for r in recs:
                    if match.equal(r["print"]):
                        return {"result": "match", "finger": r["finger"], "name": r["name"]}
                return {"result": "match", "finger": None, "name": "unknown finger"}
            return {"result": "retry", "message": last_retry}
    finally:
        timer.cancel()
        TEST["cancellable"] = None


def run_script(argv, env_extra=None):
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)        # the scripts use the system tools
    env.update(env_extra or {})
    r = subprocess.run(["bash"] + argv, cwd=TOOLS, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    text = ANSI.sub("", (r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise Fail(text or f"{argv[0]} failed ({r.returncode})")
    return {"output": text}


# ── Fingerprint for login and sudo (PAM) — via fingerprint-pam.sh ─────────────
# ── Testing the distro's own libfprint ───────────────────────────────────────
DISTRO_CHECK = os.path.join(HERE, "distro-driver-check.py")
RUN_DROPIN = "/run/systemd/system/fprintd.service.d/" + os.path.basename(DROPIN)


def distro_driver():
    """(word, detail): what the distro's libfprint can do with the reader —
    'sdcp' (from the distro), 'modified' / 'foreign' (an SDCP build from
    another fix), 'plain', 'none', 'unknown' or 'error' — from
    distro-driver-check.py, which drops our LD_LIBRARY_PATH. Run here, as
    root: some libfprint builds open the reader while listing it."""
    try:
        out = subprocess.run([sys.executable, DISTRO_CHECK], capture_output=True, text=True,
                             timeout=60).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return "error", ""
    word = out[0].strip() if out else ""
    detail = out[1].strip() if len(out) > 1 else ""
    return (word, detail) if word in ("sdcp", "modified", "foreign", "plain", "none", "unknown") \
        else ("error", detail)


def do_distro_check(_req):
    kind, detail = distro_driver()
    return {"kind": kind, "detail": detail}


def _dropin_off():
    """Switch our drop-in off: a package's (under /usr/lib) is masked from /run,
    so a crash or reboot can't leave it off; install.sh's (in /etc, which /run
    can't override) is moved aside, and put back at the helper's next start."""
    if DROPIN.startswith("/usr/lib/"):
        os.makedirs(os.path.dirname(RUN_DROPIN), exist_ok=True)
        if os.path.lexists(RUN_DROPIN):
            os.remove(RUN_DROPIN)
        os.symlink("/dev/null", RUN_DROPIN)
    elif os.path.isfile(DROPIN):
        os.replace(DROPIN, DROPIN + ".testing")


def _dropin_on():
    if os.path.islink(RUN_DROPIN):
        os.remove(RUN_DROPIN)
    if os.path.isfile(DROPIN + ".testing") and not os.path.exists(DROPIN):
        os.replace(DROPIN + ".testing", DROPIN)


def restore_dropin_left_off():
    """A distro test interrupted (helper killed): turn the fix back on."""
    if os.path.isfile(DROPIN + ".testing") or os.path.islink(RUN_DROPIN):
        _dropin_on()
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "try-restart", "fprintd"], capture_output=True)


def fprintd_uses_fix():
    """True / False: whether the running fprintd has the fix's library loaded."""
    pid = subprocess.run(["pidof", "fprintd"], capture_output=True, text=True).stdout.split()
    try:
        with open(f"/proc/{pid[0]}/maps") as f:
            return LIBDIR in f.read()
    except (OSError, IndexError):
        return None


def do_test_distro(req):
    """Would fingerprints work without the fix? With our drop-in off, fprintd
    runs on the distro's libfprint; fprintd-verify then checks the user's
    enrolled fingers exactly as login would after removing the fix. The
    drop-in always goes back on afterwards. Cancelled like the test."""
    user = calling_user()
    if not fix_state()[0]:
        raise Fail("fingerprint-fix-sdcp's driver isn't installed: fprintd already uses your "
                   "distro's libfprint.")
    kind, detail = distro_driver()
    if kind != "sdcp":
        return {"result": "unsupported", "driver": kind, "detail": detail}
    _dropin_off()
    try:
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "restart", "fprintd"], capture_output=True)
        subprocess.run(["fprintd-list", user], capture_output=True, timeout=15)   # fprintd up
        if fprintd_uses_fix():
            raise Fail("Could not switch fprintd to the distro's libfprint for the test.")
        proc = subprocess.Popen(["fprintd-verify", user], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        TEST["proc"] = proc
        try:
            out, _ = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {"result": "timeout"}
        finally:
            TEST["proc"] = None
        if proc.returncode < 0:
            return {"result": "cancelled"}
        if "verify-match" in out:
            return {"result": "match", "output": out}
        if "verify-no-match" in out:
            return {"result": "no-match", "output": out}
        return {"result": "error", "output": out}
    finally:
        _dropin_on()
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "restart", "fprintd"], capture_output=True)


LOCAL_CLEANUP = "/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh"   # install.sh's copy


def do_remove_fix(_req):
    """Remove fingerprint-fix-sdcp's driver the way it was installed — only
    offered once the user's fingers matched with the distro's driver. The
    Manager is its own package (galaxybook-fingerprint-manager, or install.sh's
    Manager part) and stays; enrolled fingerprints are kept."""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    env.pop("LD_LIBRARY_PATH", None)
    if MARKER.startswith("/usr/lib/"):              # a package
        for tool, cmd in (("dnf", ["dnf", "remove", "-y", "fingerprint-fix-sdcp"]),
                          ("pacman", ["pacman", "-R", "--noconfirm", "fingerprint-fix-sdcp"]),
                          ("apt-get", ["apt-get", "remove", "-y", "fingerprint-fix-sdcp"])):
            if shutil.which(tool):
                break
        else:
            raise Fail("No dnf, pacman or apt-get found to remove the package.")
    elif os.path.isfile(LOCAL_CLEANUP):            # install.sh's copy: its own cleanup
        cmd = [LOCAL_CLEANUP]
    else:
        raise Fail("fingerprint-fix-sdcp's removal script wasn't found.")
    try:
        r = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise Fail("Removing fingerprint-fix-sdcp took too long — is another update running?")
    out = ANSI.sub("", (r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise Fail(out or f"{cmd[0]} failed ({r.returncode})")
    subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    subprocess.run(["systemctl", "try-restart", "fprintd"], capture_output=True)
    return {"output": out}


def pam_state():
    try:
        out = run_script([os.path.join(TOOLS, "fingerprint-pam.sh"), "status", "--short"])
        state, method, detail = (out["output"].splitlines()[-1].split("|") + ["", ""])[:3]
        return {"state": state, "method": method, "detail": detail}
    except Exception as e:
        return {"state": "unavailable", "method": "", "detail": str(e)}


def do_pam(req):
    op = req.get("op")
    if op not in ("enable", "disable"):
        raise Fail("op must be enable or disable")
    out = run_script([os.path.join(TOOLS, "fingerprint-pam.sh"), op])
    return dict(pam_state(), output=out["output"])


# ── Putting moved-aside records back ──────────────────────────────────────────
def moved_records(serial):
    """Records in removed-fingerprints/ and replaced-fingerprints/ for this sensor."""
    out = []
    for kind, root in (("removed", REMOVED_DIR), ("replaced", REPLACED_DIR)):
        for path in sorted(glob.glob(f"{root}/*/*/egismoc/{serial}/*")):
            if not os.path.isfile(path) or os.path.islink(path):
                continue
            date, user = os.path.relpath(path, root).split("/")[:2]
            finger = os.path.basename(path)
            if not (re.fullmatch(r"[a-z_][a-z0-9_.-]*", user) and re.fullmatch(FINGER_FILE, finger)):
                continue
            rec = {"kind": kind, "date": date, "user": user, "finger": finger,
                   "name": finger_name(finger), "path": path, "print": None}
            try:
                with open(path, "rb") as f:
                    rec["print"] = FPrint.Print.deserialize(f.read())
            except Exception:
                pass
            out.append(rec)
    return out


def prune_moved(serial, records):
    """Delete moved-aside records that are back in use: the same user has the
    same slot here again (imported, restored, undone). Restoring one could
    only duplicate it. Returns how many went."""
    gone = 0
    for m in moved_records(serial):
        if m["print"] is None:
            continue
        if any(r["user"] == m["user"] and r["print"] is not None and r["print"].equal(m["print"])
               for r in records):
            try:
                os.remove(m["path"])
                gone += 1
            except OSError:
                pass
    if gone:
        for root in (REMOVED_DIR, REPLACED_DIR):    # empty dated folders
            for d in sorted(glob.glob(f"{root}/**/", recursive=True), key=len, reverse=True):
                if d.rstrip("/") != root:
                    try:
                        os.rmdir(d)
                    except OSError:
                        pass
    return gone


def do_list_moved(_req):
    _, serial = sensor_usb()
    try:
        prune_moved(serial, read_records(serial))
    except Exception:
        pass
    recs = moved_records(serial)
    with Sensor() as dev:
        chip = dev.list_prints_sync(None)
    result = []
    for r in recs:
        dest = f"{STORE}/{r['user']}/egismoc/{serial}/{r['finger']}"
        try:
            pwd.getpwnam(r["user"])
            user_ok = True
        except KeyError:
            user_ok = False
        result.append({k: r[k] for k in ("kind", "date", "user", "finger", "name", "path")} | {
            "on_sensor": r["print"] is not None and any(r["print"].equal(p) for p in chip),
            "exists": os.path.exists(dest), "user_ok": user_ok})
    result.sort(key=lambda r: r["date"], reverse=True)
    return {"records": result}


def do_restore(req):
    """Move records back into /var/lib/fprint — only if their template is still
    on the sensor and that finger isn't enrolled here again since."""
    _, serial = sensor_usb()
    wanted = set(req.get("paths", []))
    recs = [r for r in moved_records(serial) if r["path"] in wanted]
    with Sensor() as dev:
        chip = dev.list_prints_sync(None)
    restored, skipped = [], []
    for r in recs:
        label = f"{r['name']} ({r['user']})"
        dest_dir = f"{STORE}/{r['user']}/egismoc/{serial}"
        dest = f"{dest_dir}/{r['finger']}"
        try:
            pwd.getpwnam(r["user"])
        except KeyError:
            skipped.append(f"{label}: no such user here")
            continue
        if r["print"] is None or not any(r["print"].equal(p) for p in chip):
            skipped.append(f"{label}: its template is no longer on the sensor")
            continue
        if os.path.exists(dest):
            skipped.append(f"{label}: that finger is enrolled here again")
            continue
        for d in (f"{STORE}/{r['user']}", f"{STORE}/{r['user']}/egismoc", dest_dir):
            os.makedirs(d, exist_ok=True)
            os.chmod(d, 0o700)
        shutil.move(r["path"], dest)
        os.chmod(dest, 0o600)
        restored.append(label)
        # Tidy the now-empty folders left behind in the safety folder.
        d = os.path.dirname(r["path"])
        for root in (REMOVED_DIR, REPLACED_DIR):
            while d.startswith(root + "/") and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
    if restored:
        if shutil.which("restorecon"):                 # SELinux (Fedora)
            subprocess.run(["restorecon", "-R", STORE], capture_output=True)
        subprocess.run(["systemctl", "restart", "fprintd"], capture_output=True)
    return {"restored": restored, "skipped": skipped}


def do_forget_install(req):
    """Take another install, one that's gone, out of the shared slots file,
    and clear the slots ("ids") only it used, when asked to."""
    key = str(req.get("key") or "")
    if not re.fullmatch(r"[0-9a-f]{12}", key) or key == install_key():
        raise Fail("That install can't be forgotten.")
    out = {"forgotten": forget_installs([key])}
    if req.get("ids"):
        out.update(do_delete_templates({"ids": req["ids"]}))
    return out


def do_backup_slots(_req):
    """The shared slots file (with the records), for a backup the window saves."""
    data = read_file()
    if not data.get("sensors"):
        raise Fail("There's nothing to back up yet: no fingerprint records on the EFI partition.")
    return {"data": data}


def do_restore_slots(req):
    """Merge a backup of the shared slots file into it (nothing there is changed)."""
    try:
        added = merge_backup(req.get("data"))
    except ValueError as e:
        raise Fail(f"That file isn't a fingerprint records backup ({e}).")
    if added is None:
        raise Fail("The EFI partition wasn't found, so there's nowhere to restore to.")
    return {"added": added}


def do_export(req):
    out = req.get("file") or ""
    argv = [os.path.join(TOOLS, "export-fingerprint.sh")] + ([out] if out else [])
    return run_script(argv, {"SUDO_USER": calling_user()})


def do_import(req):
    argv = [os.path.join(TOOLS, "import-fingerprint.sh"), "--user", calling_user()]
    if req.get("replace"):
        argv.append("--replace")
    fingers = [f for f in req.get("fingers") or [] if re.fullmatch(FINGER_FILE, str(f))]
    if fingers:
        argv += ["--fingers", ",".join(fingers)]
    dead = [f for f in req.get("dead") or [] if re.fullmatch(FINGER_FILE, str(f))]
    if dead and not req.get("replace"):
        argv += ["--dead", ",".join(dead)]          # gone from the sensor: replaced
    if req.get("file"):
        argv.append(req["file"])
    return run_script(argv)


ACTIONS = {"status": do_status, "remove_records": do_remove_records,
           "test_distro": do_test_distro, "distro_check": do_distro_check,
           "remove_fix": do_remove_fix,
           "delete_other_driver": do_delete_other_driver,
           "delete_templates": do_delete_templates, "wipe": do_wipe,
           "export": do_export, "import": do_import, "import_offer": do_import_offer,
           "backup_slots": do_backup_slots, "restore_slots": do_restore_slots, "test": do_test,
           "pam": do_pam, "forget_install": do_forget_install,
           "reset_install": do_reset_install, "list_moved": do_list_moved, "restore": do_restore}


def handle(req):
    try:
        fn = ACTIONS.get(req.get("action"))
        if not fn:
            raise Fail(f"Unknown action: {req.get('action')}")
        reply = {"ok": True, "result": fn(req)}
    except Fail as e:
        reply = {"ok": False, "error": str(e)}
    except Exception as e:                           # report, keep running
        reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    with OUT_LOCK:
        print(json.dumps(reply), flush=True)


def main():
    if os.geteuid() != 0:
        sys.exit("This is started by fingerprint-manager.py (via pkexec), not by hand.")
    restore_dropin_left_off()
    print(json.dumps({"ready": True}), flush=True)
    worker = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if req.get("action") == "cancel":            # no reply of its own
            c = TEST["cancellable"]
            if c:
                c.cancel()
            p = TEST["proc"]
            if p and p.poll() is None:
                p.terminate()
            continue
        if req.get("action") in ("test", "test_distro"):
            # Runs alongside this loop, so a "cancel" can still be read.
            worker = threading.Thread(target=handle, args=(req,), daemon=True)
            worker.start()
            continue
        if worker and worker.is_alive():
            worker.join()
        handle(req)
    if worker and worker.is_alive():
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
