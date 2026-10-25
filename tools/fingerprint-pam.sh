#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — fingerprint PAM switch
# =============================================================================
# Turns fingerprint login / sudo / admin prompts on or off the way each distro
# expects, and reports whether it is on. Used by install.sh (Step 12) and the
# Fingerprint Manager.
#
#   sudo bash fingerprint-pam.sh enable
#   sudo bash fingerprint-pam.sh disable
#   bash fingerprint-pam.sh status            (no sudo needed)
#   bash fingerprint-pam.sh status --short    → "<state>|<method>|<detail>"
#                                               state: enabled, disabled,
#                                               partial or unavailable
#
#   Fedora                  authselect feature with-fingerprint
#   Ubuntu / Debian / MX    pam-auth-update profile "fprintd"
#   Linux Mint              pam-auth-update profile "fingwit" (Mint's own;
#                           it conflicts with fprintd's, which is removed)
#   Arch-based              arch-pam.sh (sudo and polkit-1, with backups)
# =============================================================================

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

ACTION="${1:-}"
SHORT=false
[[ "${2:-}" == "--short" ]] && SHORT=true

[[ -f /etc/os-release ]] || error "Cannot detect distro — /etc/os-release not found"
. /etc/os-release
_id="${ID,,}"; _like="${ID_LIKE:-}"; _like="${_like,,}"
if [[ "$_id" == "fedora" ]]; then DISTRO="fedora"
elif [[ "$_id" == "ubuntu" || "$_like" == *"ubuntu"* || "$_id" == "debian" || "$_like" == *"debian"* ]]; then DISTRO="debian"
elif [[ "$_id" == "arch" || "$_like" == *"arch"* ]]; then DISTRO="arch"
else error "Unsupported distro: ${PRETTY_NAME:-$_id}"
fi

# ── Fedora: authselect ────────────────────────────────────────────────────────
fedora_status() {
    command -v authselect >/dev/null 2>&1 \
        || { echo "unavailable|authselect|authselect is not installed"; return; }
    local cur
    if ! cur=$(authselect current --raw 2>/dev/null) || [[ -z "$cur" ]]; then
        echo "unavailable|authselect|authselect is not managing PAM on this system"
        return
    fi
    if [[ " $cur " == *" with-fingerprint "* ]]; then
        echo "enabled|authselect|profile ${cur%% *} with-fingerprint"
    else
        echo "disabled|authselect|profile ${cur%% *}"
    fi
}
fedora_set() {
    if [[ "$1" == enable ]]; then
        authselect enable-feature with-fingerprint >/dev/null \
            || error "authselect enable-feature with-fingerprint failed"
    else
        authselect disable-feature with-fingerprint >/dev/null \
            || error "authselect disable-feature with-fingerprint failed"
    fi
}

# ── Ubuntu / Debian / MX / Mint: pam-auth-update ──────────────────────────────
debian_profile() {
    if [[ -f /usr/share/pam-configs/fingwit ]]; then echo fingwit
    elif [[ -f /usr/share/pam-configs/fprintd ]]; then echo fprintd
    fi
}
debian_status() {
    command -v pam-auth-update >/dev/null 2>&1 \
        || { echo "unavailable|pam-auth-update|pam-auth-update is not installed"; return; }
    local prof; prof=$(debian_profile)
    [[ -n "$prof" ]] \
        || { echo "unavailable|pam-auth-update|libpam-fprintd is not installed"; return; }
    if grep -q pam_fprintd /etc/pam.d/common-auth 2>/dev/null; then
        echo "enabled|pam-auth-update|profile $prof"
    else
        echo "disabled|pam-auth-update|profile $prof"
    fi
}
debian_set() {
    local prof; prof=$(debian_profile)
    [[ -n "$prof" ]] || error "libpam-fprintd is not installed (no fprintd PAM profile)."
    if [[ "$1" == enable ]]; then
        # Mint's fingwit and fprintd's profile conflict — only one may be on.
        [[ "$prof" == fingwit ]] && pam-auth-update --remove fprintd --force 2>/dev/null || true
        pam-auth-update --enable "$prof" --force >/dev/null 2>&1 \
            || error "pam-auth-update --enable $prof failed"
    else
        local p
        for p in fingwit fprintd; do
            [[ -f "/usr/share/pam-configs/$p" ]] || continue
            pam-auth-update --remove "$p" --force >/dev/null 2>&1 \
                || error "pam-auth-update --remove $p failed"
        done
    fi
}

# ── Arch-based: sudo and polkit-1 via arch-pam.sh ─────────────────────────────
arch_status() {
    local on=() off=() s f
    for s in sudo polkit-1; do
        f="/etc/pam.d/$s"
        if [[ -f "$f" ]] && grep -q pam_fprintd "$f"; then on+=("$s"); else off+=("$s"); fi
    done
    if [[ ${#off[@]} -eq 0 ]]; then echo "enabled|arch-pam.sh|sudo and polkit-1"
    elif [[ ${#on[@]} -eq 0 ]]; then echo "disabled|arch-pam.sh|sudo and polkit-1"
    else echo "partial|arch-pam.sh|on for ${on[*]}, off for ${off[*]}"
    fi
}
arch_set() {
    [[ -f "$HERE/arch-pam.sh" ]] || error "arch-pam.sh is missing from $HERE"
    bash "$HERE/arch-pam.sh" "$1"
}

status() { "${DISTRO}_status"; }

case "$ACTION" in
    status)
        line=$(status)
        if $SHORT; then
            echo "$line"
        else
            IFS='|' read -r state method detail <<< "$line"
            echo "  Fingerprint for login and sudo: $state ($method — $detail)"
        fi
        ;;
    enable|disable)
        [[ "${EUID:-$(id -u)}" -eq 0 ]] || error "Please run with sudo: sudo bash $0 $ACTION"
        "${DISTRO}_set" "$ACTION"
        IFS='|' read -r state method detail <<< "$(status)"
        case "$ACTION:$state" in
            enable:enabled)   info "✓ Fingerprint authentication enabled ($method — $detail)" ;;
            disable:disabled) info "✓ Fingerprint authentication disabled ($method — $detail)" ;;
            *) warn "Fingerprint authentication is now: $state ($method — $detail)"
               [[ "$DISTRO" == arch && "$ACTION" == disable ]] \
                   && warn "arch-pam.sh only removes lines it added itself — any others were left alone."
               exit 1 ;;
        esac
        ;;
    *)
        echo "Usage: sudo bash $0 enable|disable"
        echo "       bash $0 status [--short]"
        exit 1 ;;
esac
