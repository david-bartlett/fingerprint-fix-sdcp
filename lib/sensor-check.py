#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book — Fingerprint Manager: boot-time sensor check
# =============================================================================
# Compares fprintd's fingerprint records with the templates actually stored on
# the sensor, and prints every record whose template is gone (typically
# removed by Windows Hello after booting Windows with its fingerprint device
# enabled). Run at boot BEFORE fprintd starts, so it has the sensor to itself.
#
# Works with whichever libfprint drives the reader: fingerprint-fix-sdcp's
# driver when it is installed (it starts itself again with that library), the
# distro's otherwise — so it keeps working once a distro's own libfprint has
# SDCP and the driver package is removed. (It replaces lib/sensor-check.c,
# which only ran against this fix's library.)
#
#   sensor-check.py                        check the sensor
#     Output:  OTHERDRIVER <kind> <user> <finger> <path> for each record
#              enrolled with another driver (not SDCP: never matches, not
#              compared), then MISSING <user> <finger-number> <record-path>
#              for each lost fingerprint, or OK <n> records, <m> templates
#     Exit:    0 all found (or nothing enrolled), 1 at least one missing,
#              2 could not check (no sensor, open/list failed, ...)
#
#   sensor-check.py --set-owner USER IN OUT
#     Reads the fprintd record IN, sets its owner to USER and writes it to OUT,
#     so a fingerprint exported by one user can be imported for another.
#     Doesn't touch the sensor. Exit 0 on success, 2 on error.
#
# Testing only:
#   FPRINT_STORE          use this folder instead of /var/lib/fprint
#   SENSOR_CHECK_DRIVER   look for this driver instead of egismoc
#                         (e.g. libfprint's virtual_device_storage)
#   SENSOR_CHECK_SETTLE   milliseconds to wait after opening the sensor
# =============================================================================
import os
import sys
import time

# fingerprint-fix-sdcp's driver, when it is installed (package, then install.sh)
FIX_LIBS = ("/usr/lib/fingerprint-fix-sdcp", "/usr/local/lib/libfprint-egismoc-sdcp")
lib = next((d for d in FIX_LIBS if os.path.isfile(os.path.join(d, "libfprint-2.so.2"))), None)
if lib and os.environ.get("LD_LIBRARY_PATH") != lib:
    os.execve(sys.executable, [sys.executable, os.path.realpath(__file__)] + sys.argv[1:],
              dict(os.environ, LD_LIBRARY_PATH=lib))

try:
    import gi
    gi.require_version("FPrint", "2.0")
    from gi.repository import FPrint, GLib
except (ImportError, ValueError) as e:
    print(f"libfprint's Python bindings couldn't be loaded: {e}", file=sys.stderr)
    sys.exit(2)

# libfprint writes a record as "FP3" + a GVariant "(issbymsmsia{sv}v)" whose
# first field is the print type: 1 raw (the distro's pre-SDCP egismoc and
# other non-SDCP builds), 2 nbis, 3 sdcp (this driver).
PRINT_KINDS = {1: "raw", 2: "nbis", 3: "sdcp"}


def print_kind(data):
    if len(data) >= 7 and data[:3] == b"FP3":
        return PRINT_KINDS.get(int.from_bytes(data[3:7], "little"), "unknown")
    return "unknown"


def set_owner(user, src, dst):
    try:
        with open(src, "rb") as f:
            p = FPrint.Print.deserialize(f.read())
    except OSError as e:
        print(f"Cannot read {src}: {e}", file=sys.stderr)
        return 2
    except GLib.Error:
        print(f"Not a valid fingerprint record: {src}", file=sys.stderr)
        return 2
    try:
        p.set_username(user)
        data = p.serialize()
        data = bytes(data[0] if isinstance(data, tuple) else data)
        with open(dst, "wb") as f:
            f.write(data)
    except (OSError, GLib.Error) as e:
        print(f"Cannot write {dst}: {e}", file=sys.stderr)
        return 2
    return 0


def load_records(store, driver, device_id):
    """Every fprintd record for this sensor: <store>/<user>/<driver>/<device-id>/<finger>."""
    out = []
    try:
        users = sorted(os.listdir(store))
    except OSError:
        return out
    for user in users:
        folder = os.path.join(store, user, driver, device_id)
        try:
            fingers = sorted(os.listdir(folder))
        except OSError:
            continue
        for finger in fingers:
            path = os.path.join(folder, finger)
            try:
                with open(path, "rb") as f:
                    data = f.read()
                p = FPrint.Print.deserialize(data)
            except (OSError, GLib.Error):
                print(f"Skipping unreadable record {path}", file=sys.stderr)
                continue
            out.append({"user": user, "finger": finger, "path": path,
                        "kind": print_kind(data), "print": p})
    return out


def check_sensor():
    store = os.environ.get("FPRINT_STORE", "/var/lib/fprint")
    driver = os.environ.get("SENSOR_CHECK_DRIVER", "egismoc")
    settle = int(os.environ.get("SENSOR_CHECK_SETTLE", "0") or 0)

    ctx = FPrint.Context()
    ctx.enumerate()
    dev = next((d for d in ctx.get_devices() if d.get_driver() == driver), None)
    if dev is None:
        print(f"No {driver} fingerprint sensor found", file=sys.stderr)
        return 2

    records = load_records(store, driver, dev.get_device_id())
    # Records enrolled with another driver (e.g. the distro's non-SDCP egismoc)
    # can't be identified over SDCP and never match: report them, and leave
    # them out of the comparison — they are not "gone from the sensor". Only a
    # type we can name and that isn't SDCP: an unreadable type is compared.
    kept = []
    for r in records:
        if r["kind"] not in ("sdcp", "unknown"):
            print(f"OTHERDRIVER {r['kind']} {r['user']} {r['finger']} {r['path']}")
        else:
            kept.append(r)
    if not kept:
        print("OK 0 records")
        return 0                       # nothing enrolled: no need to touch the sensor

    if not dev.has_feature(FPrint.DeviceFeature.STORAGE_LIST):
        print("Driver cannot list stored templates", file=sys.stderr)
        return 2
    try:
        dev.open_sync(None)
    except GLib.Error as e:
        print(f"Could not open sensor: {e.message}", file=sys.stderr)
        return 2
    try:
        if settle:
            ctx_main = GLib.MainContext.default()
            until = time.monotonic() + settle / 1000
            while time.monotonic() < until:
                ctx_main.iteration(False)
                time.sleep(0.01)
        stored = dev.list_prints_sync(None)
    except GLib.Error as e:
        print(f"Could not list templates: {e.message}", file=sys.stderr)
        return 2
    finally:
        try:
            dev.close_sync(None)
        except GLib.Error:
            pass

    missing = 0
    for r in kept:
        if not any(r["print"].equal(t) for t in stored):
            print(f"MISSING {r['user']} {r['finger']} {r['path']}")
            missing += 1
    if not missing:
        print(f"OK {len(kept)} records, {len(stored)} templates on sensor")
    return 1 if missing else 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--set-owner":
        if len(sys.argv) != 5 or not sys.argv[2]:
            print(f"Usage: {sys.argv[0]} --set-owner USER IN OUT", file=sys.stderr)
            sys.exit(2)
        sys.exit(set_owner(*sys.argv[2:5]))
    sys.exit(check_sensor())
