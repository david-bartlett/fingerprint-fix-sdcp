#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP driver) — Install
# =============================================================================
# Self-contained. Run as root: sudo bash install.sh
#
# Builds ONLY the egismoc driver from Abdallah Alkanani's libfprint-egismoc-sdcp
# branch (libfprint-TOD v1.95.2 + Joshua Grisham's Egis SDCP driver, hardened),
# pinned to a known commit, and points fprintd at it with a systemd drop-in.
# The distro's libfprint is left untouched, so distro updates cannot overwrite
# this fix and removing it is just deleting the drop-in.
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run as root: sudo bash install.sh"
    exit 1
fi

# This fix uses a systemd drop-in for fprintd plus systemd services and timers.
if [[ ! -d /run/systemd/system ]]; then
    echo "ERROR: systemd is not running (e.g. MX Linux booted with SysVinit)."
    echo "       The fingerprint fix needs systemd. Reboot, choose the systemd"
    echo "       boot option and run this installer again."
    exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${BLUE}══ $* ${NC}"; }

# ── Source pin ────────────────────────────────────────────────────────────────
# Change these two lines (after testing) to move to a newer commit.
SDCP_REPO_URL="https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp.git"
SDCP_COMMIT="c4880d057e80c7095eb02d227c860ae8d8ddfe54"   # egismoc-sdcp, 2026-10-16

# ── Paths ─────────────────────────────────────────────────────────────────────
FPRINT_LIB_DIR="/usr/local/lib/libfprint-egismoc-sdcp"
FPRINT_LIB="${FPRINT_LIB_DIR}/libfprint-2.so.2"
FPRINT_DROPIN_DIR="/etc/systemd/system/fprintd.service.d"
FPRINT_DROPIN="${FPRINT_DROPIN_DIR}/samsung-galaxybook-egismoc-sdcp.conf"
FPRINT_MARKER="/etc/samsung-galaxybook-egismoc-sdcp.installed"
FPRINT_STATE_DIR="/var/lib/samsung-galaxybook"
FPRINT_SYSLIB_HASH="${FPRINT_STATE_DIR}/libfprint-system.sha256"
FPRINT_BUILD_DIR="/tmp/libfprint-egismoc-sdcp"

FPRINT_MONITOR_SVC="samsung-galaxybook-fprint-sdcp-monitor.service"
FPRINT_USER_CHECK_SVC="samsung-galaxybook-fprint-sdcp-user-check.service"
FPRINT_USER_CHECK_TIMER="samsung-galaxybook-fprint-sdcp-user-check.timer"
FPRINT_CHECK_SCRIPT="/usr/local/bin/samsung-galaxybook-fprint-sdcp-monitor.sh"
FPRINT_USER_CHECK_SCRIPT="/usr/local/bin/samsung-galaxybook-fprint-sdcp-user-check.sh"
FPRINT_CLEANUP="/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh"
FPRINT_POLKIT_RULE="/etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-sdcp-monitor.rules"

# Old fingerprint-fix (feature/sdcp-v2 installed over the system libfprint)
OLD_MARKER="/etc/samsung-galaxybook-libfprint-sdcp-v2.installed"
OLD_HASH_FILE="/var/lib/samsung-galaxybook/libfprint.sha256"
OLD_CLEANUP="/usr/local/bin/samsung-galaxybook-libfprint-cleanup.sh"
OLD_MONITOR_SVC="samsung-galaxybook-fprint-monitor.service"
OLD_USER_CHECK_SVC="samsung-galaxybook-fprint-user-check.service"
OLD_USER_CHECK_TIMER="samsung-galaxybook-fprint-user-check.timer"

# ── Distro detection ──────────────────────────────────────────────────────────
detect_distro() {
    [[ -f /etc/os-release ]] || error "Cannot detect distro — /etc/os-release not found"
    source /etc/os-release
    local id="${ID,,}" like="${ID_LIKE:-}"; like="${like,,}"
    if [[ "$id" == "fedora" ]]; then DISTRO="fedora"
    elif [[ "$id" == "ubuntu" || "$like" == *"ubuntu"* || "$id" == "debian" || "$like" == *"debian"* ]]; then DISTRO="ubuntu"
    elif [[ "$id" == "arch" || "$like" == *"arch"* ]]; then DISTRO="arch"
    else error "Unsupported distro: $PRETTY_NAME"
    fi
}

