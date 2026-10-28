#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — fingerprint login at the first install on a computer
# =============================================================================
# Run as root by the install scripts of BOTH packages (the driver and the
# Fingerprint Manager), each with its own copy next to fingerprint-pam.sh, so
# whichever is installed first — or alone — turns fingerprint login on (lock
# screen, sudo, admin prompts) the way the distro expects. Only once per
# computer: after that, upgrades, reinstalls and the other package leave it
# as the user set it in the Manager. Never turned off by removing anything.
#
#   FPRINT_PAM=0   don't turn it on
#
# "Once per computer" is recorded in /var/lib/samsung-galaxybook/
# fingerprint-login-set-up. Computers set up before this (2.1 and earlier)
# have the Manager's libfprint hash instead, and are left as they are; so is
# a computer whose install.sh copy a package has just replaced
# (keep-pam-setting, left by the package's pre-install script).
# =============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE=/var/lib/samsung-galaxybook
DONE="$STATE/fingerprint-login-set-up"
KEEP="$STATE/keep-pam-setting"

if [[ ! -e "$DONE" ]]; then
    if [[ ! -f "$STATE/libfprint-system.sha256" && ! -e "$KEEP" && "${FPRINT_PAM:-1}" != 0 ]]; then
        if bash "$HERE/fingerprint-pam.sh" enable >/dev/null 2>&1; then
            echo "Fingerprint login is on (lock screen, sudo, admin prompts). Turn it off in the"
            echo "Galaxy Book Fingerprint Manager, or: sudo bash $HERE/fingerprint-pam.sh disable"
        else
            echo "Fingerprint login wasn't turned on. Turn it on in the Galaxy Book Fingerprint"
            echo "Manager, or: sudo bash $HERE/fingerprint-pam.sh enable"
        fi
    fi
    mkdir -p "$STATE" && touch "$DONE"
fi
rm -f "$KEEP"
exit 0
