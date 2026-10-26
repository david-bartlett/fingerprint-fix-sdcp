#!/usr/bin/env python3
# fpcheck.py — read-only: show the fingerprint driver's features and the
# templates stored on the sensor.
#
# Run with fprintd stopped:
#   sudo systemctl stop fprintd
#   sudo LD_LIBRARY_PATH=/usr/local/lib/libfprint-egismoc-sdcp python3 fpcheck.py
#   sudo systemctl start fprintd
import gi
gi.require_version("FPrint", "2.0")
from gi.repository import FPrint

ctx = FPrint.Context()
ctx.enumerate()
devs = ctx.get_devices()
if not devs:
    raise SystemExit("No fingerprint device found (is fprintd still running?)")
dev = devs[0]
print("Driver:", dev.get_driver(), "| Device ID:", dev.get_device_id(), "|", dev.get_name())

dev.open_sync(None)
try:
    for f in ("IDENTIFY", "VERIFY", "STORAGE", "STORAGE_LIST", "STORAGE_DELETE", "STORAGE_CLEAR", "DUPLICATES_CHECK"):
        feat = getattr(FPrint.DeviceFeature, f, None)
        if feat is not None:
            print(f"{f:17}", dev.has_feature(feat))

    if dev.has_feature(FPrint.DeviceFeature.STORAGE_LIST):
        prints = dev.list_prints_sync(None)
        print(f"\n{len(prints)} print(s) on sensor")
finally:
    dev.close_sync(None)
