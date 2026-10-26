#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP driver) — Uninstall
# =============================================================================
# Self-contained. Run as root: sudo bash uninstall.sh
# Enrolled fingerprints are always kept (fprintd's records and the templates
# on the sensor). To delete fingers, use the Fingerprint Manager first.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Paths of an install.sh install (the packages remove themselves).
# shellcheck source=lib/fixpaths.sh
. "$SCRIPT_DIR/lib/fixpaths.sh" 2>/dev/null \
    || error "lib/fixpaths.sh not found — run uninstall.sh from the complete fingerprint-fix-sdcp folder."
fix_layout local
if [[ -f "$FIX_PACKAGE_MARKER" && ! -f "$FPRINT_MARKER" ]]; then
    error "fingerprint-fix-sdcp is installed as a package — remove it with your package\n  manager instead (enrolled fingerprints are kept):\n  sudo pacman -R / dnf remove / apt remove fingerprint-fix-sdcp"
fi

echo
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Uninstalling: Fingerprint Fix (egismoc SDCP driver)    ║"
echo "╚════════════════════════════════════════════════════════════╝"

# ── Step 1: Enrolled fingerprints are kept ────────────────────────────────────
# Never deleted here: a mistyped answer would also wipe the templates on the
# sensor, which other installs and Windows Hello may share. Deleting is done
# in the Fingerprint Manager (or with fprintd-delete before uninstalling,
# while fprintd still uses this driver — deleting /var/lib/fprint by hand would
# leave orphaned templates on the sensor).
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
    info "Fingerprints enrolled for: ${ENROLLED_USERS[*]} — kept"
    info "Reinstalling this fix (install.sh or a package) uses them again."
    info "To delete fingers, use the Fingerprint Manager before uninstalling."
fi

# ── Step 2: Remove the fprintd drop-in and the library ────────────────────────
# ── Undo the Arch PAM changes, if this fix made them ──────────────────────────
# arch-pam.sh only removes lines it marked itself; hand edits are left alone.
if grep -qsF "fingerprint-fix-sdcp (arch-pam.sh)" /etc/pam.d/sudo /etc/pam.d/polkit-1 \
        || [[ -f /var/lib/samsung-galaxybook/pam-polkit-1-created ]]; then
    step "Fingerprint Step 1b: Removing fingerprint from sudo and polkit"
    if [[ -f "$SCRIPT_DIR/tools/arch-pam.sh" ]]; then
        bash "$SCRIPT_DIR/tools/arch-pam.sh" disable \
            || warn "arch-pam.sh disable failed — check /etc/pam.d/sudo and /etc/pam.d/polkit-1"
    else
        warn "tools/arch-pam.sh not found — remove the marked lines in\n       /etc/pam.d/sudo and /etc/pam.d/polkit-1 by hand"
    fi
fi

step "Fingerprint Step 2: Restoring the distro libfprint for fprintd"
rm -f "$FPRINT_DROPIN" "${FPRINT_DROPIN}.testing"
rmdir "$FPRINT_DROPIN_DIR" 2>/dev/null || true
rm -rf "$FPRINT_LIB_DIR"       # includes the Galaxy Book Fingerprint Manager (manager/)
# Fingerprint Manager's menu entry, command, icon and polkit policy
rm -f "$MGR_BIN" "$MGR_DESKTOP" "$MGR_ICON" "$MGR_POLICY"
# Refresh the icon caches only where there is one (none is fine: GTK then reads
# the folder). /usr/local held the icon before 1.3.2: remove that copy.
LEGACY_ICON=/usr/local/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg
rm -f "$LEGACY_ICON"
for _icons in "$(dirname "$(dirname "$(dirname "$MGR_ICON")")")" /usr/local/share/icons/hicolor; do
    [[ -f "$_icons/icon-theme.cache" ]] && command -v gtk-update-icon-cache >/dev/null 2>&1 \
        && gtk-update-icon-cache -q -t -f "$_icons" 2>/dev/null || true
done
command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database -q /usr/share/applications 2>/dev/null || true
systemctl daemon-reload
systemctl restart fprintd 2>/dev/null || true
info "✓ fprintd now uses the distro libfprint (it was never replaced)"

# ── Step 3: Remove the monitor ────────────────────────────────────────────────
step "Fingerprint Step 3: Removing the fingerprint monitor"
systemctl disable "$FPRINT_BOOT_CHECK_SVC" 2>/dev/null || true
rm -f "$FPRINT_POLKIT_RULE" "${FPRINT_UNIT_DIR}/${FPRINT_MONITOR_SVC}" \
      "${FPRINT_UNIT_DIR}/${FPRINT_BOOT_CHECK_SVC}"
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
        "${USER_HOME}.config/systemd/user/graphical-session.target.wants/${FPRINT_USER_CHECK_TIMER}" \
        "${USER_HOME}.cache/samsung-galaxybook/fprint-sdcp-boot-shown" \
        "${USER_HOME}.cache/samsung-galaxybook/fprint-sdcp-welcome-shown" \
        "${USER_HOME}.cache/samsung-galaxybook/fprint-sdcp-pam-hint-shown"
    [[ -n "$USER_ID" ]] && sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
        systemctl --user daemon-reload 2>/dev/null || true
    info "Removed user timer and service for $USER_NAME"
done
rm -f "$FPRINT_CHECK_SCRIPT" "$FPRINT_USER_CHECK_SCRIPT" "$FPRINT_BOOT_CHECK_SCRIPT" "$FPRINT_CLEANUP"
info "✓ Monitor and boot-time sensor check removed"

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
    rm -f "$SESSION_HELPER_TARGET" "$SESSION_HELPER_SCRIPT" "$SESSION_HELPER_AUTOSTART"
    rmdir "$SESSION_HELPER_USERS" /etc/samsung-galaxybook 2>/dev/null || true
    info "Removed graphical session helper"
fi

# ── Step 4: Remove state files ────────────────────────────────────────────────
step "Fingerprint Step 4: Removing state files"
rm -f "$FPRINT_MARKER" "$FPRINT_SYSLIB_HASH" /run/samsung-galaxybook/fprint-sdcp-status \
      "$FPRINT_BOOT_STATUS"
rm -rf "$FPRINT_REMOVED_DIR" "${FPRINT_STATE_DIR}/replaced-fingerprints"
rmdir /run/samsung-galaxybook 2>/dev/null || true
rmdir "$FPRINT_STATE_DIR" 2>/dev/null || true
# PAM fingerprint authentication is left enabled on purpose.

info "✓ Fingerprint fix uninstalled"
