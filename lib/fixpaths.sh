# shellcheck shell=bash
# shellcheck disable=SC2034   # the paths are used by the scripts that source this
# =============================================================================
# fingerprint-fix-sdcp — where the fix's files live (sourced, not run)
# =============================================================================
# The fix is installed one of two ways, each with its own paths:
#   local    by install.sh, under /usr/local and /etc
#   package  by an rpm / deb / pacman package, under /usr
#
#   . lib/fixpaths.sh
#   fix_layout local|package   set the FPRINT_* / MGR_* / SESSION_* paths below
#   fix_detect                 the layout that is installed here (package first),
#                              or local if neither is — sets FIX_LAYOUT too
#
# The Manager's helper (lib/fingerprint-manager-helper.py) keeps its own copy
# of the marker, library and drop-in paths: change them there as well.
# =============================================================================

FIX_PACKAGE_MARKER="/usr/lib/fingerprint-fix-sdcp/installed"
FIX_LOCAL_MARKER="/etc/samsung-galaxybook-egismoc-sdcp.installed"

fix_layout() {
    FIX_LAYOUT="$1"
    case "$FIX_LAYOUT" in
    local)
        FPRINT_LIB_DIR="/usr/local/lib/libfprint-egismoc-sdcp"
        FPRINT_MARKER="$FIX_LOCAL_MARKER"
        FPRINT_UNIT_DIR="/etc/systemd/system"
        FPRINT_USER_UNIT_DIR=""                 # written into each user's home instead
        FPRINT_SCRIPT_DIR="/usr/local/bin"
        FPRINT_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-monitor.sh"
        FPRINT_USER_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-user-check.sh"
        FPRINT_BOOT_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-boot-check.sh"
        FPRINT_CLEANUP="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-cleanup.sh"
        FPRINT_POLKIT_RULE="/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"
        MGR_BIN="/usr/local/bin/galaxybook-fingerprint-manager"
        MGR_ICON="/usr/local/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg"
        # Shared with other Galaxy Book fixes (same paths as theirs).
        SESSION_HELPER_TARGET="/etc/systemd/user/samsung-galaxybook-session.target"
        SESSION_HELPER_SCRIPT="/usr/local/bin/samsung-galaxybook-session-start.sh"
        SESSION_HELPER_AUTOSTART="/etc/xdg/autostart/samsung-galaxybook-session.desktop"
        ;;
    package)
        FPRINT_LIB_DIR="/usr/lib/fingerprint-fix-sdcp"
        FPRINT_MARKER="$FIX_PACKAGE_MARKER"
        FPRINT_UNIT_DIR="/usr/lib/systemd/system"
        FPRINT_USER_UNIT_DIR="/usr/lib/systemd/user"
        FPRINT_SCRIPT_DIR="$FPRINT_LIB_DIR"
        FPRINT_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/monitor.sh"
        FPRINT_USER_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/user-check.sh"
        FPRINT_BOOT_CHECK_SCRIPT="${FPRINT_SCRIPT_DIR}/boot-check.sh"
        FPRINT_CLEANUP=""                       # the package manager removes a package
        FPRINT_POLKIT_RULE="/usr/share/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"
        MGR_BIN="/usr/bin/galaxybook-fingerprint-manager"
        MGR_ICON="/usr/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg"
        # Package-owned copies: names that can't clash with the shared helper's
        # files (the target itself is the same unit, so either copy works).
        SESSION_HELPER_TARGET="/usr/lib/systemd/user/samsung-galaxybook-session.target"
        SESSION_HELPER_SCRIPT="${FPRINT_LIB_DIR}/session-start.sh"
        SESSION_HELPER_AUTOSTART="/etc/xdg/autostart/fingerprint-fix-sdcp-session.desktop"
        ;;
    *)
        echo "fix_layout: unknown layout '$FIX_LAYOUT' (local or package)" >&2
        return 1 ;;
    esac

    FPRINT_LIB="${FPRINT_LIB_DIR}/libfprint-2.so.2"
    FPRINT_SENSOR_CHECK="${FPRINT_LIB_DIR}/sensor-check"
    FPRINT_DROPIN_DIR="${FPRINT_UNIT_DIR}/fprintd.service.d"
    FPRINT_DROPIN="${FPRINT_DROPIN_DIR}/samsung-galaxybook-egismoc-sdcp.conf"

    # The same in both layouts
    FPRINT_STATE_DIR="/var/lib/samsung-galaxybook"
    FPRINT_SYSLIB_HASH="${FPRINT_STATE_DIR}/libfprint-system.sha256"
    FPRINT_REMOVED_DIR="${FPRINT_STATE_DIR}/removed-fingerprints"
    FPRINT_BOOT_STATUS="/run/samsung-galaxybook/fprint-sdcp-boot-status"
    FPRINT_MONITOR_SVC="samsung-galaxybook-fprint-sdcp-monitor.service"
    FPRINT_USER_CHECK_SVC="samsung-galaxybook-fprint-sdcp-user-check.service"
    FPRINT_USER_CHECK_TIMER="samsung-galaxybook-fprint-sdcp-user-check.timer"
    FPRINT_BOOT_CHECK_SVC="samsung-galaxybook-fprint-sdcp-boot-check.service"
    HARDWARE_USB_ID="1c7a:05a5|1c7a:05a1"

    # Galaxy Book Fingerprint Manager — its files live in MGR_DIR
    MGR_ID="galaxybook-fingerprint-manager"
    MGR_DIR="${FPRINT_LIB_DIR}/manager"
    # The menu entry's file name must equal the app's ID (its Wayland app ID), or
    # the taskbar can't match the window to it and shows a generic icon.
    MGR_APP_ID="io.github.david_bartlett.GalaxyBookFingerprintManager"
    # In /usr/share/applications even for install.sh: Cinnamon's menu doesn't
    # notice a new entry in /usr/local/share/applications until you log in again.
    MGR_DESKTOP="/usr/share/applications/${MGR_APP_ID}.desktop"
    MGR_POLICY="/usr/share/polkit-1/actions/io.github.david-bartlett.${MGR_ID}.policy"
}

fix_detect() {
    if [[ -f "$FIX_PACKAGE_MARKER" ]]; then fix_layout package
    else fix_layout local
    fi
}

# True when every file fprintd needs for the fix is in place.
fix_installed() {
    [[ -f "$FPRINT_MARKER" && -f "$FPRINT_LIB" && -f "$FPRINT_DROPIN" ]]
}
