#!/bin/bash
# =============================================================================
# Galaxy Book Fingerprint Manager — install an update, in a terminal window
# =============================================================================
#   update-in-terminal.sh TITLE FOLDER COMMAND [CLOSED-FILE]
#
# Started by the Manager's Update in the user's terminal: shows what is being
# installed and runs COMMAND (sudo asks for the password, dnf / apt / pacman
# ask to confirm). Afterwards FOLDER, the download in /tmp, is removed if it
# worked; the window closes by itself 10 seconds later. If it didn't work, the
# window and the files stay until the user closes it. CLOSED-FILE is created
# as the window closes (however it's closed), so the Manager waits for that
# before asking to restart into the new version.
# Also started by update_check.py --install (the notification's Update now),
# after it has downloaded the files: TITLE_SHOWN=1, as it showed the title.
# GBF_OWN_TERMINAL=1 ('galaxybook-fingerprint-manager update', typed in the
# user's own terminal): no window title and no waiting before it closes.
# =============================================================================
title="${1:?Usage: $0 TITLE FOLDER COMMAND [CLOSED-FILE]}"; folder="${2:?}"; cmd="${3:?}"; closed="${4:-}"
[[ -n "$closed" ]] && trap 'touch -- "$closed"; exit' EXIT HUP TERM INT
bold=$'\e[1m'; green=$'\e[32m'; red=$'\e[31m'; off=$'\e[0m'
own="${GBF_OWN_TERMINAL:-}"
[[ -z "$own" ]] && printf '\e]0;%s\a' "$title"     # the window's title

if [[ -z "${TITLE_SHOWN:-}" ]]; then
    echo "${bold}${title}${off}"
    echo
fi
echo "Running:  $cmd"
echo
bash -c "$cmd"
rc=$?
echo
if [[ $rc -eq 0 ]]; then
    case "$folder" in
        /tmp/galaxybook-update-*) rm -rf -- "$folder" ;;
    esac
    echo "${green}${bold}Done.${off} If the Fingerprint Manager is open, press Restart in it to use the new version."
    [[ -n "$own" ]] && exit 0
    echo
    read -r -t 10 -p "This window closes in 10 seconds (or press Enter)." _ || true
else
    echo "${red}${bold}The update didn't finish${off} (exit code $rc). Nothing was changed unless it says so above."
    echo "The downloaded files are in: $folder"
    [[ -n "$own" ]] && exit "$rc"
    echo
    read -r -p "Press Enter to close this window." _ || true
fi
