#!/usr/bin/env python3
# fpslots.py — read-only snapshot of every template on the fingerprint sensor.
#
# Each template gets a short ID (a hash of what the sensor reports for it),
# so two snapshots can be compared to see exactly which templates were added
# or removed. Templates this install has an fprintd record for are named
# (user + finger); anything else is shown as "unknown" (Windows, another
# distro, or a leftover).
#
# Run with fprintd stopped, using the egismoc SDCP library:
#   sudo systemctl stop fprintd
#   sudo LD_LIBRARY_PATH=/usr/local/lib/libfprint-egismoc-sdcp python3 fpslots.py | tee before.txt
#   sudo systemctl start fprintd
#
# Compare two snapshots:   diff before.txt after.txt
import gi, glob, hashlib, os, datetime
gi.require_version("FPrint", "2.0")
from gi.repository import FPrint

FINGERS = ["unknown", "left-thumb", "left-index-finger", "left-middle-finger",
           "left-ring-finger", "left-little-finger", "right-thumb",
           "right-index-finger", "right-middle-finger", "right-ring-finger",
           "right-little-finger"]

def short_id(p):
    data = p.serialize()
    if isinstance(data, tuple):          # PyGObject may return (ok, data)
        data = next(x for x in data if not isinstance(x, bool))
    return hashlib.sha1(bytes(data)).hexdigest()[:10]   # bytes or list of ints

ctx = FPrint.Context()
ctx.enumerate()
devs = [d for d in ctx.get_devices() if d.get_driver() == "egismoc"]
if not devs:
    raise SystemExit("No egismoc sensor found (is fprintd still running? LD_LIBRARY_PATH set?)")
dev = devs[0]
dev.open_sync(None)
try:
    chip = dev.list_prints_sync(None)
    records = []
    for path in glob.glob(f"/var/lib/fprint/*/egismoc/{dev.get_device_id()}/*"):
        with open(path, "rb") as fh:
            n = os.path.basename(path)
            name = FINGERS[int(n)] if n.isdigit() and int(n) <= 10 else n
            records.append((path.split("/")[4], name, FPrint.Print.deserialize(fh.read())))

    print(f"# {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  sensor {dev.get_device_id()}  "
          f"{len(chip)} template(s), {len(records)} record(s) on this install")
    for p in sorted(chip, key=short_id):
        owner = next((f"{u} {f}" for u, f, r in records if p.equal(r)), "unknown")
        print(f"{short_id(p)}  {owner}")
    for u, f, r in records:
        if not any(r.equal(p) for p in chip):
            print(f"# record with NO template on sensor: {u} {f}")
finally:
    dev.close_sync(None)
