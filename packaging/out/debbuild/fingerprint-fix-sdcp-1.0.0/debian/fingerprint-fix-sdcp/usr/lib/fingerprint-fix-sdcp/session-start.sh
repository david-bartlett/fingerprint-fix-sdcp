#!/bin/bash
# Samsung Galaxy Book — start graphical-session.target on desktops that don't.
systemctl --user is-active --quiet graphical-session.target && exit 0
if command -v dbus-update-activation-environment >/dev/null 2>&1; then
    dbus-update-activation-environment --systemd --all
else
    systemctl --user import-environment DISPLAY XAUTHORITY WAYLAND_DISPLAY \
        XDG_CURRENT_DESKTOP XDG_SESSION_TYPE 2>/dev/null
fi
systemctl --user start samsung-galaxybook-session.target
