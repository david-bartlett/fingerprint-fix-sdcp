#!/usr/bin/env python3
# =============================================================================
# fingerprint-fix-sdcp — show a notification with buttons straight over
# D-Bus, and print the button pressed (used on GNOME by notify-update.sh and
# notify-open-manager.sh)
# =============================================================================
#   notify-dbus.py URGENCY APP ICON TITLE BODY [KEY LABEL]...
#
# URGENCY 0-2 (2 = critical). KEY "default" is a click on the notification
# itself. Prints the KEY of the button pressed, or nothing if the notification
# was closed; exits 0. Exits 2 if it couldn't be shown (no PyGObject, no
# session bus), so the caller can fall back to notify-send.
#
# NOTIFY_WATCH_FILE / NOTIFY_WATCH_VERSION (environment): every 2 seconds,
# read the installed version from that file; once it's that version or
# newer (updated another way while this was on screen), close the
# notification - it's this program's own, so the desktop allows it - and
# print nothing, as when it's closed by hand.
#
# The same helper as galaxybook-fan's (keep them in step). Why not
# notify-send: on David's Ubuntu 26.04 GNOME lists "actions" in its
# capabilities and shows buttons when asked over D-Bus, but notify-send 0.8.8
# says "Actions are not supported by this notifications server" and shows it
# without them. GNOME sends the button press only to the program that made
# the notification, so this one stays until it's pressed or closed.
# =============================================================================
import os
import re
import sys

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    sys.exit(2)

BUS = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


def _version(text):
    """(1, 2, 3) from '1.2.3', or None."""
    m = re.fullmatch(r"\s*v?(\d+(?:\.\d+)*)\s*", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _installed(path):
    try:
        with open(path) as f:
            return _version(f.read())
    except OSError:
        return None


def main(argv):
    if len(argv) < 6 or len(argv[6:]) % 2:
        print("Usage: notify-dbus.py URGENCY APP ICON TITLE BODY [KEY LABEL]...", file=sys.stderr)
        return 2
    urgency, app, icon, title, body = argv[1:6]
    actions = argv[6:]
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    except GLib.Error:
        return 2
    loop = GLib.MainLoop()
    state = {"id": None, "choice": ""}

    def on_signal(_conn, _sender, _path, _iface, name, params):
        args = params.unpack()
        if state["id"] is None or args[0] != state["id"]:
            return
        if name == "ActionInvoked":
            state["choice"] = args[1]
        loop.quit()             # a button, or closed (it closes after a button too)

    for sig in ("ActionInvoked", "NotificationClosed"):
        bus.signal_subscribe(BUS, BUS, sig, PATH, None, Gio.DBusSignalFlags.NONE, on_signal)
    try:
        state["id"] = bus.call_sync(
            BUS, PATH, BUS, "Notify",
            GLib.Variant("(susssasa{sv}i)", (app, 0, icon, title, body, actions,
                                              {"urgency": GLib.Variant("y", int(urgency))}, 0)),
            GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
    except (GLib.Error, ValueError):
        return 2

    watch, wanted = os.environ.get("NOTIFY_WATCH_FILE"), _version(os.environ.get("NOTIFY_WATCH_VERSION"))

    def updated():
        have = _installed(watch)
        if have and have >= wanted:
            try:
                bus.call_sync(BUS, PATH, BUS, "CloseNotification", GLib.Variant("(u)", (state["id"],)),
                              None, Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error:
                pass
            loop.quit()                 # NotificationClosed may follow; nothing to print
            return False
        return True                     # look again in 2 s

    if watch and wanted:
        GLib.timeout_add_seconds(2, updated)
    loop.run()
    if state["choice"]:
        print(state["choice"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
