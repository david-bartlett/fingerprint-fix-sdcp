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

# Two parts, each its own package from 2.0.0 (install.sh installs both):
#   the driver   fingerprint-fix-sdcp            libfprint build, fprintd drop-in
#   the Manager  galaxybook-fingerprint-manager  window, helper, tools, monitor,
#                                                boot and login checks
# Either can be installed without the other: the driver alone (enrol in the
# desktop's settings), or the Manager alone (with the distro's libfprint once
# it has SDCP). The driver package recommends the Manager.
FIX_PACKAGE_MARKER="/usr/lib/fingerprint-fix-sdcp/installed"
FIX_LOCAL_MARKER="/etc/samsung-galaxybook-egismoc-sdcp.installed"
MGR_PACKAGE_MARKER="/usr/lib/galaxybook-fingerprint-manager/installed"
MGR_LOCAL_MARKER="/etc/galaxybook-fingerprint-manager.installed"

fix_layout() {
    FIX_LAYOUT="$1"
    case "$FIX_LAYOUT" in
    local)
        # the driver
        FPRINT_LIB_DIR="/usr/local/lib/libfprint-egismoc-sdcp"
        FPRINT_MARKER="$FIX_LOCAL_MARKER"
        FPRINT_SCRIPT_DIR="/usr/local/bin"
        FPRINT_CLEANUP="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-cleanup.sh"
        FPRINT_ENV_SCRIPT="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-fprintd-env.sh"
        FPRINT_OTHER_FIX="${FPRINT_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-other-fix.sh"
        # the Manager
        MGR_ROOT="/usr/local/lib/galaxybook-fingerprint-manager"
        MGR_MARKER="$MGR_LOCAL_MARKER"
        MGR_SCRIPT_DIR="/usr/local/bin"
        MGR_CLEANUP="${MGR_SCRIPT_DIR}/galaxybook-fingerprint-manager-cleanup.sh"
        FPRINT_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-monitor.sh"
        FPRINT_USER_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-user-check.sh"
        FPRINT_BOOT_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/samsung-galaxybook-fprint-sdcp-boot-check.sh"
        FPRINT_UNIT_DIR="/etc/systemd/system"
        FPRINT_USER_UNIT_DIR=""                 # written into each user's home instead
        FPRINT_POLKIT_RULE="/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"
        MGR_BIN="/usr/local/bin/galaxybook-fingerprint-manager"
        # In /usr/share like the menu entry (below): Cinnamon's menu doesn't pick
        # up an icon newly added under /usr/local/share/icons until it restarts.
        MGR_ICON="/usr/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg"
        # Shared with other Galaxy Book fixes (same paths as theirs).
        SESSION_HELPER_TARGET="/etc/systemd/user/samsung-galaxybook-session.target"
        SESSION_HELPER_SCRIPT="/usr/local/bin/samsung-galaxybook-session-start.sh"
        SESSION_HELPER_AUTOSTART="/etc/xdg/autostart/samsung-galaxybook-session.desktop"
        ;;
    package)
        # the driver
        FPRINT_LIB_DIR="/usr/lib/fingerprint-fix-sdcp"
        FPRINT_MARKER="$FIX_PACKAGE_MARKER"
        # Fedora keeps scripts in /usr/libexec (SELinux labels them as
        # programs there); Arch and Debian in the package's library folder.
        FPRINT_SCRIPT_DIR="${FIX_PACKAGE_SCRIPT_DIR:-$FPRINT_LIB_DIR}"
        FPRINT_CLEANUP=""                       # the package manager removes a package
        FPRINT_ENV_SCRIPT="${FPRINT_SCRIPT_DIR}/fprintd-env.sh"
        FPRINT_OTHER_FIX="${FPRINT_SCRIPT_DIR}/other-fix.sh"
        # the Manager
        MGR_ROOT="/usr/lib/galaxybook-fingerprint-manager"
        MGR_MARKER="$MGR_PACKAGE_MARKER"
        MGR_SCRIPT_DIR="${MGR_PACKAGE_SCRIPT_DIR:-$MGR_ROOT}"
        MGR_CLEANUP=""
        FPRINT_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/monitor.sh"
        FPRINT_USER_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/user-check.sh"
        FPRINT_BOOT_CHECK_SCRIPT="${MGR_SCRIPT_DIR}/boot-check.sh"
        FPRINT_UNIT_DIR="/usr/lib/systemd/system"
        FPRINT_USER_UNIT_DIR="/usr/lib/systemd/user"
        FPRINT_POLKIT_RULE="/usr/share/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"
        MGR_BIN="/usr/bin/galaxybook-fingerprint-manager"
        MGR_ICON="/usr/share/icons/hicolor/scalable/apps/galaxybook-fingerprint-manager.svg"
        # Package-owned copies: names that can't clash with the shared helper's
        # files (the target itself is the same unit, so either copy works).
        SESSION_HELPER_TARGET="/usr/lib/systemd/user/samsung-galaxybook-session.target"
        SESSION_HELPER_SCRIPT="${MGR_SCRIPT_DIR}/session-start.sh"
        SESSION_HELPER_AUTOSTART="/etc/xdg/autostart/fingerprint-fix-sdcp-session.desktop"
        ;;
    *)
        echo "fix_layout: unknown layout '$FIX_LAYOUT' (local or package)" >&2
        return 1 ;;
    esac

    FPRINT_LIB="${FPRINT_LIB_DIR}/libfprint-2.so.2"
    FPRINT_DROPIN_DIR="${FPRINT_UNIT_DIR}/fprintd.service.d"
    FPRINT_DROPIN="${FPRINT_DROPIN_DIR}/samsung-galaxybook-egismoc-sdcp.conf"

    # The same in both layouts
    FPRINT_STATE_DIR="/var/lib/samsung-galaxybook"
    FPRINT_SYSLIB_HASH="${FPRINT_STATE_DIR}/libfprint-system.sha256"
    FPRINT_REMOVED_DIR="${FPRINT_STATE_DIR}/removed-fingerprints"
    FPRINT_BOOT_STATUS="/run/samsung-galaxybook/fprint-sdcp-boot-status"
    # Written by FPRINT_ENV_SCRIPT each time fprintd starts, read by the drop-in:
    # LD_LIBRARY_PATH only when the Galaxy Book's reader is present.
    FPRINT_ENV_FILE="/run/samsung-galaxybook/fprintd-sdcp.env"
    FPRINT_MONITOR_SVC="samsung-galaxybook-fprint-sdcp-monitor.service"
    FPRINT_USER_CHECK_SVC="samsung-galaxybook-fprint-sdcp-user-check.service"
    FPRINT_USER_CHECK_TIMER="samsung-galaxybook-fprint-sdcp-user-check.timer"
    # The hourly check for new releases (user timers): one in each package,
    # the driver's skipped while the Manager is installed (its own runs).
    FIX_UPDATE_DIR="${FPRINT_LIB_DIR}/update"
    FIX_UPDATE_SVC="fingerprint-fix-sdcp-update-check.service"
    FIX_UPDATE_TIMER="fingerprint-fix-sdcp-update-check.timer"
    MGR_UPDATE_SVC="galaxybook-fingerprint-manager-update-check.service"
    MGR_UPDATE_TIMER="galaxybook-fingerprint-manager-update-check.timer"
    FPRINT_BOOT_CHECK_SVC="samsung-galaxybook-fprint-sdcp-boot-check.service"
    HARDWARE_USB_ID="1c7a:05a5|1c7a:05a1"

    # Galaxy Book Fingerprint Manager — the app itself lives in MGR_DIR
    MGR_ID="galaxybook-fingerprint-manager"
    MGR_DIR="$MGR_ROOT"
    # The boot-time sensor check (Python, with whichever libfprint fprintd uses)
    FPRINT_SENSOR_CHECK="${MGR_DIR}/lib/sensor-check.py"
    # The menu entry's file name must equal the app's ID (its Wayland app ID), or
    # the taskbar can't match the window to it and shows a generic icon.
    MGR_APP_ID="io.github.david_bartlett.GalaxyBookFingerprintManager"
    # In /usr/share/applications even for install.sh: Cinnamon's menu doesn't
    # notice a new entry in /usr/local/share/applications until you log in again.
    MGR_DESKTOP="/usr/share/applications/${MGR_APP_ID}.desktop"
    MGR_POLICY="/usr/share/polkit-1/actions/io.github.david-bartlett.${MGR_ID}.policy"
}

fix_detect() {
    if [[ -f "$FIX_PACKAGE_MARKER" || -f "$MGR_PACKAGE_MARKER" ]]; then fix_layout package
    else fix_layout local
    fi
}

# True when every file fprintd needs for the driver is in place.
fix_installed() {
    [[ -f "$FPRINT_MARKER" && -f "$FPRINT_LIB" && -f "$FPRINT_DROPIN" ]]
}

# True when the Manager (and its monitor and checks) is installed.
mgr_installed() {
    [[ -f "$MGR_MARKER" ]]
}

# True when fprintd can use SDCP fingerprints: this fix's driver is installed,
# or — once it has been removed — the distro's own libfprint has an SDCP driver
# for the reader (from the distro itself, not another fix). Run as root.
sdcp_available() {
    fix_installed && return 0
    [[ -f "$MGR_DIR/lib/distro-driver-check.py" ]] || return 1
    [[ "$(env -u LD_LIBRARY_PATH python3 "$MGR_DIR/lib/distro-driver-check.py" 2>/dev/null | head -n1)" == sdcp ]]
}