# ── Hardware detection ────────────────────────────────────────────────────────
check_hardware() {
    local _vendor
    _vendor=$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo "unknown")
    if ! echo "$_vendor" | grep -qi "samsung"; then
        echo "Unsupported hardware: vendor is '$_vendor' — this script is for Samsung Galaxy Book laptops only"
        return 1
    fi
    return 0
}

# ── Check if fprintd can see our sensor via D-Bus ─────────────────────────────
check_fprintd_functional() {
    systemctl start fprintd 2>/dev/null || return 1
    local devices i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        devices=$(gdbus call --system \
            --dest net.reactivated.Fprint \
            --object-path /net/reactivated/Fprint/Manager \
            --method net.reactivated.Fprint.Manager.GetDevices 2>/dev/null || echo "")
        echo "$devices" | grep -q "Fprint/Device" && return 0
        sleep 1
    done
    return 1
}

# The system libfprint as the dynamic linker sees it (our copy is not in the
# ldconfig cache, so this is always the distro's library).
system_libfprint() {
    ldconfig -p | grep 'libfprint-2\.so\.2 ' | awk '{print $NF}' | head -1
}

reinstall_distro_libfprint() {
    if [[ "$DISTRO" == "fedora" ]]; then
        dnf reinstall -y libfprint
    elif [[ "$DISTRO" == "arch" ]]; then
        pacman -S --noconfirm libfprint
    else
        apt-get install -y --reinstall libfprint-2-2
    fi
}

# ── Install ───────────────────────────────────────────────────────────────────
detect_distro
check_hardware || exit 1

SENSOR_ON_BUS=$(lsusb 2>/dev/null | grep -iE "1c7a:05a5|1c7a:05a1" || true)
HARDWARE_USB_ID="1c7a:05a5|1c7a:05a1"

echo
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Installing: Fingerprint Fix (egismoc SDCP driver)    ║"
echo "╚════════════════════════════════════════════════════════════╝"

# ── Step 1: Check sensor is present ──────────────────────────────────────────
step "Fingerprint Step 1: Checking sensor is present"
[[ -z "$SENSOR_ON_BUS" ]] && \
    error "EgisTec SDCP fingerprint sensor not found on USB bus.\nExpected: 1c7a:05a5 (Galaxy Book 5) or 1c7a:05a1 (Galaxy Book 3/4)\nRun 'lsusb' to check what USB devices are present."
info "✓ Sensor found: $SENSOR_ON_BUS"

# ── Step 2: Install dependencies ─────────────────────────────────────────────
step "Fingerprint Step 2: Installing dependencies"
if [[ "$DISTRO" == "fedora" ]]; then
    dnf install -y \
        git gcc gcc-c++ meson ninja-build pkgconf-pkg-config \
        glib2-devel libgusb-devel cairo-devel openssl-devel systemd-devel \
        fprintd fprintd-pam libfprint libnotify \
        || error "Failed to install dependencies via dnf.\n  Check your internet connection and that Fedora repos are reachable (dnf repolist)."
elif [[ "$DISTRO" == "arch" ]]; then
    pacman -S --noconfirm --needed \
        git base-devel meson ninja pkgconf \
        glib2 libgusb cairo openssl systemd \
        fprintd libfprint libnotify \
        || error "Failed to install dependencies via pacman.\n  Check your internet connection and that Arch repos are reachable (pacman -Sy)."
else
    apt-get update -q \
        || error "apt-get update failed.\n  Check your internet connection and that the repos are reachable."
    apt-get install -y \
        git build-essential meson ninja-build pkg-config \
        libglib2.0-dev libgusb-dev libcairo2-dev libssl-dev systemd-dev \
        fprintd libfprint-2-2 libpam-fprintd libnotify-bin \
        || error "Failed to install dependencies via apt-get.\n  Check your internet connection and that the repos are reachable."
fi
info "Dependencies installed"

