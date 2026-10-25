#!/usr/bin/env python3
# fpclean.py — delete orphaned fingerprint templates from the sensor.
# Keeps every template this install has an fprintd record for.
#
# Run with fprintd stopped:
#   sudo systemctl stop fprintd
#   sudo python3 fpclean.py
#   sudo systemctl start fprintd
import gi, os, glob
gi.require_version("FPrint", "2.0")
from gi.repository import FPrint

ctx = FPrint.Context()
ctx.enumerate()
devs = ctx.get_devices()
if not devs:
    raise SystemExit("No fingerprint device found (is fprintd still running?)")
dev = devs[0]
dev.open_sync(None)

try:
    if not dev.has_feature(FPrint.DeviceFeature.STORAGE_DELETE):
        raise SystemExit("This driver cannot delete individual templates.")

    chip = dev.list_prints_sync(None)

    # Records for this device, for every user on this install
    host = []
    for path in glob.glob(f"/var/lib/fprint/*/{dev.get_driver()}/{dev.get_device_id()}/*"):
        with open(path, "rb") as fh:
            user = path.split("/")[4]
            finger = os.path.basename(path)
            host.append((user, finger, FPrint.Print.deserialize(fh.read())))

    orphans = []
    print(f"{len(chip)} template(s) on the sensor:")
    for i, p in enumerate(chip):
        owner = next(((u, f) for u, f, h in host if p.equal(h)), None)
        if owner:
            print(f"  Slot {i}: KEEP   — {owner[0]}, finger {owner[1]}")
        else:
            print(f"  Slot {i}: orphan — no record on this install")
            orphans.append((i, p))

    if not orphans:
        print("\nNo orphans — nothing to delete.")
        raise SystemExit(0)

    print("\nOrphans may belong to Windows Hello or another Linux install.")
    print("Deleting them breaks fingerprint login there (re-enrol to fix).")
    for i, p in orphans:
        if input(f"Delete slot {i}? [y/N] ").strip().lower().startswith("y"):
            dev.delete_print_sync(p, None)
            print(f"  Slot {i} deleted")
        else:
            print(f"  Slot {i} kept")

    left = dev.list_prints_sync(None)
    print(f"\n{len(left)} template(s) now on the sensor.")
finally:
    dev.close_sync(None)
