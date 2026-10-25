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
# export-fingerprint.sh from this folder, with all their checks.
#
# Records are never deleted: anything removed from /var/lib/fprint is moved to
# /var/lib/samsung-galaxybook/removed-fingerprints/<date>/ (last 5 kept), the
# same folder the boot check uses.
# =============================================================================
import os
import sys

LIBDIR = "/usr/local/lib/libfprint-egismoc-sdcp"
MARKER = "/etc/samsung-galaxybook-egismoc-sdcp.installed"
DROPIN = "/etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf"

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
import subprocess
import time

HERE = os.path.dirname(os.path.realpath(__file__))
STORE = "/var/lib/fprint"
REMOVED_DIR = "/var/lib/samsung-galaxybook/removed-fingerprints"
FINGERS = ["unknown", "left-thumb", "left-index-finger", "left-middle-finger",
           "left-ring-finger", "left-little-finger", "right-thumb",
           "right-index-finger", "right-middle-finger", "right-ring-finger",
           "right-little-finger"]
ANSI = re.compile(r"\x1b\[[0-9;]*m")

FPrint = None
GI_ERROR = None
try:
    import gi
    gi.require_version("FPrint", "2.0")
    from gi.repository import FPrint
except (ImportError, ValueError) as e:
    GI_ERROR = str(e)


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


def finger_name(n):
    return FINGERS[int(n)] if n.isdigit() and 0 < int(n) <= 10 else n


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
                rec["print"] = FPrint.Print.deserialize(f.read())
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
def do_status(_req):
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
        chip = dev.list_prints_sync(None) if st["features"]["STORAGE_LIST"] else []
    records = read_records(serial)
    for p in chip:
        users = [f"{r['user']} {r['name']}" for r in records
                 if r["print"] is not None and p.equal(r["print"])]
        st["templates"].append({"id": short_id(p), "used_by": users})
    for r in records:
        on = None if r["print"] is None else any(r["print"].equal(p) for p in chip)
        st["records"].append({"user": r["user"], "finger": r["finger"], "name": r["name"],
                              "path": r["path"], "on_sensor": on,
                              "enrolled": enroll_date(r["print"]) if r["print"] else "",
                              "error": r.get("error")})
    st["templates"].sort(key=lambda t: (not t["used_by"], t["id"]))
    return st


def do_remove_records(req):
    """Move this install's records aside. The sensor is not touched."""
    _, serial = sensor_usb()
    wanted = {(r["user"], r["finger"]) for r in req.get("records", [])}
    paths = [f"{STORE}/{u}/egismoc/{serial}/{f}" for u, f in wanted
             if re.fullmatch(r"[a-z_][a-z0-9_.-]*", u) and re.fullmatch(r"[0-9]+", f)]
    moved = move_records(paths)
    subprocess.run(["systemctl", "restart", "fprintd"], capture_output=True)
    return {"moved": moved}


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


def run_script(argv, env_extra=None):
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)        # the scripts use the system tools
    env.update(env_extra or {})
    r = subprocess.run(["bash"] + argv, cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    text = ANSI.sub("", (r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise Fail(text or f"{argv[0]} failed ({r.returncode})")
    return {"output": text}


def do_export(req):
    out = req.get("file") or ""
    argv = [os.path.join(HERE, "export-fingerprint.sh")] + ([out] if out else [])
    return run_script(argv, {"SUDO_USER": calling_user()})


def do_import(req):
    argv = [os.path.join(HERE, "import-fingerprint.sh"), "--user", calling_user()]
    if req.get("replace"):
        argv.append("--replace")
    if req.get("file"):
        argv.append(req["file"])
    return run_script(argv)


ACTIONS = {"status": do_status, "remove_records": do_remove_records,
           "delete_templates": do_delete_templates, "wipe": do_wipe,
           "export": do_export, "import": do_import}


def main():
    if os.geteuid() != 0:
        sys.exit("This is started by fingerprint-manager.py (via pkexec), not by hand.")
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            fn = ACTIONS.get(req.get("action"))
            if not fn:
                raise Fail(f"Unknown action: {req.get('action')}")
            reply = {"ok": True, "result": fn(req)}
        except Fail as e:
            reply = {"ok": False, "error": str(e)}
        except Exception as e:                       # report, keep running
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