# ── Step 3: Migrate from the old fingerprint-fix if present ───────────────────
step "Fingerprint Step 3: Checking for the old fingerprint-fix"
if [[ -f "$OLD_MARKER" || -f "$OLD_HASH_FILE" || -f "$OLD_CLEANUP" \
      || -f "/etc/systemd/system/${OLD_MONITOR_SVC}" ]]; then
    warn "Old fingerprint-fix found (feature/sdcp-v2 built over the system libfprint)"
    info "Removing its monitor and restoring the distro libfprint."
    info "Enrolled fingerprints are KEPT — both builds use the same SDCP print format."
    if [[ -x "$OLD_CLEANUP" ]]; then
        "$OLD_CLEANUP" || true
    else
        rm -f "$OLD_HASH_FILE" "$OLD_MARKER" \
              "/etc/systemd/system/${OLD_MONITOR_SVC}" \
              /etc/polkit-1/rules.d/49-samsung-galaxybook-fprint-monitor.rules \
              /usr/local/bin/samsung-galaxybook-fprint-monitor.sh \
              /usr/local/bin/samsung-galaxybook-fprint-user-check.sh
        for _home in /home/*/; do
            _udir="${_home}.config/systemd/user"
            rm -f "${_udir}/${OLD_USER_CHECK_TIMER}" "${_udir}/${OLD_USER_CHECK_SVC}" \
                  "${_udir}/graphical-session.target.wants/${OLD_USER_CHECK_TIMER}" \
                  "${_udir}/graphical-session.target.wants/${OLD_USER_CHECK_SVC}"
        done
        systemctl daemon-reload 2>/dev/null || true
    fi
    rm -f /etc/samsung-galaxybook/session-helper.d/fingerprint-fix
    reinstall_distro_libfprint \
        || error "Could not reinstall the distro libfprint.\n  Run it manually, then re-run this installer:\n  Fedora: sudo dnf reinstall libfprint\n  Ubuntu: sudo apt install --reinstall libfprint-2-2\n  Arch:   sudo pacman -S libfprint"
    ldconfig
    MIGRATED=1
    info "✓ Old fingerprint-fix removed, distro libfprint restored"
else
    info "Old fingerprint-fix not installed"
fi

# ── Step 4: Check if the distro libfprint already supports our sensor ─────────
step "Fingerprint Step 4: Checking if the distro libfprint already supports the sensor"
# Skipped on a reinstall (our drop-in is active) and right after migrating from
# the old fix (we already know the distro libfprint wasn't enough).
if [[ -f "$FPRINT_DROPIN" || "${MIGRATED:-0}" == "1" || "${FORCE:-0}" == "1" ]]; then
    info "Skipped (reinstall, migration or FORCE=1)"
elif check_fprintd_functional; then
    info "✓ fprintd can already see the sensor with the distro libfprint."
    info "  This fix is probably not needed. If fingerprint login still does not"
    info "  work (enrolled prints not kept, or verify always fails), install it"
    info "  anyway with:  sudo FORCE=1 bash install.sh"
    exit 0
else
    info "Distro libfprint cannot use the sensor — proceeding with the fix"
fi

# ── Step 5: Fetch the pinned source ───────────────────────────────────────────
step "Fingerprint Step 5: Fetching libfprint-egismoc-sdcp at ${SDCP_COMMIT:0:12}"
rm -rf "$FPRINT_BUILD_DIR"
mkdir -p "$FPRINT_BUILD_DIR"
git -C "$FPRINT_BUILD_DIR" init -q
git -C "$FPRINT_BUILD_DIR" remote add origin "$SDCP_REPO_URL"
git -C "$FPRINT_BUILD_DIR" fetch -q --depth 1 origin "$SDCP_COMMIT" \
    || error "Could not fetch commit ${SDCP_COMMIT} from:\n  ${SDCP_REPO_URL}\n  Check your internet connection. If the repository or commit has been\n  removed, this fix needs updating."
git -C "$FPRINT_BUILD_DIR" checkout -q FETCH_HEAD
info "✓ Source at commit ${SDCP_COMMIT:0:12}"

# ── Step 6: Build only the egismoc driver ─────────────────────────────────────
step "Fingerprint Step 6: Building libfprint (egismoc driver only)"
cd "$FPRINT_BUILD_DIR"
meson setup build --buildtype=release \
    -Ddrivers=egismoc -Dtod=false -Ddoc=false -Dgtk-examples=false \
    -Dintrospection=false -Dinstalled-tests=false \
    || error "meson setup failed"
meson compile -C build || error "Build failed"
[[ -f build/libfprint/libfprint-2.so.2.0.0 ]] || error "Build finished but libfprint-2.so.2.0.0 was not produced"
info "Build complete"

# ── Step 7: Install the library and the fprintd drop-in ───────────────────────
step "Fingerprint Step 7: Installing the library for fprintd only"
install -Dm755 build/libfprint/libfprint-2.so.2.0.0 "$FPRINT_LIB"
command -v restorecon >/dev/null 2>&1 && restorecon -R "$FPRINT_LIB_DIR" 2>/dev/null || true
cd /
rm -rf "$FPRINT_BUILD_DIR"
mkdir -p "$FPRINT_DROPIN_DIR"
cat > "$FPRINT_DROPIN" << DROPINEOF
# Samsung Galaxy Book fingerprint fix — load the egismoc SDCP driver build.
# Remove this file (then: systemctl daemon-reload && systemctl restart fprintd)
# to go back to the distro libfprint.
[Service]
Environment=LD_LIBRARY_PATH=${FPRINT_LIB_DIR}
DROPINEOF
chmod 644 "$FPRINT_DROPIN"
systemctl daemon-reload
systemctl restart fprintd 2>/dev/null || true
info "✓ Library installed to $FPRINT_LIB_DIR (distro libfprint untouched)"

# ── Step 8: Confirm fprintd loaded our library ────────────────────────────────
step "Fingerprint Step 8: Checking fprintd uses the new driver"
if check_fprintd_functional \
        && grep -q "$FPRINT_LIB_DIR" "/proc/$(pidof fprintd 2>/dev/null | awk '{print $1}')/maps" 2>/dev/null; then
    info "✓ fprintd is running with the egismoc SDCP driver and sees the sensor"
else
    warn "Could not confirm fprintd loaded $FPRINT_LIB.\n       Check with: fprintd-list \"\$USER\"; sudo grep libfprint /proc/\$(pidof fprintd)/maps"
fi

# ── Step 9: Record state ──────────────────────────────────────────────────────
step "Fingerprint Step 9: Recording installed state"
mkdir -p "$FPRINT_STATE_DIR"
SYSLIB=$(system_libfprint)
if [[ -n "$SYSLIB" ]]; then
    sha256sum "$SYSLIB" | awk '{print $1}' > "$FPRINT_SYSLIB_HASH"
    chmod 644 "$FPRINT_SYSLIB_HASH"
fi
echo "${SDCP_COMMIT:0:12} (installed $(date '+%Y-%m-%d'))" > "$FPRINT_MARKER"
info "✓ Marker and distro libfprint hash stored"

# ── Step 10: Monitor — cleanup helper, scripts, polkit rule, services ─────────
step "Fingerprint Step 10: Installing the fingerprint monitor"

# Cleanup helper — removes the whole fix (used by the monitor once the distro
# libfprint supports the sensor). PAM fingerprint auth is left enabled.
cat > "$FPRINT_CLEANUP" << CLEANEOF
#!/bin/bash
# Samsung Galaxy Book — remove egismoc SDCP fingerprint fix and its monitor (runs as root)
rm -f "${FPRINT_DROPIN}"
rmdir "${FPRINT_DROPIN_DIR}" 2>/dev/null || true
rm -rf "${FPRINT_LIB_DIR}"
rm -f "${FPRINT_SYSLIB_HASH}" "${FPRINT_MARKER}"
rmdir "${FPRINT_STATE_DIR}" 2>/dev/null || true
rm -f "/etc/systemd/system/${FPRINT_MONITOR_SVC}" "${FPRINT_POLKIT_RULE}"
systemctl daemon-reload 2>/dev/null || true
for _home in /home/*/; do
    _udir="\${_home}.config/systemd/user"
    rm -f "\${_udir}/${FPRINT_USER_CHECK_TIMER}" "\${_udir}/${FPRINT_USER_CHECK_SVC}" \\
          "\${_udir}/graphical-session.target.wants/${FPRINT_USER_CHECK_TIMER}"
