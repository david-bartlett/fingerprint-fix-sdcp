#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP driver) — Uninstall
# =============================================================================
# Self-contained. Run as root: sudo bash uninstall.sh
#   DELETE_PRINTS=1  delete enrolled fingerprints without asking
#   DELETE_PRINTS=0  keep them without asking
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run as root: sudo bash uninstall.sh"
    exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${BLUE}══ $* ${NC}"; }

FPRINT_LIB_DIR="/usr/local/lib/libfprint-egismoc-sdcp"
FPRINT_DROPIN_DIR="/etc/systemd/system/fprintd.service.d"
FPRINT_DROPIN="${FPRINT_DROPIN_DIR}/samsung-galaxybook-egismoc-sdcp.conf"
FPRINT_MARKER="/etc/samsung-galaxybook-egismoc-sdcp.installed"
FPRINT_STATE_DIR="/var/lib/samsung-galaxybook"
FPRINT_SYSLIB_HASH="${FPRINT_STATE_DIR}/libfprint-system.sha256"
FPRINT_MONITOR_SVC="samsung-galaxybook-fprint-sdcp-monitor.service"
FPRINT_USER_CHECK_SVC="samsung-galaxybook-fprint-sdcp-user-check.service"
FPRINT_USER_CHECK_TIMER="samsung-galaxybook-fprint-sdcp-user-check.timer"
FPRINT_CHECK_SCRIPT="/usr/local/bin/samsung-galaxybook-fprint-sdcp-monitor.sh"
FPRINT_USER_CHECK_SCRIPT="/usr/local/bin/samsung-galaxybook-fprint-sdcp-user-check.sh"
FPRINT_CLEANUP="/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh"
FPRINT_POLKIT_RULE="/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"

echo
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Uninstalling: Fingerprint Fix (egismoc SDCP driver)    ║"
echo "╚════════════════════════════════════════════════════════════╝"

# ── Step 1: Optionally delete enrolled fingerprints ───────────────────────────
# Done FIRST, while fprintd still uses the SDCP driver, so fprintd-delete
# removes both the record in /var/lib/fprint and the template on the sensor.
# (Deleting /var/lib/fprint by hand would leave orphaned templates behind.)
step "Fingerprint Step 1: Enrolled fingerprints"
ENROLLED_USERS=()
if [[ -d /var/lib/fprint ]]; then
    for _d in /var/lib/fprint/*/; do
        [[ -d "$_d" ]] && ENROLLED_USERS+=("$(basename "$_d")")
    done
fi

if [[ ${#ENROLLED_USERS[@]} -eq 0 ]]; then
    info "No enrolled fingerprints"
else
    info "Fingerprints enrolled for: ${ENROLLED_USERS[*]}"
    info "After uninstalling, the distro libfprint cannot use SDCP enrolments."
    info "Keep them only if you will reinstall this fix (or the old fingerprint-fix)."
    _delete="${DELETE_PRINTS:-}"
    if [[ -z "$_delete" ]]; then
        if [[ -t 0 ]]; then
            if ! read -r -t 30 -p "Delete enrolled fingerprints now (also frees them on the sensor)? [y/N] (No in 30s) " _ans; then
                echo; info "No answer — keeping enrolled fingerprints"; _ans=n
            fi
            [[ "${_ans,,}" == y* ]] && _delete=1 || _delete=0
        else
            _delete=0
        fi
    fi
    if [[ "$_delete" == "1" ]]; then
        for _u in "${ENROLLED_USERS[@]}"; do
            fprintd-delete "$_u" >/dev/null 2>&1 \
                && info "Deleted fingerprints for $_u" \
                || warn "fprintd-delete failed for $_u — run it manually before reinstalling"
        done
    else
        info "Keeping enrolled fingerprints"
    fi
fi

# ── Step 2: Remove the fprintd drop-in and the library ────────────────────────
step "Fingerprint Step 2: Restoring the distro libfprint for fprintd"
rm -f "$FPRINT_DROPIN" "${FPRINT_DROPIN}.testing"
rmdir "$FPRINT_DROPIN_DIR" 2>/dev/null || true
rm -rf "$FPRINT_LIB_DIR"
systemctl daemon-reload
systemctl restart fprintd 2>/dev/null || true
info "✓ fprintd now uses the distro libfprint (it was never replaced)"

# ── Step 3: Remove the monitor ────────────────────────────────────────────────
step "Fingerprint Step 3: Removing the fingerprint monitor"
rm -f "$FPRINT_POLKIT_RULE" "/etc/systemd/system/${FPRINT_MONITOR_SVC}"
systemctl daemon-reload 2>/dev/null || true
for USER_HOME in /home/*/; do
    USER_NAME=$(basename "$USER_HOME")
    USER_SVC="${USER_HOME}.config/systemd/user/${FPRINT_USER_CHECK_SVC}"
    USER_TIMER="${USER_HOME}.config/systemd/user/${FPRINT_USER_CHECK_TIMER}"
    [[ -f "$USER_SVC" || -f "$USER_TIMER" ]] || continue
    USER_ID=$(id -u "$USER_NAME" 2>/dev/null || true)
    if [[ -n "$USER_ID" ]]; then
        sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
            systemctl --user disable --now "${FPRINT_USER_CHECK_TIMER}" 2>/dev/null || true
    fi
    rm -f "$USER_TIMER" "$USER_SVC" \
        "${USER_HOME}.config/systemd/user/graphical-session.target.wants/${FPRINT_USER_CHECK_TIMER}"
    [[ -n "$USER_ID" ]] && sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
        systemctl --user daemon-reload 2>/dev/null || true
    info "Removed user timer and service for $USER_NAME"
done
rm -f "$FPRINT_CHECK_SCRIPT" "$FPRINT_USER_CHECK_SCRIPT" "$FPRINT_CLEANUP"
info "✓ Monitor removed"

# Shared graphical session helper — remove only if no other fix uses it.
SESSION_HELPER_USERS="/etc/samsung-galaxybook/session-helper.d"
rm -f "$SESSION_HELPER_USERS/fingerprint-fix-sdcp"
_session_helper_in_use=false
if [[ -d "$SESSION_HELPER_USERS" ]] && [[ -n "$(ls -A "$SESSION_HELPER_USERS" 2>/dev/null)" ]]; then
    _session_helper_in_use=true
fi
for USER_HOME in /home/*/; do
    [[ -f "${USER_HOME}.config/systemd/user/webcam-switch-watch.service" ]] && _session_helper_in_use=true
done
if $_session_helper_in_use; then
    info "Graphical session helper kept — still used by another fix"
else
    rm -f /etc/systemd/user/samsung-galaxybook-session.target \
          /usr/local/bin/samsung-galaxybook-session-start.sh \
          /etc/xdg/autostart/samsung-galaxybook-session.desktop
    rmdir "$SESSION_HELPER_USERS" /etc/samsung-galaxybook 2>/dev/null || true
    info "Removed graphical session helper"
fi

# ── Step 4: Remove state files ────────────────────────────────────────────────
step "Fingerprint Step 4: Removing state files"
rm -f "$FPRINT_MARKER" "$FPRINT_SYSLIB_HASH" /run/samsung-galaxybook/fprint-sdcp-status
rmdir /run/samsung-galaxybook 2>/dev/null || true
rmdir "$FPRINT_STATE_DIR" 2>/dev/null || true
# PAM fingerprint authentication is left enabled on purpose.

info "✓ Fingerprint fix uninstalled"
