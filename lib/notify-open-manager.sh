#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — a notification with an "Open Fingerprint Manager" button
# =============================================================================
#   notify-open-manager.sh TITLE MESSAGE [ICON]  (as the user, in their desktop)
#
# Waits for the notification to be clicked or closed (at most an hour), so the
# login check starts it on its own with systemd-run instead of waiting for it.
# On GNOME it's shown by notify-dbus.py (notify-send drops the button there,
# see notify-update.sh), and clicking the notification itself opens the
# Manager too. Desktops without notification buttons show it without one.
# =============================================================================
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
title="${1:?Usage: $0 TITLE MESSAGE [ICON]}"; msg="${2:-}"; icon="${3:-galaxybook-fingerprint-manager}"
args=(-t 0 -a "Samsung Galaxy Book Fixes" -i "$icon")

desk="${XDG_CURRENT_DESKTOP,,}"
choice=""
if [[ "$desk" == *gnome* && "$desk" != *budgie* && -f "$HERE/notify-dbus.py" ]] \
        && command -v python3 >/dev/null 2>&1 && python3 -c 'import gi' 2>/dev/null; then
    # Normal urgency, as before (GNOME moves it into its list after a moment;
    # it's still there, and the button and the click still work from there)
    choice=$(timeout 3600 python3 -I "$HERE/notify-dbus.py" 1 "Samsung Galaxy Book Fixes" "$icon" \
                 "$title" "$msg"$'\n\n'"Click this notification to open the Fingerprint Manager." \
                 open "Open Fingerprint Manager" default "Open Fingerprint Manager")
    rc=$?
    [[ "$choice" == default ]] && choice=open
    (( rc == 2 )) && notify-send "${args[@]}" "$title" "$msg"
elif notify-send --help 2>&1 | grep -q -- '--action'; then
    choice=$(timeout 3600 notify-send "${args[@]}" --action=open="Open Fingerprint Manager" \
                 "$title" "$msg" 2>/dev/null)
else
    notify-send "${args[@]}" "$title" "$msg"
fi
[[ "$choice" == open ]] && exec "$HERE/../fingerprint-manager.sh"
exit 0
