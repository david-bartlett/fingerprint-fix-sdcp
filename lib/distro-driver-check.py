#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book — fingerprint-fix-sdcp: can the distro's own libfprint
# drive the Galaxy Book's Egis reader over SDCP?
# =============================================================================
#   python3 distro-driver-check.py        → prints one word, exit code:
#     sdcp     0  the distro's egismoc driver is an SDCP driver (the fix may no
#                 longer be needed: confirm with the Manager's test)
#     plain    1  it handles the reader, but without SDCP (the distro's
#                 egismoc before SDCP: 1c7a:05a1 only, and it can't keep prints)
#     none     1  no driver for the reader in the distro's libfprint, or the
#                 reader isn't on USB
#     error    3  libfprint's Python bindings couldn't be loaded
#
# Always runs on the distro's libfprint: started with the fix's LD_LIBRARY_PATH,
# it starts itself again without it. Only lists the USB devices (nothing is
# opened), so it needs no root and fprintd can keep running.
#
# Used by install.sh (Step 3), the monitor (after a distro libfprint update)
# and the Fingerprint Manager. For testing, CHECK_DRIVER=<driver id> looks for
# another driver (e.g. virtual_sdcp, with FP_VIRTUAL_SDCP=1).
# =============================================================================
import os
import sys

if os.environ.get("LD_LIBRARY_PATH"):
    env = {k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}
    os.execve(sys.executable, [sys.executable, os.path.realpath(__file__)] + sys.argv[1:], env)

DRIVER = os.environ.get("CHECK_DRIVER", "egismoc")
SDCP_CLASS = "FpSdcpDevice"     # the shared SDCP device class SDCP drivers derive from


def answer(word, code, detail=""):
    print(word)
    if detail:
        print(detail, file=sys.stderr)
    sys.exit(code)


try:
    import gi
    gi.require_version("FPrint", "2.0")
    from gi.repository import FPrint
except (ImportError, ValueError) as e:
    answer("error", 3, f"libfprint's Python bindings: {e}")


def class_names(obj):
    """The object's GType and every parent type's name."""
    names, t = [], obj.__gtype__
    while t and t.name not in ("GObject", "invalid") and len(names) < 32:
        names.append(t.name)
        t = t.parent
    return names


ctx = FPrint.Context()
ctx.enumerate()
for dev in ctx.get_devices():
    if dev.get_driver() != DRIVER:
        continue
    names = class_names(dev)
    if SDCP_CLASS in names:
        answer("sdcp", 0, " → ".join(names))
    answer("plain", 1, " → ".join(names))
answer("none", 1)