done
rm -f /etc/samsung-galaxybook/session-helper.d/fingerprint-fix-sdcp
# /run/samsung-galaxybook/fprint-sdcp-status is left for the user check script.
rm -f "${FPRINT_CHECK_SCRIPT}" "${FPRINT_USER_CHECK_SCRIPT}" "${FPRINT_CLEANUP}"
CLEANEOF
chown root:root "$FPRINT_CLEANUP"
chmod 750 "$FPRINT_CLEANUP"

# System monitor — runs as root when the user check script starts it.
cat > "$FPRINT_CHECK_SCRIPT" << 'MONITOREOF'
#!/bin/bash
# Samsung Galaxy Book — egismoc SDCP fingerprint fix monitor (system service, root)
# Writes any notification to FPRINT_STATUS_FILE; the user check script shows it.
FPRINT_LIB="__FPRINT_LIB__"
FPRINT_DROPIN="__FPRINT_DROPIN__"
FPRINT_MARKER="__FPRINT_MARKER__"
FPRINT_SYSLIB_HASH="__FPRINT_SYSLIB_HASH__"
FPRINT_CLEANUP="__FPRINT_CLEANUP__"
HARDWARE_USB_ID="__HARDWARE_USB_ID__"
FPRINT_STATUS_DIR="/run/samsung-galaxybook"
FPRINT_STATUS_FILE="${FPRINT_STATUS_DIR}/fprint-sdcp-status"
TAG="samsung-galaxybook-fprint-sdcp-monitor"

