#!/bin/bash
# =============================================================================
# Galaxy Book Fingerprint Manager — install an update, in a terminal window
# =============================================================================
#   update-in-terminal.sh TITLE FOLDER COMMAND
#
# Started by the Manager's Update in the user's terminal: shows what is being
# installed and runs COMMAND (sudo asks for the password, dnf / apt / pacman
# ask to confirm). Afterwards FOLDER, the download in /tmp, is removed if it
# worked; the window closes by itself 10 seconds later. If it didn't work, the
# window and the files stay until the user closes it.
# =============================================================================
title="${1:?Usage: $0 TITLE FOLDER COMMAND}"; folder="${2:?}"; cmd="${3:?}"
bold=$'\e[1m'; green=$'\e[32m'; red=$'\e[31m'; off=$'\e[0m'
printf '\e]0;%s\a' "$title"           # the window's title

echo "${bold}${title}${off}"
echo
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
    echo
    read -r -t 10 -p "This window closes in 10 seconds (or press Enter)." _ || true
else
    echo "${red}${bold}The update didn't finish${off} (exit code $rc). Nothing was changed unless it says so above."
    echo "The downloaded files are in: $folder"
    echo
    read -r -p "Press Enter to close this window." _ || true
fi
