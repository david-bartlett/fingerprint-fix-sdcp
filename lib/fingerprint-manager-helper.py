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

# (marker, library folder, fprintd drop-in) of each way the fix is installed:
# a package first, then install.sh. Keep in step with lib/fixpaths.sh.
LAYOUTS = [
    ("/usr/lib/fingerprint-fix-sdcp/installed",
     "/usr/lib/fingerprint-fix-sdcp",
     "/usr/lib/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf"),
    ("/etc/samsung-galaxybook-egismoc-sdcp.installed",
     "/usr/local/lib/libfprint-egismoc-sdcp",
     "/etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf"),
]
MARKER, LIBDIR, DROPIN = next((l for l in LAYOUTS if os.path.isfile(l[0])), LAYOUTS[-1])

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


def fix_state():
    marker = None
    if os.path.isfile(MARKER):
        with open(MARKER) as f:
            marker = f.read().strip()
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
class Sensor:
    def __enter__(self):
        subprocess.run(["systemctl", "stop", "fprintd"], capture_output=True)
        last = None
        for _ in range(3):
            ctx = FPrint.Context()
            ctx.enumerate()
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
def export_offer(user, serial, chip, records):
    """Fingers in the user's ~/fingerprint-export.tgz worth importing here: made
    on this sensor, still stored on it, and not already the user's (same finger,
    or the same template under another finger). None when there is no such
    file or nothing in it to offer. Only that one file is ever read."""
    try:
        pw = pwd.getpwnam(user)
        path = os.path.join(pw.pw_dir, EXPORT_NAME)
        st = os.lstat(path)
    except (KeyError, OSError):
        return None
    if not stat.S_ISREG(st.st_mode) or st.st_size > (1 << 20) or st.st_uid not in (0, pw.pw_uid):
        return None
    mine = [r for r in records if r["user"] == user]
    have = {r["finger"] for r in mine}
    offer = []
    try:
        with tarfile.open(path, "r:gz") as tar:
            for m in tar.getmembers():
                mt = re.fullmatch(r"[a-z_][a-z0-9_.-]*/egismoc/([A-Za-z0-9._-]+)/([1-9a])", m.name)
                if not mt or not m.isfile() or m.size > 65536 or mt.group(1) != serial \
                        or mt.group(2) in have:
                    continue
                p = FPrint.Print.deserialize(tar.extractfile(m).read())
                if not any(p.equal(c) for c in chip):
                    continue                     # gone from the sensor: would never match
                if any(r["print"] is not None and p.equal(r["print"]) for r in mine):
                    continue                     # already here under another finger
                offer.append({"finger": mt.group(2), "name": finger_name(mt.group(2))})
    except Exception:
        return None
    if not offer:
        return None
    offer.sort(key=lambda f: int(f["finger"], 16))
    return {"file": path, "id": f"{int(st.st_mtime)}-{st.st_size}", "fingers": offer}


def do_status(req):
    pid, serial = sensor_usb()
    ok, marker = fix_state()
    st = {"user": calling_user(), "usb_id": f"1c7a:{pid}" if pid else None,
          "serial": serial, "fix_installed": ok, "marker": marker,
          "records": [], "templates": [], "features": {}}
    if not pid:
        raise Fail("EgisTec fingerprint sensor (1c7a:05a5 / 1c7a:05a1) not found.")
    if not ok:
        raise Fail("fingerprint-fix-sdcp is not installed (or incomplete) here.\n"
                   "Install it first: sudo bash install.sh")
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
    st["pam"] = pam_state()
    if req.get("export"):
        st["export_offer"] = export_offer(st["user"], serial, chip, records)
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
    another fix), 'plain', 'none' or 'error' — from distro-driver-check.py,
    which drops our LD_LIBRARY_PATH."""
    try:
        out = subprocess.run([sys.executable, DISTRO_CHECK], capture_output=True, text=True,
                             timeout=60).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return "error", ""
    word = out[0].strip() if out else ""
    detail = out[1].strip() if len(out) > 1 else ""
    return (word, detail) if word in ("sdcp", "modified", "foreign", "plain", "none") \
        else ("error", detail)


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


def do_list_moved(_req):
    _, serial = sensor_usb()
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
    if req.get("file"):
        argv.append(req["file"])
    return run_script(argv)


ACTIONS = {"status": do_status, "remove_records": do_remove_records,
           "test_distro": do_test_distro,
           "delete_other_driver": do_delete_other_driver,
           "delete_templates": do_delete_templates, "wipe": do_wipe,
           "export": do_export, "import": do_import, "test": do_test,
           "pam": do_pam, "list_moved": do_list_moved, "restore": do_restore}


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
