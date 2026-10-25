#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP driver) — Install
# =============================================================================
# Self-contained. Run as root: sudo bash install.sh
#
# Builds ONLY the egismoc driver from libfprint-egismoc-sdcp (our fork of
# Abdallah Alkanani's repo: libfprint-TOD v1.95.2 + Joshua Grisham's Egis SDCP
# driver, hardened) and points fprintd at it with a systemd drop-in.
# The distro's libfprint is left untouched, so distro updates cannot overwrite
# this fix and removing it is just deleting the drop-in.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The installer needs its tools/ and lib/ folders — run it from the whole
# fingerprint-fix-sdcp folder, not on its own.
for _f in lib/sensor-check.c lib/fingerprint-manager.py lib/fingerprint-manager-helper.py \
          lib/galaxybook-fingerprint-manager.svg lib/patches/sdcp-kdf-openssl30.patch fingerprint-manager.sh \
          tools/fingerprint-pam.sh tools/arch-pam.sh tools/import-fingerprint.sh tools/export-fingerprint.sh; do
    [[ -f "$SCRIPT_DIR/$_f" ]] || { echo "Missing $SCRIPT_DIR/$_f — run install.sh from the complete fingerprint-fix-sdcp folder."; exit 1; }
done

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

# ── Source ────────────────────────────────────────────────────────────────────
# Builds the newest commit of SDCP_BRANCH in our fork of
# abdallah-alkanani/libfprint-egismoc-sdcp. The fork is the release channel:
# users get whatever it holds, so "Sync fork" on GitHub publishes an update.
#
# Test upstream changes BEFORE syncing the fork, by building the original repo:
#   sudo SDCP_REPO_URL=https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp.git bash install.sh
DEFAULT_SDCP_REPO_URL="https://github.com/david-bartlett/libfprint-egismoc-sdcp.git"
SDCP_REPO_URL="${SDCP_REPO_URL:-$DEFAULT_SDCP_REPO_URL}"
SDCP_BRANCH="egismoc-sdcp"
[[ "$SDCP_REPO_URL" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$ ]] \
    || { echo "ERROR: SDCP_REPO_URL must be an https://github.com/OWNER/REPO URL."; exit 1; }

# ── Paths ─────────────────────────────────────────────────────────────────────
FPRINT_LIB_DIR="/usr/local/lib/libfprint-egismoc-sdcp"
FPRINT_LIB="${FPRINT_LIB_DIR}/libfprint-2.so.2"
# Galaxy Book Fingerprint Manager (Step 14) — its files live in MGR_DIR
MGR_ID="galaxybook-fingerprint-manager"
MGR_DIR="${FPRINT_LIB_DIR}/manager"
MGR_BIN="/usr/local/bin/${MGR_ID}"
# The menu entry's file name must equal the app's ID (its Wayland app ID), or
# the taskbar can't match the window to it and shows a generic icon.
MGR_APP_ID="io.github.david_bartlett.GalaxyBookFingerprintManager"
# In /usr/share/applications: Cinnamon's menu doesn't notice a new entry in
# /usr/local/share/applications until you log in again (often not even then).
MGR_DESKTOP="/usr/share/applications/${MGR_APP_ID}.desktop"
MGR_DESKTOP_OLD="/usr/local/share/applications/${MGR_ID}.desktop"   # name used before 2026-10-25
MGR_DESKTOP_LOCAL="/usr/local/share/applications/${MGR_APP_ID}.desktop"   # place used before 2026-10-25
MGR_ICON="/usr/local/share/icons/hicolor/scalable/apps/${MGR_ID}.svg"
MGR_POLICY="/usr/share/polkit-1/actions/io.github.david-bartlett.${MGR_ID}.policy"
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

