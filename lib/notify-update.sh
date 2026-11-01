#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — "a new release is available" notification
# =============================================================================
#   notify-update.sh TITLE MESSAGE URL [VERSION]   (as the user, in their desktop)
#
# Buttons: "Update now" (when VERSION is given and the Fingerprint Manager was
# installed from a package: update_check.py --update-now opens a terminal
# that downloads, checks and installs both packages, as the Manager's Update
# does) and "What's new" (URL: the release's page; then the notification is
# shown again, so "Update now" is still there). With buttons the text is just
# MESSAGE's first line ("You have X.Y.Z."); without them it's all of it, and
# the URL. Critical urgency, so it stays on screen until it's clicked or
# closed (Ubuntu's otherwise shrink away after a moment). Waits for that, so
# update_check.py starts it on its own with systemd-run.
# On GNOME it's shown by notify-dbus.py, straight over D-Bus: there
# notify-send drops the buttons ("Actions are not supported"), although GNOME
# shows them. Clicking the notification itself there is "What's new" (its
# "default" action; only on GNOME, as other desktops can draw it as a button
# of its own), so a stray click never starts an install.
# Shipped in both packages (the driver's copy is used when only it is
# installed; it has no "Update now": the release's packages go together).
# =============================================================================
title="${1:?Usage: $0 TITLE MESSAGE URL [VERSION]}"; msg="${2:-}"; url="${3:-}"; version="${4:-}"
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APPNAME="Samsung Galaxy Book Fixes"; ICON=galaxybook-fingerprint-manager
args=(-u critical -t 0 -a "$APPNAME" -i "$ICON")

# The buttons, as KEY=LABEL
acts=()
if [[ -n "$version" && -f "$HERE/update_check.py" ]] \
        && python3 -I "$HERE/update_check.py" --can-update-now 2>/dev/null; then
    acts+=("update=Update now")
fi
[[ -n "$url" ]] && acts+=("whatsnew=What's new")

# GNOME (Ubuntu's is ubuntu:GNOME; not Budgie, budgie:GNOME): notify-dbus.py,
# with a click on the notification being "What's new"
desk="${XDG_CURRENT_DESKTOP,,}"
dbus=0
if [[ "$desk" == *gnome* && "$desk" != *budgie* && -f "$HERE/notify-dbus.py" ]] \
        && command -v python3 >/dev/null 2>&1 && python3 -c 'import gi' 2>/dev/null; then
    dbus=1
fi

full="$msg"
plain() { notify-send "${args[@]}" "$title" "$full${url:+
$url}"; }

way=""
if (( dbus )) && (( ${#acts[@]} )); then
    way=dbus
    pairs=()
    for a in "${acts[@]}"; do pairs+=("${a%%=*}" "${a#*=}"); done
    [[ -n "$url" ]] && pairs+=(default "What's new")
elif notify-send --help 2>&1 | grep -q -- '--action'; then
    way=notify-send
    opts=()
    for a in "${acts[@]}"; do opts+=("--action=$a"); done
else
    plain
    exit 0
fi
(( ${#acts[@]} )) || { plain; exit 0; }
# With buttons, only the first line ("You have X.Y.Z."): they do the rest
msg="${msg%%$'\n'*}"
[[ $way == dbus && -n "$url" ]] && msg+=$'\n'"Click this notification to see what's new."

# "What's new" shouldn't take "Update now" away: desktops close a
# notification when one of its buttons is pressed, so after opening the page
# show it again - a new one, a moment later so it pops up after the browser
# window (as galaxybook-fan does). "Update now" or closing it ends this.
for (( n = 0; n < 20; n++ )); do
    if [[ $way == dbus ]]; then
        choice=$(python3 -I "$HERE/notify-dbus.py" 2 "$APPNAME" "$ICON" "$title" "$msg" "${pairs[@]}")
        rc=$?
        if (( rc == 2 )); then plain; break; fi     # couldn't show it that way: plainly, with the URL
        [[ "$choice" == default ]] && choice=whatsnew
    else
        choice=$(notify-send "${args[@]}" "${opts[@]}" "$title" "$msg" 2>/dev/null)
    fi
    case "${choice:-}" in
        update)
            # A terminal downloading and installing it (update_check.py
            # --install); if none starts, the release page instead
            python3 -I "$HERE/update_check.py" --update-now "$version" \
                || xdg-open "$url" >/dev/null 2>&1
            break ;;
        whatsnew)
            xdg-open "$url" >/dev/null 2>&1 &         # (not the browser's own messages)
            sleep 2 ;;
        *) break ;;                                   # closed
    esac
done
exit 0
