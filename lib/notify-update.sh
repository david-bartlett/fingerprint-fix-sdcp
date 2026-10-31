#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — "a new release is available" notification
# =============================================================================
#   notify-update.sh TITLE MESSAGE URL   (as the user, in their desktop)
#
# Buttons: "Open GitHub" (URL: the release's page; then the notification is
# shown again, so the other button is still there) and, when the Fingerprint
# Manager is installed, "Open Fingerprint Manager". Critical urgency, so it
# stays on screen until it's clicked or closed (Ubuntu's otherwise shrink away
# after a moment). Waits for that, so update_check.py starts it on its own
# with systemd-run.
# On GNOME it's shown by notify-dbus.py, straight over D-Bus: there
# notify-send drops the buttons ("Actions are not supported"), although GNOME
# shows them. Clicking the notification itself there does what the first
# button does (its "default" action; only on GNOME, as other desktops can
# draw it as a button of its own).
# Desktops without notification buttons show it without them, with the URL.
# Shipped in both packages (the driver's copy is used when only it is installed).
# =============================================================================
title="${1:?Usage: $0 TITLE MESSAGE URL}"; msg="${2:-}"; url="${3:-}"
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APPNAME="Samsung Galaxy Book Fixes"; ICON=galaxybook-fingerprint-manager
args=(-u critical -t 0 -a "$APPNAME" -i "$ICON")

manager=""
for m in /usr/bin/galaxybook-fingerprint-manager /usr/local/bin/galaxybook-fingerprint-manager; do
    [[ -x "$m" ]] && { manager="$m"; break; }
done

# The buttons, as KEY=LABEL
acts=()
[[ -n "$manager" ]] && acts+=("manager=Open Fingerprint Manager")
[[ -n "$url" ]] && acts+=("github=Open GitHub")

# GNOME (Ubuntu's is ubuntu:GNOME; not Budgie, budgie:GNOME): notify-dbus.py,
# with a click on the notification doing what the first button does
desk="${XDG_CURRENT_DESKTOP,,}"
dbus=0
if [[ "$desk" == *gnome* && "$desk" != *budgie* && -f "$HERE/notify-dbus.py" ]] \
        && command -v python3 >/dev/null 2>&1 && python3 -c 'import gi' 2>/dev/null; then
    dbus=1
fi

plain() { notify-send "${args[@]}" "$title" "$msg${url:+
$url}"; }

way=""
if (( dbus )) && (( ${#acts[@]} )); then
    way=dbus
    pairs=()
    for a in "${acts[@]}"; do pairs+=("${a%%=*}" "${a#*=}"); done
    pairs+=(default "${acts[0]#*=}")
    if [[ "${acts[0]%%=*}" == manager ]]; then
        click="Click this notification to open the Fingerprint Manager."
    else
        click="Click this notification to see the release on GitHub."
    fi
elif notify-send --help 2>&1 | grep -q -- '--action'; then
    way=notify-send
    opts=()
    for a in "${acts[@]}"; do opts+=("--action=$a"); done
else
    plain
    exit 0
fi

# "Open GitHub" shouldn't take "Open Fingerprint Manager" away: desktops close
# a notification when one of its buttons is pressed, so after opening the
# page show it again - a new one, a moment later so it pops up after the
# browser window (as galaxybook-fan does). "Open Fingerprint Manager" or
# closing it ends this.
for (( n = 0; n < 20; n++ )); do
    if [[ $way == dbus ]]; then
        choice=$(python3 -I "$HERE/notify-dbus.py" 2 "$APPNAME" "$ICON" "$title" "$msg"$'\n\n'"$click" "${pairs[@]}")
        rc=$?
        if (( rc == 2 )); then plain; break; fi     # couldn't show it that way: plainly, with the URL
        [[ "$choice" == default ]] && choice="${acts[0]%%=*}"
    else
        choice=$(notify-send "${args[@]}" "${opts[@]}" "$title" "$msg" 2>/dev/null)
    fi
    case "${choice:-}" in
        manager) exec "$manager" ;;
        github)
            xdg-open "$url" >/dev/null 2>&1 &         # (not the browser's own messages)
            sleep 2 ;;
        *) break ;;                                   # closed
    esac
done
exit 0