mkdir -p "$FPRINT_STATUS_DIR"; chmod 755 "$FPRINT_STATUS_DIR"
rm -f "$FPRINT_STATUS_FILE"

# File format: line 1 = icon, line 2 = title, line 3 = message.
notify_user() {
    local title="$1" msg="$2" icon="${3:-dialog-information}" tmp
    logger -t "$TAG" "$title: $msg"
    tmp=$(mktemp "${FPRINT_STATUS_DIR}/.fprint-sdcp-status.XXXXXX") || return 0
    printf '%s\n%s\n%s\n' "$icon" "$title" "$msg" > "$tmp"
    chmod 644 "$tmp"; mv -f "$tmp" "$FPRINT_STATUS_FILE"
}

fprintd_device_path() {
    gdbus call --system --dest net.reactivated.Fprint \
        --object-path /net/reactivated/Fprint/Manager \
        --method net.reactivated.Fprint.Manager.GetDevices 2>/dev/null \
        | grep -o '/net/reactivated/Fprint/Device/[0-9]*' | head -1
}

check_fprintd_functional() {
    systemctl start fprintd 2>/dev/null || return 1
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        [[ -n "$(fprintd_device_path)" ]] && return 0
        sleep 1
    done
    return 1
}

# Device listed AND reporting a real enrolment process.
check_sensor_usable() {
    check_fprintd_functional || return 1
    local dev stages
    dev=$(fprintd_device_path); [[ -n "$dev" ]] || return 1
    stages=$(gdbus call --system --dest net.reactivated.Fprint --object-path "$dev" \
        --method org.freedesktop.DBus.Properties.Get \
        net.reactivated.Fprint.Device num-enroll-stages 2>/dev/null \
        | grep -o '[0-9]\+' | tail -1)
    [[ "${stages:-0}" -gt 0 ]]
}

[[ -f "$FPRINT_MARKER" ]] || exit 0
SENSOR_ON_BUS=$(lsusb 2>/dev/null | grep -Ei "$HARDWARE_USB_ID" || true)

# 1. Our files must still be there.
if [[ ! -f "$FPRINT_LIB" || ! -f "$FPRINT_DROPIN" ]]; then
    notify_user "Samsung Galaxy Book — Fingerprint Fix Incomplete" \
        "Files of the fingerprint fix are missing, so fprintd is using the distro libfprint. Please reinstall the fingerprint fix." \
        "dialog-error"
    exit 0
fi

