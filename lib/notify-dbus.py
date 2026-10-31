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
# The same helper as galaxybook-fan's. Why not notify-send: on David's
# Ubuntu 26.04 GNOME lists "actions" in its capabilities and shows buttons
# when asked over D-Bus, but notify-send 0.8.8 says "Actions are not
# supported by this notifications server" and shows it without them. GNOME sends the button press only to the program that made
# the notification, so this one stays until it's pressed or closed.
# =============================================================================
import sys

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    sys.exit(2)

BUS = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


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
    loop.run()
    if state["choice"]:
        print(state["choice"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
