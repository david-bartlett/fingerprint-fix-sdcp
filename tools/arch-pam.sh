#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — PAM for Arch-based distros
# =============================================================================
# Fedora (authselect) and Ubuntu/Debian/Mint (pam-auth-update) switch on
# fingerprint authentication themselves. Arch-based distros (CachyOS, Manjaro,
# EndeavourOS, ...) don't, so this adds fingerprint to sudo and to polkit
# (pkexec and graphical admin prompts):
#
#   sudo bash arch-pam.sh enable     # add fingerprint to sudo and polkit-1
#   sudo bash arch-pam.sh disable    # remove exactly what 'enable' added
#   sudo bash arch-pam.sh status
#
# Each file gets one 'auth sufficient pam_fprintd.so' line above its first
# auth line, marked with a comment. Until a finger is enrolled, pam_fprintd
# reports "not available" and the password is asked for as usual.
#
# Not touched: the KDE lock screen (its kde-fingerprint service already uses
# the fingerprint) and the login screen (fingerprint there makes it wait for
# the sensor after a password is typed).
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run as root: sudo bash $0 enable|disable|status"
    exit 1
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Arch itself has ID=arch and no ID_LIKE; derivatives (CachyOS, EndeavourOS,
# Manjaro, Garuda, ...) have ID_LIKE=arch, sometimes quoted or with other values.
[[ -f /etc/os-release ]] || error "Cannot detect distro — /etc/os-release not found"
# shellcheck disable=SC1091
. /etc/os-release
case " ${ID,,} ${ID_LIKE,,} " in
    *" arch "*) ;;
    *) error "arch-pam.sh is only for Arch-based distros (this is ${PRETTY_NAME:-unknown})." ;;
esac

MARK="# Added by Samsung Galaxy Book fingerprint-fix-sdcp (arch-pam.sh)"
RULE="auth            sufficient      pam_fprintd.so"
STATE_DIR="/var/lib/samsung-galaxybook"
POLKIT_CREATED="${STATE_DIR}/pam-polkit-1-created"
BAK=".bak-samsung-galaxybook"

# file in /etc/pam.d, optional vendor copy in /usr/lib/pam.d
SERVICES=(sudo polkit-1)

# Print FILE with our two lines inserted above its first auth line.
with_rule() {
    awk -v mark="$MARK" -v rule="$RULE" '
        !done && /^[[:space:]]*-?auth[[:space:]]/ { print mark; print rule; done = 1 }
        { print }
        END { if (!done) exit 3 }' "$1"
}

# Print FILE without our two lines.
without_rule() {
    awk -v mark="$MARK" '
        $0 == mark { skip = 1; next }
        skip && /pam_fprintd\.so/ { skip = 0; next }
        { skip = 0; print }' "$1"
}

enable_one() {
    local svc="$1" f="/etc/pam.d/$1" vendor="/usr/lib/pam.d/$1" tmp
    if [[ ! -f "$f" ]]; then
        if [[ -f "$vendor" ]]; then
            install -m 644 "$vendor" "$f"
            mkdir -p "$STATE_DIR"
            [[ "$svc" == "polkit-1" ]] && touch "$POLKIT_CREATED"
            info "Copied $vendor to $f (files in /etc/pam.d take precedence)"
        else
            warn "$svc: no PAM file found — skipped"
            return 0
        fi
    fi
    if grep -qE '^[[:space:]]*[^#[:space:]].*pam_fprintd' "$f"; then
        info "$svc: fingerprint already enabled — left as it is"
        return 0
    fi
    [[ -f "$f$BAK" ]] || cp -p "$f" "$f$BAK"
    tmp=$(mktemp)
    if ! with_rule "$f" > "$tmp"; then
        rm -f "$tmp"
        warn "$svc: no auth line in $f — skipped"
        return 0
    fi
    # Safety: removing our lines again must give back the original exactly.
    if ! diff -q <(without_rule "$tmp") "$f" >/dev/null; then
        rm -f "$tmp"
        warn "$svc: could not edit $f safely — left unchanged"
        return 0
    fi
    cat "$tmp" > "$f"      # keep the file's owner, mode and SELinux label
    rm -f "$tmp"
    info "✓ $svc: fingerprint enabled (backup: $f$BAK)"
}

disable_one() {
    local svc="$1" f="/etc/pam.d/$1" vendor="/usr/lib/pam.d/$1" tmp
    [[ -f "$f" ]] || return 0
    if grep -qxF "$MARK" "$f"; then
        tmp=$(mktemp)
        without_rule "$f" > "$tmp"
        cat "$tmp" > "$f"
        rm -f "$tmp"
        info "✓ $svc: fingerprint line removed"
    fi
    # Remove the polkit-1 copy we created, unless it has since been changed.
    if [[ "$svc" == "polkit-1" && -f "$POLKIT_CREATED" ]]; then
        if [[ -f "$vendor" ]] && cmp -s "$f" "$vendor"; then
            rm -f "$f"
            info "✓ Removed $f (the distro's $vendor applies again)"
        else
            warn "$f was changed by hand since it was copied — left in place"
        fi
        rm -f "$POLKIT_CREATED"
    fi
    rm -f "$f$BAK"
}

status_one() {
    local f="/etc/pam.d/$1"
    if [[ ! -f "$f" ]]; then echo "  $1: no /etc/pam.d file"
    elif grep -qxF "$MARK" "$f"; then echo "  $1: fingerprint enabled (by this fix)"
    elif grep -qE '^[[:space:]]*[^#[:space:]].*pam_fprintd' "$f"; then echo "  $1: fingerprint enabled (not by this fix)"
    else echo "  $1: fingerprint not enabled"
    fi
}

# Before adding pam_fprintd.so to a PAM file, the module and fprintd must be
# installed: a line naming a module PAM can't load could break sudo itself.
# (disable and status are never blocked, so changes can always be undone.)
check_fprintd_pam() {
    local d found=""
    for d in /usr/lib/security /usr/lib64/security /lib/security /lib64/security \
             /usr/lib/x86_64-linux-gnu/security /lib/x86_64-linux-gnu/security; do
        [[ -f "$d/pam_fprintd.so" ]] && { found="$d/pam_fprintd.so"; break; }
    done
    [[ -n "$found" ]] \
        || error "pam_fprintd.so not found — fprintd is not installed. Install it first:\n  sudo pacman -S fprintd   (or run install.sh, which installs it)"
    command -v fprintd-list >/dev/null 2>&1 && systemctl cat fprintd.service >/dev/null 2>&1 \
        || error "fprintd is not installed. Install it first:\n  sudo pacman -S fprintd   (or run install.sh, which installs it)"
}

case "${1:-}" in
    enable)  check_fprintd_pam
             for s in "${SERVICES[@]}"; do enable_one "$s"; done
             echo
             echo "  Test in a NEW terminal:  sudo -k; sudo true   and   pkexec true"
             echo "  Undo:                    sudo bash $(basename "$0") disable" ;;
    disable) for s in "${SERVICES[@]}"; do disable_one "$s"; done ;;
    status)  for s in "${SERVICES[@]}"; do status_one "$s"; done ;;
    *)       error "Usage: sudo bash $0 enable|disable|status" ;;
esac
