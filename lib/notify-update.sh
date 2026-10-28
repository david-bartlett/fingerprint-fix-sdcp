#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — "a new release is available" notification
# =============================================================================
#   notify-update.sh TITLE MESSAGE URL   (as the user, in their desktop)
#
# Buttons: "Open GitHub" (URL: the release's page) and, when the Fingerprint
# Manager is installed, "Open Fingerprint Manager". Critical urgency, so it
# stays on screen until it's clicked or closed (Ubuntu's otherwise shrink away
# after a moment). Waits for that, so update_check.py starts it on its own
# with systemd-run.
# Desktops without notification buttons show it without them, with the URL.
# Shipped in both packages (the driver's copy is used when only it is installed).
# =============================================================================
title="${1:?Usage: $0 TITLE MESSAGE URL}"; msg="${2:-}"; url="${3:-}"
args=(-u critical -t 0 -a "Samsung Galaxy Book Fixes" -i galaxybook-fingerprint-manager)

manager=""
for m in /usr/bin/galaxybook-fingerprint-manager /usr/local/bin/galaxybook-fingerprint-manager; do
    [[ -x "$m" ]] && { manager="$m"; break; }
done

if notify-send --help 2>&1 | grep -q -- '--action'; then
    actions=()
    [[ -n "$manager" ]] && actions+=(--action=manager="Open Fingerprint Manager")
    [[ -n "$url" ]] && actions+=(--action=github="Open GitHub")
    choice=$(notify-send "${args[@]}" "${actions[@]}" "$title" "$msg" 2>/dev/null)
    case "$choice" in
        manager) exec "$manager" ;;
        github)  exec xdg-open "$url" ;;
    esac
else
    notify-send "${args[@]}" "$title" "$msg${url:+
$url}"
fi
exit 0
