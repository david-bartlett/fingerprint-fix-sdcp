#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — a notification with an "Open Fingerprint Manager" button
# =============================================================================
#   notify-open-manager.sh TITLE MESSAGE [ICON]  (as the user, in their desktop)
#
# Waits for the notification to be clicked or closed (at most an hour), so the
# login check starts it on its own with systemd-run instead of waiting for it.
# Desktops without notification buttons show it without one.
# =============================================================================
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
title="${1:?Usage: $0 TITLE MESSAGE [ICON]}"; msg="${2:-}"
args=(-t 0 -a "Samsung Galaxy Book Fixes" -i "${3:-galaxybook-fingerprint-manager}")

if notify-send --help 2>&1 | grep -q -- '--action'; then
    choice=$(timeout 3600 notify-send "${args[@]}" --action=open="Open Fingerprint Manager" \
                 "$title" "$msg" 2>/dev/null)
    [[ "$choice" == open ]] && exec "$HERE/../fingerprint-manager.sh"
else
    notify-send "${args[@]}" "$title" "$msg"
fi
exit 0