# 2. Distro libfprint changed? Test it on its own, with our drop-in disabled.
SYSLIB=$(ldconfig -p | grep 'libfprint-2\.so\.2 ' | awk '{print $NF}' | head -1)
if [[ -n "$SYSLIB" ]]; then
    CURRENT_HASH=$(sha256sum "$SYSLIB" | awk '{print $1}')
    STORED_HASH=$(cat "$FPRINT_SYSLIB_HASH" 2>/dev/null || true)
    if [[ "$CURRENT_HASH" != "$STORED_HASH" ]]; then
        logger -t "$TAG" "Distro libfprint changed — testing it without the fix"
        restore_dropin() {
            [[ -f "${FPRINT_DROPIN}.testing" ]] && mv -f "${FPRINT_DROPIN}.testing" "$FPRINT_DROPIN"
            systemctl daemon-reload; systemctl restart fprintd 2>/dev/null || true
        }
        trap restore_dropin EXIT
        mv -f "$FPRINT_DROPIN" "${FPRINT_DROPIN}.testing"
        systemctl daemon-reload; systemctl stop fprintd 2>/dev/null || true
        if [[ -n "$SENSOR_ON_BUS" ]] && check_sensor_usable; then
            trap - EXIT
            rm -f "${FPRINT_DROPIN}.testing"
            "$FPRINT_CLEANUP"
            systemctl restart fprintd 2>/dev/null || true
            notify_user "Samsung Galaxy Book — Fingerprint Fix No Longer Needed" \
                "Your distro's libfprint now supports the fingerprint sensor, so the fix has been removed. If fingerprint login stops working, re-enrol your fingerprints." \
                "dialog-information"
            exit 0
        fi
        restore_dropin; trap - EXIT
        echo "$CURRENT_HASH" > "$FPRINT_SYSLIB_HASH"
        logger -t "$TAG" "Distro libfprint still lacks support — fix kept"
    fi
fi

# 3. The fix should be working.
if [[ -n "$SENSOR_ON_BUS" ]] && ! check_fprintd_functional; then
    notify_user "Samsung Galaxy Book — Fingerprint Sensor Not Working" \
        "fprintd cannot see your fingerprint sensor. Please reinstall the fingerprint fix." \
        "dialog-error"
fi
MONITOREOF
# '#' as the sed separator: paths contain '/' and HARDWARE_USB_ID contains '|'.
sed -i -e "s#__FPRINT_LIB__#${FPRINT_LIB}#" \
       -e "s#__FPRINT_DROPIN__#${FPRINT_DROPIN}#" \
       -e "s#__FPRINT_MARKER__#${FPRINT_MARKER}#" \
       -e "s#__FPRINT_SYSLIB_HASH__#${FPRINT_SYSLIB_HASH}#" \
       -e "s#__FPRINT_CLEANUP__#${FPRINT_CLEANUP}#" \
       -e "s#__HARDWARE_USB_ID__#${HARDWARE_USB_ID}#" "$FPRINT_CHECK_SCRIPT"
chown root:root "$FPRINT_CHECK_SCRIPT"; chmod 755 "$FPRINT_CHECK_SCRIPT"

# User check script — run by a user timer 10s after login.
cat > "$FPRINT_USER_CHECK_SCRIPT" << USERCHECKEOF
#!/bin/bash
# Samsung Galaxy Book — egismoc SDCP fingerprint fix user check (runs as user)
# Starts the root monitor (allowed by polkit), then shows any notification it left.
FPRINT_STATUS_FILE="/run/samsung-galaxybook/fprint-sdcp-status"
[[ -f "${FPRINT_MARKER}" ]] || exit 0
systemctl start ${FPRINT_MONITOR_SVC} || exit 0
[[ -s "\$FPRINT_STATUS_FILE" ]] || exit 0
{ IFS= read -r ICON; IFS= read -r TITLE; IFS= read -r MSG; } < "\$FPRINT_STATUS_FILE"
[[ -n "\$TITLE" ]] || exit 0
notify-send -t 0 -a "Samsung Galaxy Book Fixes" -i "\${ICON:-dialog-information}" "\$TITLE" "\$MSG" \\
    || logger -t samsung-galaxybook-fprint-sdcp-user-check "notify-send failed: \$TITLE: \$MSG"