# Boot-time check that enrolled fingerprints are still stored on the sensor
FPRINT_SENSOR_CHECK="${FPRINT_LIB_DIR}/sensor-check"
FPRINT_BOOT_CHECK_SCRIPT="/usr/local/bin/samsung-galaxybook-fprint-sdcp-boot-check.sh"
FPRINT_BOOT_CHECK_SVC="samsung-galaxybook-fprint-sdcp-boot-check.service"
FPRINT_BOOT_STATUS="/run/samsung-galaxybook/fprint-sdcp-boot-status"
FPRINT_REMOVED_DIR="${FPRINT_STATE_DIR}/removed-fingerprints"

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
# Polls once a second for up to $1 seconds (default 10) and returns as soon as a
# device is listed — fprintd resets the sensor over USB as it starts, so it can
# take a few seconds to appear.
check_fprintd_functional() {
    local tries="${1:-10}" devices i
    systemctl start fprintd 2>/dev/null || return 1
    for ((i = 0; i < tries; i++)); do
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
        glib2 glib2-devel libgusb cairo openssl systemd \
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
# Only 3 seconds here: the distro libfprint can't use these sensors, so this
# would otherwise always wait the full 10. Missing a slow start just means the
# fix is installed anyway, which is harmless.
elif check_fprintd_functional 3; then
    info "✓ fprintd can already see the sensor with the distro libfprint."
    info "  This fix is probably not needed. If fingerprint login still does not"
    info "  work (enrolled prints not kept, or verify always fails), install it"
    info "  anyway with:  sudo FORCE=1 bash install.sh"
    exit 0
else
    info "Distro libfprint cannot use the sensor — proceeding with the fix"
fi

# ── Step 5: Fetch the source ──────────────────────────────────────────────────
step "Fingerprint Step 5: Fetching libfprint-egismoc-sdcp ($SDCP_BRANCH)"
info "From: $SDCP_REPO_URL"
rm -rf "$FPRINT_BUILD_DIR"
mkdir -p "$FPRINT_BUILD_DIR"
git -C "$FPRINT_BUILD_DIR" init -q
git -C "$FPRINT_BUILD_DIR" remote add origin "$SDCP_REPO_URL"
git -C "$FPRINT_BUILD_DIR" fetch -q --depth 1 origin "$SDCP_BRANCH" \
    || error "Could not fetch branch ${SDCP_BRANCH} from:\n  ${SDCP_REPO_URL}\n  Check your internet connection and that the repository still exists."
git -C "$FPRINT_BUILD_DIR" checkout -q FETCH_HEAD
SDCP_COMMIT=$(git -C "$FPRINT_BUILD_DIR" rev-parse HEAD)
SDCP_DATE=$(git -C "$FPRINT_BUILD_DIR" log -1 --format=%cs)
if [[ "$SDCP_REPO_URL" == "$DEFAULT_SDCP_REPO_URL" ]]; then
    SDCP_SOURCE="fork"
else
    SDCP_SOURCE="$SDCP_REPO_URL"
    warn "Building from ${SDCP_REPO_URL}, not the usual fork — for testing.\n       Run the installer without SDCP_REPO_URL to go back (enrolments are kept)."
fi
info "✓ Source at commit ${SDCP_COMMIT:0:12} (${SDCP_DATE})"

# Fixes kept in lib/patches/ until they are in the fork. Each one is applied
# only if the source still needs it: skipped when the source already has it,
# and the install stops if the source has changed so much it no longer fits.
SDCP_FIXES=()
for _patch in "$SCRIPT_DIR"/lib/patches/*.patch; do
    [[ -f "$_patch" ]] || continue
    _name=$(basename "$_patch" .patch)
    _desc=$(sed -n 's/^Subject: //p' "$_patch" | head -1)
    if git -C "$FPRINT_BUILD_DIR" apply --check "$_patch" 2>/dev/null; then
        git -C "$FPRINT_BUILD_DIR" apply "$_patch" || error "Could not apply fix ${_name}"
        SDCP_FIXES+=("$_name")
        info "✓ Applied fix: ${_desc:-$_name}"
    elif git -C "$FPRINT_BUILD_DIR" apply --reverse --check "$_patch" 2>/dev/null; then
        info "Fix already in the source — not needed: ${_desc:-$_name}"
    elif _needed=$(sed -n 's/^Needed-if-source-has: //p' "$_patch" | head -1) && [[ -n "$_needed" ]] \
            && [[ -f "$FPRINT_BUILD_DIR/${_needed%%|*}" ]] \
            && ! grep -qF -- "${_needed#*|}" "$FPRINT_BUILD_DIR/${_needed%%|*}"; then
        # Fixed in the source in a different way: the code the fix replaces is gone.
        info "Fix already in the source — not needed: ${_desc:-$_name}"
    else
        error "Fix ${_name} no longer fits the source at commit ${SDCP_COMMIT:0:12}.\n  The source has changed: check whether it still needs\n  lib/patches/${_name}.patch, then update or remove that file."
    fi
done

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

# The boot-time sensor check helper, linked against this build. The runpath
# makes it load the library from FPRINT_LIB_DIR, never the distro libfprint.
SENSOR_CHECK_BUILT=false
# shellcheck disable=SC2046  # pkg-config output must be word-split
if gcc -O2 -Wall -o build/sensor-check "$SCRIPT_DIR/lib/sensor-check.c" \
        -Ilibfprint -Ibuild/libfprint \
        $(pkg-config --cflags glib-2.0 gio-2.0 gobject-2.0 gusb) \
        -Lbuild/libfprint -lfprint-2 \
        $(pkg-config --libs glib-2.0 gio-2.0 gobject-2.0) \
        -Wl,-rpath,"$FPRINT_LIB_DIR"; then
    SENSOR_CHECK_BUILT=true
    info "Sensor check helper built"
else
    warn "Could not build the sensor check helper — the fix works, but you won't be told\n       if fingerprints are removed from the sensor (e.g. by Windows)."
fi

# ── Step 7: Install the library and the fprintd drop-in ───────────────────────
step "Fingerprint Step 7: Installing the library for fprintd only"
install -Dm755 build/libfprint/libfprint-2.so.2.0.0 "$FPRINT_LIB"
$SENSOR_CHECK_BUILT && install -m755 build/sensor-check "$FPRINT_SENSOR_CHECK"
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
echo "${SDCP_COMMIT:0:12} ${SDCP_DATE} ${SDCP_SOURCE}${SDCP_FIXES[*]:+ +${SDCP_FIXES[*]}} (installed $(date '+%Y-%m-%d'))" > "$FPRINT_MARKER"
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
rm -f "${MGR_BIN}" "${MGR_DESKTOP}" "${MGR_DESKTOP_OLD}" "${MGR_DESKTOP_LOCAL}" "${MGR_ICON}" "${MGR_POLICY}"
rm -f "${FPRINT_SYSLIB_HASH}" "${FPRINT_MARKER}"
rm -rf "${FPRINT_REMOVED_DIR}"
rmdir "${FPRINT_STATE_DIR}" 2>/dev/null || true
systemctl disable "${FPRINT_BOOT_CHECK_SVC}" 2>/dev/null || true
rm -f "/etc/systemd/system/${FPRINT_MONITOR_SVC}" "/etc/systemd/system/${FPRINT_BOOT_CHECK_SVC}" \\
      "${FPRINT_POLKIT_RULE}" "${FPRINT_BOOT_STATUS}"
systemctl daemon-reload 2>/dev/null || true
for _home in /home/*/; do
    _udir="\${_home}.config/systemd/user"
    rm -f "\${_udir}/${FPRINT_USER_CHECK_TIMER}" "\${_udir}/${FPRINT_USER_CHECK_SVC}" \\
          "\${_udir}/graphical-session.target.wants/${FPRINT_USER_CHECK_TIMER}" \\
          "\${_home}.cache/samsung-galaxybook/fprint-sdcp-boot-shown"
done
rm -f /etc/samsung-galaxybook/session-helper.d/fingerprint-fix-sdcp
# /run/samsung-galaxybook/fprint-sdcp-status is left for the user check script.
rm -f "${FPRINT_CHECK_SCRIPT}" "${FPRINT_USER_CHECK_SCRIPT}" "${FPRINT_BOOT_CHECK_SCRIPT}" "${FPRINT_CLEANUP}"
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
# 1. Starts the root monitor (allowed by polkit) and shows any notification it left.
# 2. Shows the result of the boot-time sensor check, once per boot.
# Status files: line 1 = icon, line 2 = title, line 3 = message.
FPRINT_STATUS_FILE="/run/samsung-galaxybook/fprint-sdcp-status"
FPRINT_BOOT_STATUS="${FPRINT_BOOT_STATUS}"
[[ -f "${FPRINT_MARKER}" ]] || exit 0

show() {
    local ICON TITLE MSG
    { IFS= read -r ICON; IFS= read -r TITLE; IFS= read -r MSG; } < "\$1"
    [[ -n "\$TITLE" ]] || return 0
    notify-send -t 0 -a "Samsung Galaxy Book Fixes" -i "\${ICON:-dialog-information}" "\$TITLE" "\$MSG" \\
        || logger -t samsung-galaxybook-fprint-sdcp-user-check "notify-send failed: \$TITLE: \$MSG"
}

if systemctl start ${FPRINT_MONITOR_SVC}; then
    [[ -s "\$FPRINT_STATUS_FILE" ]] && show "\$FPRINT_STATUS_FILE"
fi

# The boot check result lives until the next reboot; show it once per boot,
# not at every login.
if [[ -s "\$FPRINT_BOOT_STATUS" ]]; then
    SHOWN="\${XDG_CACHE_HOME:-\$HOME/.cache}/samsung-galaxybook/fprint-sdcp-boot-shown"
    BOOT_ID=\$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
    if [[ "\$(cat "\$SHOWN" 2>/dev/null)" != "\$BOOT_ID" ]]; then
        show "\$FPRINT_BOOT_STATUS"
        mkdir -p "\$(dirname "\$SHOWN")" && echo "\$BOOT_ID" > "\$SHOWN"
    fi
fi
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

# Boot-time sensor check — runs before fprintd, so it has the sensor to itself.
# Its result is written to FPRINT_BOOT_STATUS and shown by the login check.
cat > "$FPRINT_BOOT_CHECK_SCRIPT" << BOOTCHECKEOF
#!/bin/bash
# Samsung Galaxy Book — check enrolled fingerprints are still on the sensor
# (runs at boot as root, before fprintd). Never fails the boot.
SENSOR_CHECK="${FPRINT_SENSOR_CHECK}"
STATUS="${FPRINT_BOOT_STATUS}"
[[ -f "${FPRINT_MARKER}" && -x "\$SENSOR_CHECK" ]] || exit 0
mkdir -p "\$(dirname "\$STATUS")"; chmod 755 "\$(dirname "\$STATUS")"
rm -f "\$STATUS"

# Nothing enrolled at all: nothing to check.
[[ -n "\$(find /var/lib/fprint -type f 2>/dev/null | head -1)" ]] || exit 0

# Wait up to 8 seconds for the sensor to appear on USB.
found=false
for _ in \$(seq 1 40); do
    for d in /sys/bus/usb/devices/*; do
        [[ "\$(cat "\$d/idVendor" 2>/dev/null)" == "1c7a" ]] || continue
        [[ "\$(cat "\$d/idProduct" 2>/dev/null)" =~ ^05a[15]\$ ]] && found=true && break 2
    done
    sleep 0.2
done
\$found || { echo "Fingerprint sensor not found — skipping check"; exit 0; }

OUT=\$(timeout 8 "\$SENSOR_CHECK" 2>&1); RC=\$?
echo "\$OUT"
[[ \$RC -eq 1 ]] || exit 0

FINGERS=(unknown left-thumb left-index-finger left-middle-finger left-ring-finger
         left-little-finger right-thumb right-index-finger right-middle-finger
         right-ring-finger right-little-finger)
LOST=()
# Dead records are MOVED (not deleted) to a dated safety folder, so a false
# alarm could be undone by moving them back. The last 5 folders are kept.
REMOVED="${FPRINT_REMOVED_DIR}/\$(date +%Y-%m-%d_%H%M%S)"
ALL_CLEARED=true
while read -r _tag _user _finger _path; do
    [[ "\$_tag" == "MISSING" ]] || continue
    _name="\$_finger"
    # fprintd names records by finger number in hex: 1-9, a = right little finger
    [[ "\$_finger" =~ ^[1-9a]\$ ]] && _name="\${FINGERS[\$((16#\$_finger))]}"
    LOST+=("\${_name} (\${_user})")
    # Only ever touch records inside fprintd's own folder.
    _done=false
    if [[ "\$_path" == /var/lib/fprint/* && "\$_path" != *..* && -f "\$_path" ]]; then
        _dest="\$REMOVED/\${_path#/var/lib/fprint/}"
        mkdir -p "\$(dirname "\$_dest")" && mv -f "\$_path" "\$_dest" \\
            && echo "Moved dead record \$_path to \$_dest" && _done=true
    fi
    \$_done || { ALL_CLEARED=false; echo "Did not clear record: \$_path"; }
done <<< "\$OUT"
[[ \${#LOST[@]} -gt 0 ]] || exit 0
chmod -R go-rwx "${FPRINT_REMOVED_DIR}" 2>/dev/null
ls -1dt "${FPRINT_REMOVED_DIR}"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
_list=\$(printf '%s, ' "\${LOST[@]}"); _list="\${_list%, }"
if \$ALL_CLEARED; then
    _next="They have been cleared from this system — please enrol them again."
else
    _next="Please remove them in your fingerprint settings (or run: fprintd-delete USER) and enrol them again."
fi
printf '%s\n%s\n%s\n' "dialog-warning" \\
    "Samsung Galaxy Book — Fingerprint Removed From Sensor" \\
    "These fingerprints are no longer stored on the sensor: \${_list}. This usually happens after booting Windows with its fingerprint device enabled. \${_next}" \\
    > "\$STATUS"
chmod 644 "\$STATUS"
exit 0
BOOTCHECKEOF
chown root:root "$FPRINT_BOOT_CHECK_SCRIPT"; chmod 755 "$FPRINT_BOOT_CHECK_SCRIPT"

cat > "/etc/systemd/system/${FPRINT_BOOT_CHECK_SVC}" << BOOTSVCEOF
[Unit]
Description=Samsung Galaxy Book — check enrolled fingerprints are still on the sensor
# Runs in parallel with the rest of the boot; only fprintd waits for it, so
# nothing else can use the sensor while it is being checked.
Before=fprintd.service
After=systemd-udevd.service local-fs.target
ConditionPathExists=${FPRINT_MARKER}

[Service]
Type=oneshot
ExecStart=${FPRINT_BOOT_CHECK_SCRIPT}
TimeoutStartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
BOOTSVCEOF
systemctl daemon-reload
if $SENSOR_CHECK_BUILT; then
    systemctl enable "$FPRINT_BOOT_CHECK_SVC" >/dev/null 2>&1 \
        && info "✓ Boot-time sensor check enabled" \
        || warn "Could not enable ${FPRINT_BOOT_CHECK_SVC}"
fi

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
# fingerprint-pam.sh does it the way each distro expects (authselect on
# Fedora, pam-auth-update on Ubuntu/Debian/MX, Mint's fingwit profile on Mint,
# arch-pam.sh on Arch); the Fingerprint Manager uses the same script.
if [[ "$DISTRO" != "arch" ]]; then
    bash "$SCRIPT_DIR/tools/fingerprint-pam.sh" enable \
        || warn "Could not enable fingerprint authentication — try: sudo bash $SCRIPT_DIR/tools/fingerprint-pam.sh enable"
else
    # Arch-based distros have no authselect/pam-auth-update. Offer to add
    # fingerprint to sudo and polkit (pkexec, admin prompts). This edits PAM,
    # so it waits for an answer (no timeout) and never happens unattended.
    # FPRINT_PAM=1 / FPRINT_PAM=0 answers without asking.
    _pam="${FPRINT_PAM:-}"
    if [[ -z "$_pam" ]]; then
        if [[ -t 0 ]]; then
            echo "  Arch-based distros don't enable fingerprint for sudo and admin prompts"
            echo "  by themselves. This can add it to /etc/pam.d/sudo and polkit-1"
            echo "  (pkexec, graphical password prompts), with backups. Until a finger is"
            echo "  enrolled, they keep asking for your password as normal."
            read -r -p "  Enable fingerprint for sudo and admin prompts? [Y/n] " _ans || _ans=n
            [[ -z "$_ans" || "${_ans,,}" == y* ]] && _pam=1 || _pam=0
        else
            _pam=0
            info "No terminal — not changing PAM. To enable later: sudo bash $SCRIPT_DIR/tools/fingerprint-pam.sh enable"
        fi
    fi
    if [[ "$_pam" == "1" ]]; then
        bash "$SCRIPT_DIR/tools/fingerprint-pam.sh" enable \
            || warn "Could not enable it — see README.md for the manual PAM steps"
    elif [[ -t 0 || -n "${FPRINT_PAM:-}" ]]; then
        info "PAM not changed. To enable later: sudo bash $SCRIPT_DIR/tools/fingerprint-pam.sh enable"
    fi
    info "The KDE lock screen uses the fingerprint without changes (kde-fingerprint)"
fi

# ── Step 13: Import fingerprints exported from another install ───────────────
# ~/fingerprint-export.tgz (where export-fingerprint.sh writes it) is imported
# automatically — import-fingerprint.sh first checks its fingerprints are
# still on the sensor. Without it, the user is asked [y/N] (30s, then skip)
# and, only if they say yes, for the path (no timeout).
# FPRINT_IMPORT=FILE imports a file kept anywhere else without asking.
step "Fingerprint Step 13: Importing fingerprints from another install (optional)"
_imp_user="${FPRINT_USER:-${SUDO_USER:-}}"
_imp_home=""
[[ -n "$_imp_user" ]] && _imp_home=$(getent passwd "$_imp_user" | cut -d: -f6)
_imp_file="${FPRINT_IMPORT:-}"
if [[ -z "$_imp_user" ]]; then
    info "Could not tell which user to import for — skipping"
elif [[ -n "$(find "/var/lib/fprint/$_imp_user" -type f 2>/dev/null | head -1)" ]]; then
    info "${_imp_user} already has fingerprints enrolled — skipping import"
else
    if [[ -z "$_imp_file" && -n "$_imp_home" && -f "$_imp_home/fingerprint-export.tgz" ]]; then
        _imp_file="$_imp_home/fingerprint-export.tgz"
        info "Found $_imp_file — importing it"
    elif [[ -z "$_imp_file" && -t 0 ]]; then
        if read -r -t 30 -p "  Do you have fingerprints exported from another install to import? [y/N] (skips in 30s) " _ans; then
            if [[ "${_ans,,}" == y* ]]; then
                while true; do
                    read -r -p "  Path to the export file (Enter to skip): " _imp_file || _imp_file=""
                    [[ -z "$_imp_file" ]] && break
                    # shellcheck disable=SC2088  # a typed "~/" means the user's home
                    [[ "$_imp_file" == "~/"* && -n "$_imp_home" ]] && _imp_file="$_imp_home/${_imp_file#\~/}"
                    [[ -f "$_imp_file" ]] && break
                    echo "  Not found: $_imp_file"
                done
            fi
        else
            echo; info "No answer — skipping import"
        fi
    fi
    if [[ -n "$_imp_file" ]]; then
        bash "$SCRIPT_DIR/tools/import-fingerprint.sh" --user "$_imp_user" "$_imp_file" \
            || warn "Not imported — the fix is installed. Enrol instead, or fix the problem above and run:\n       sudo bash $SCRIPT_DIR/tools/import-fingerprint.sh $_imp_file"
    fi
fi

# ── Step 14: Galaxy Book Fingerprint Manager ──────────────────────────────────
# A root-owned copy of the Manager (window + helper + tools), so the helper that
# pkexec runs as root can't be changed by anything running as the user. It
# lives inside FPRINT_LIB_DIR, so uninstalling the fix (or the monitor's
# cleanup) removes it with the library. Its GUI packages are installed here,
# separately: if they fail, the fix itself is still fine.
step "Fingerprint Step 14: Installing the Galaxy Book Fingerprint Manager"
case "$DISTRO" in
    fedora) dnf install -y python3-gobject python3-cairo gtk3 polkit ;;
    arch)   pacman -S --noconfirm --needed python-gobject python-cairo gtk3 polkit ;;
    *)      apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-fprint-2.0 pkexec ;;
esac >/dev/null 2>&1 \
    || warn "Could not install the Fingerprint Manager's packages — it will list what it needs when started."

rm -rf "$MGR_DIR"
install -d -m 755 -o root -g root "$MGR_DIR" "$MGR_DIR/lib" "$MGR_DIR/tools"
install -m 755 -o root -g root "$SCRIPT_DIR/fingerprint-manager.sh" "$MGR_DIR/"
install -m 755 -o root -g root "$SCRIPT_DIR/lib/fingerprint-manager.py" \
    "$SCRIPT_DIR/lib/fingerprint-manager-helper.py" "$MGR_DIR/lib/"
install -m 755 -o root -g root "$SCRIPT_DIR"/tools/*.sh "$MGR_DIR/tools/"
mkdir -p "$(dirname "$MGR_BIN")"
ln -sfn "$MGR_DIR/fingerprint-manager.sh" "$MGR_BIN"
install -Dm 644 "$SCRIPT_DIR/lib/${MGR_ID}.svg" "$MGR_ICON"

mkdir -p "$(dirname "$MGR_DESKTOP")"
rm -f "$MGR_DESKTOP_OLD" "$MGR_DESKTOP_LOCAL"
cat > "$MGR_DESKTOP" << MGRDESKTOPEOF
[Desktop Entry]
Type=Application
Name=Galaxy Book Fingerprint Manager
GenericName=Fingerprint Manager
Comment=From Samsung Galaxy Book Fixes (fingerprint-fix-sdcp): test, enrol, share and tidy fingerprints
Exec=${MGR_BIN}
Icon=${MGR_ID}
Terminal=false
Categories=Settings;HardwareSettings;
Keywords=fingerprint;fprint;sensor;login;galaxy;book;
StartupWMClass=${MGR_APP_ID}
MGRDESKTOPEOF
chmod 644 "$MGR_DESKTOP"

# polkit: the password prompt names this app instead of "run /usr/bin/python3".
# It only applies to the installed helper's exact path.
mkdir -p "$(dirname "$MGR_POLICY")"
cat > "$MGR_POLICY" << MGRPOLICYEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<!-- Installed by Samsung Galaxy Book Fixes (fingerprint-fix-sdcp) -->
<policyconfig>
  <vendor>Samsung Galaxy Book Fixes (unofficial)</vendor>
  <action id="io.github.david-bartlett.${MGR_ID}">
    <description>Run the Galaxy Book Fingerprint Manager</description>
    <message>Galaxy Book Fingerprint Manager needs administrator access to read and manage the fingerprint sensor</message>
    <icon_name>${MGR_ID}</icon_name>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">${MGR_DIR}/lib/fingerprint-manager-helper.py</annotate>
  </action>
</policyconfig>
MGRPOLICYEOF
chmod 644 "$MGR_POLICY"

command -v restorecon >/dev/null 2>&1 \
    && restorecon -R "$MGR_DIR" "$MGR_BIN" "$MGR_DESKTOP" "$MGR_ICON" "$MGR_POLICY" 2>/dev/null || true
# Refresh the icon cache only if there is one (none is fine: GTK then reads the folder).
[[ -f /usr/local/share/icons/hicolor/icon-theme.cache ]] && command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || true
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
    [[ -d /usr/local/share/applications ]] \
        && update-desktop-database -q /usr/local/share/applications 2>/dev/null || true
fi
# An earlier test version could add a per-user menu entry — remove it.
if [[ -n "${SUDO_USER:-}" ]]; then
    _home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    rm -f "$_home/.local/share/applications/samsung-galaxybook-fingerprint-manager.desktop"
fi
info "✓ Galaxy Book Fingerprint Manager installed (app menu, or: ${MGR_ID})"

# ── Done ──────────────────────────────────────────────────────────────────────
info "✓ Fingerprint fix installed — no reboot required"
info "Built from: $SDCP_REPO_URL"
info "            branch $SDCP_BRANCH, commit ${SDCP_COMMIT:0:12} (${SDCP_DATE})"
[[ ${#SDCP_FIXES[@]} -gt 0 ]] && info "            with fixes from lib/patches: ${SDCP_FIXES[*]}"
[[ "$SDCP_SOURCE" == "fork" ]] \
    || warn "This is a TEST build (not the usual fork). Run the installer again without\n       SDCP_REPO_URL to go back to the fork's build."
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
echo "      Any desktop (and Xfce, e.g. MX Linux, which has no fingerprint"
echo "      settings page): Galaxy Book Fingerprint Manager in the app menu"
echo
echo "  Fingerprints exported on another install of this laptop"
echo "  (export-fingerprint.sh) can be imported here instead of enrolling:"
echo "      sudo bash $SCRIPT_DIR/tools/import-fingerprint.sh ~/fingerprint-export.tgz"
echo
echo "  Galaxy Book Fingerprint Manager — test, enrol, export/import and more"
echo "  in a window: find it in your app menu, or run (as yourself, not sudo):"
echo "      ${MGR_ID}"
echo

# ── Offer to open the Galaxy Book Fingerprint Manager ────────────────────────
# It must run as the user, in their desktop session — never as root. With
# systemd, systemd-run starts it in the user's own session (their manager
# knows WAYLAND_DISPLAY / DISPLAY); otherwise the display settings are taken
# from one of the user's desktop processes. Only from a terminal, only if the
# user is logged into a desktop, and only if they say yes (30 s, then skip).
# FPRINT_OPEN_MANAGER=1 / =0 answers without asking.
open_manager() {
    local user="$1" uid env_file pid var vals=()
    uid=$(id -u "$user" 2>/dev/null) || return 1
    if command -v systemd-run >/dev/null 2>&1 \
       && systemctl --user -M "${user}@" show-environment 2>/dev/null | grep -qE '^(WAYLAND_DISPLAY|DISPLAY)='; then
        systemd-run --user -M "${user}@" --collect --quiet "$MGR_BIN" 2>/dev/null && return 0
    fi
    # No systemd user session: borrow the display settings from a desktop process.
    for pid in $(pgrep -u "$uid" -x 'plasmashell|gnome-shell|cinnamon|xfce4-session|xfce4-panel|mate-session|lxqt-session|budgie-wm|marco|xfwm4' 2>/dev/null); do
        env_file="/proc/$pid/environ"
        [[ -r "$env_file" ]] || continue
        for var in DISPLAY WAYLAND_DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XDG_CURRENT_DESKTOP; do
            local v
            v=$(tr '\0' '\n' < "$env_file" | grep -m1 "^${var}=") && vals+=("$v")
        done
        printf '%s\n' "${vals[@]}" | grep -qE '^(WAYLAND_DISPLAY|DISPLAY)=' || { vals=(); continue; }
        runuser -u "$user" -- env "${vals[@]}" setsid -f "$MGR_BIN" >/dev/null 2>&1 && return 0
        return 1
    done
    return 1
}

_open_user="${SUDO_USER:-}"
if [[ -n "$_open_user" && "$_open_user" != "root" && -x "$MGR_BIN" ]]; then
    _open="${FPRINT_OPEN_MANAGER:-}"
    if [[ -z "$_open" ]]; then
        if [[ -t 0 ]]; then
            read -r -t 30 -p "  Open the Galaxy Book Fingerprint Manager now? [Y/n] " _ans || { echo; _ans=n; }
            [[ -z "$_ans" || "${_ans,,}" == y* ]] && _open=1 || _open=0
        else
            _open=0
        fi
    fi
    if [[ "$_open" == "1" ]]; then
        if open_manager "$_open_user"; then
            if [[ -z "$(find "/var/lib/fprint/${_open_user}" -type f 2>/dev/null | head -1)" ]]; then
                info "Opening the Galaxy Book Fingerprint Manager — enrol a finger there (Enrol a finger card)"
            else
                info "Opening the Galaxy Book Fingerprint Manager"
            fi
        else
            info "Couldn't open it from here (no desktop session found) — find Galaxy Book Fingerprint Manager in your app menu"
        fi
    fi
fi