USERCHECKEOF
chown root:root "$FPRINT_USER_CHECK_SCRIPT"; chmod 755 "$FPRINT_USER_CHECK_SCRIPT"

cat > "$FPRINT_POLKIT_RULE" << POLKITEOF
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        action.lookup("unit") == "${FPRINT_MONITOR_SVC}" &&
        action.lookup("verb") == "start" &&
        (subject.isInGroup("wheel") || subject.isInGroup("sudo"))) {
        return polkit.Result.YES;
    }
});
POLKITEOF
chmod 644 "$FPRINT_POLKIT_RULE"

cat > "/etc/systemd/system/${FPRINT_MONITOR_SVC}" << SVCEOF
[Unit]
Description=Samsung Galaxy Book — egismoc SDCP fingerprint fix monitor

[Service]
Type=oneshot
ExecStart=${FPRINT_CHECK_SCRIPT}
StandardOutput=journal
StandardError=journal
SVCEOF
systemctl daemon-reload
info "✓ Monitor service and polkit rule installed"

FPRINT_USER=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$4 == "seat0" {print $3}' | head -1)
FPRINT_USER_ID=$(id -u "$FPRINT_USER" 2>/dev/null || true)
FPRINT_USER_SYSTEMD_DIR="/home/${FPRINT_USER}/.config/systemd/user"

_fp_user_systemctl() {
    sudo -u "$FPRINT_USER" \
        XDG_RUNTIME_DIR="/run/user/${FPRINT_USER_ID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${FPRINT_USER_ID}/bus" \
        systemctl --user "$@"
}

if [[ -z "$FPRINT_USER" || -z "$FPRINT_USER_ID" ]]; then
    warn "Could not detect logged-in user — skipping user monitor timer install"
else
    mkdir -p "$FPRINT_USER_SYSTEMD_DIR"
    cat > "${FPRINT_USER_SYSTEMD_DIR}/${FPRINT_USER_CHECK_SVC}" << USERSVCEOF
[Unit]
Description=Samsung Galaxy Book — egismoc SDCP fingerprint fix login check
# Started by ${FPRINT_USER_CHECK_TIMER}; no [Install] section on purpose.

[Service]
Type=oneshot
ExecStart=${FPRINT_USER_CHECK_SCRIPT}
USERSVCEOF
    cat > "${FPRINT_USER_SYSTEMD_DIR}/${FPRINT_USER_CHECK_TIMER}" << USERTIMEREOF
[Unit]
Description=Samsung Galaxy Book — egismoc SDCP fingerprint fix login check (10s after login)
PartOf=graphical-session.target
After=graphical-session.target
DefaultDependencies=no

[Timer]
OnActiveSec=10
AccuracySec=1s
Unit=${FPRINT_USER_CHECK_SVC}

[Install]
WantedBy=graphical-session.target
USERTIMEREOF
    chown -R "${FPRINT_USER}:${FPRINT_USER}" "$FPRINT_USER_SYSTEMD_DIR"
    _fp_user_systemctl daemon-reload 2>/dev/null || true
    _fp_user_systemctl enable "${FPRINT_USER_CHECK_TIMER}" \
        && info "✓ User timer enabled for $FPRINT_USER" \
        || warn "systemctl --user enable failed for ${FPRINT_USER_CHECK_TIMER}"
fi

# ── Step 11: Graphical session helper (Xfce and other desktops) ───────────────
step "Fingerprint Step 11: Checking the desktop starts graphical-session.target"
# Shared with other Galaxy Book fixes; each registers a marker and the last one
# uninstalled removes it (same helper as fingerprint-fix and webcam-toggle).
SESSION_HELPER_TARGET="/etc/systemd/user/samsung-galaxybook-session.target"
SESSION_HELPER_SCRIPT="/usr/local/bin/samsung-galaxybook-session-start.sh"
SESSION_HELPER_AUTOSTART="/etc/xdg/autostart/samsung-galaxybook-session.desktop"
SESSION_HELPER_USERS="/etc/samsung-galaxybook/session-helper.d"

install_session_helper() {
    cat > "$SESSION_HELPER_TARGET" << 'SESSTARGETEOF'
[Unit]
Description=Samsung Galaxy Book — graphical session (desktops without systemd session support)
BindsTo=graphical-session.target
Wants=graphical-session-pre.target
After=graphical-session-pre.target
SESSTARGETEOF
    chmod 644 "$SESSION_HELPER_TARGET"

    cat > "$SESSION_HELPER_SCRIPT" << 'SESSSCRIPTEOF'
#!/bin/bash
# Samsung Galaxy Book — start graphical-session.target on desktops that don't.
systemctl --user is-active --quiet graphical-session.target && exit 0
if command -v dbus-update-activation-environment >/dev/null 2>&1; then
    dbus-update-activation-environment --systemd --all
else
    systemctl --user import-environment DISPLAY XAUTHORITY WAYLAND_DISPLAY \
        XDG_CURRENT_DESKTOP XDG_SESSION_TYPE 2>/dev/null
fi
systemctl --user start samsung-galaxybook-session.target
SESSSCRIPTEOF
    chmod 755 "$SESSION_HELPER_SCRIPT"

    mkdir -p "$(dirname "$SESSION_HELPER_AUTOSTART")"
    cat > "$SESSION_HELPER_AUTOSTART" << SESSDESKTOPEOF
[Desktop Entry]
Type=Application
Name=Samsung Galaxy Book session helper
Comment=Starts systemd graphical-session.target on desktops that do not
Exec=${SESSION_HELPER_SCRIPT}
NoDisplay=true
X-GNOME-Autostart-enabled=true
SESSDESKTOPEOF
    chmod 644 "$SESSION_HELPER_AUTOSTART"

    mkdir -p "$SESSION_HELPER_USERS"
    touch "$SESSION_HELPER_USERS/fingerprint-fix-sdcp"
}

if [[ -z "$FPRINT_USER" || -z "$FPRINT_USER_ID" ]]; then
    warn "Could not detect logged-in user — skipping graphical session check"
elif [[ -f "$SESSION_HELPER_TARGET" ]] \
        || ! _fp_user_systemctl is-active --quiet graphical-session.target; then
    install_session_helper
    _fp_user_systemctl daemon-reload 2>/dev/null || true
    info "✓ Graphical session helper installed — the login check will run"
else
    info "Desktop starts graphical-session.target itself — no session helper needed"
fi

# ── Step 12: Enable fingerprint authentication ────────────────────────────────
step "Fingerprint Step 12: Enabling fingerprint authentication"
if [[ "$DISTRO" == "fedora" ]]; then
    authselect enable-feature with-fingerprint \
        && info "✓ Fingerprint auth enabled via authselect" \
        || warn "authselect failed — run 'sudo authselect enable-feature with-fingerprint' manually"
elif [[ "$DISTRO" == "arch" ]]; then
    info "Arch: PAM configuration is described in README.md"
else
    # Linux Mint's own fingerprint PAM profile (fingwit) conflicts with fprintd's.
    PAM_FPRINT_PROFILE="fprintd"
    if [[ -f /usr/share/pam-configs/fingwit ]]; then
        PAM_FPRINT_PROFILE="fingwit"
        pam-auth-update --remove fprintd --force 2>/dev/null || true
    fi
    if pam-auth-update --enable "$PAM_FPRINT_PROFILE" --force 2>/dev/null \
            && grep -q pam_fprintd /etc/pam.d/common-auth 2>/dev/null; then
        info "✓ Fingerprint PAM profile enabled ($PAM_FPRINT_PROFILE)"
    else
        warn "PAM activation could not be verified — run manually: sudo pam-auth-update"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
info "✓ Fingerprint fix installed — no reboot required"
echo
echo "  Existing SDCP enrolments (from the old fingerprint-fix) are kept."
echo "  Test with:  fprintd-verify"
echo
echo "  If verify never matches, the prints were enrolled with a non-SDCP"
echo "  driver. Delete them (this also frees their slots on the sensor),"
echo "  then enrol again:"
echo "      fprintd-delete \"\$USER\" && fprintd-enroll"
echo
echo "  Enrol in the desktop instead:"
echo "      KDE:   System Settings -> Users -> Fingerprint Authentication"
echo "      GNOME: Settings -> System -> Users -> Fingerprint Login"
echo "      Mint:  Menu -> Fingerprints"
echo
