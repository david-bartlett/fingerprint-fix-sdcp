#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP driver) — Install
# =============================================================================
# Self-contained. Run as root:
#   sudo bash install.sh                  the driver and the Fingerprint Manager
#   sudo bash install.sh --driver-only    only the driver (enrol in your desktop's
#                                         settings; no monitor or boot check)
#   sudo bash install.sh --manager-only   only the Fingerprint Manager (e.g. once
#                                         the distro's own libfprint has SDCP)
# Fingerprint login is turned on either way. Installing one part later adds it
# to what is already installed.
#
# Builds ONLY the egismoc driver from libfprint-egismoc-sdcp (our fork of
# Abdallah Alkanani's repo: libfprint-TOD v1.95.2 + Joshua Grisham's Egis SDCP
# driver, hardened) and points fprintd at it with a systemd drop-in.
# The distro's libfprint is left untouched, so distro updates cannot overwrite
# this fix and removing it is just deleting the drop-in.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Which parts to install: both, or one of them.
WANT_DRIVER=true WANT_MGR=true
case "${1:-}" in
    "")             ;;
    --driver-only)  WANT_MGR=false ;;
    --manager-only) WANT_DRIVER=false ;;
    -h|--help)      sed -n '5,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)              echo "Unknown option: $1 (use --driver-only, --manager-only, or nothing)"; exit 1 ;;
esac
# The installer needs its tools/ and lib/ folders — run it from the whole
# fingerprint-fix-sdcp folder, not on its own.
for _f in lib/sensor-check.py lib/fingerprint-manager.py lib/fingerprint-manager-helper.py \
          lib/galaxybook-fingerprint-manager.svg fingerprint-manager.sh \
          tools/fingerprint-pam.sh tools/arch-pam.sh tools/import-fingerprint.sh tools/export-fingerprint.sh \
          lib/fixpaths.sh lib/update_check.py lib/notify-open-manager.sh lib/notify-update.sh lib/distro-driver-check.py \
          lib/terminal.py lib/update-in-terminal.sh lib/shared_slots.py \
          packaging/render.sh packaging/files/monitor.sh.in packaging/files/mgr-cleanup.sh.in \
          packaging/files/fprintd-env.sh.in packaging/files/dropin.conf.in lib/other-fix.sh \
          VERSION DRIVER; do
    [[ -f "$SCRIPT_DIR/$_f" ]] || { echo "Missing $SCRIPT_DIR/$_f — run install.sh from the complete fingerprint-fix-sdcp folder."; exit 1; }
done

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run as root: sudo bash install.sh"
    exit 1
fi

# Installed from a package (rpm, deb or pacman)? Then the package manager
# updates and removes it; installing over it here would leave two copies, and
# mixing a package with an install.sh part isn't supported.
if [[ -f /usr/lib/fingerprint-fix-sdcp/installed || -f /usr/lib/galaxybook-fingerprint-manager/installed ]]; then
    echo "fingerprint-fix-sdcp is installed as packages — update them with your package"
    echo "manager instead. To use install.sh, remove the packages first (enrolled"
    echo "fingerprints are kept): sudo pacman -R / dnf remove / apt remove"
    echo "fingerprint-fix-sdcp galaxybook-fingerprint-manager"
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

# ── Version and source ────────────────────────────────────────────────────────
# VERSION: this release of fingerprint-fix-sdcp.
# DRIVER:  the libfprint-egismoc-sdcp commit it is tested with. That exact
#          commit is built from our fork of abdallah-alkanani/libfprint-egismoc-sdcp,
#          so syncing the fork changes nothing until a release names a new commit.
#
#   sudo SDCP_COMMIT=latest bash install.sh      the fork's newest commit instead
#   sudo SDCP_COMMIT=<full commit id> bash install.sh
#   sudo SDCP_REPO_URL=https://github.com/abdallah-alkanani/libfprint-egismoc-sdcp.git bash install.sh
#        Abdallah's newest commit — test it BEFORE syncing the fork
FIX_VERSION=$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION" 2>/dev/null)
[[ "$FIX_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || { echo "ERROR: VERSION is missing — run install.sh from the complete fingerprint-fix-sdcp folder."; exit 1; }
DEFAULT_SDCP_REPO_URL="https://github.com/david-bartlett/libfprint-egismoc-sdcp.git"
SDCP_REPO_URL="${SDCP_REPO_URL:-$DEFAULT_SDCP_REPO_URL}"
SDCP_BRANCH="egismoc-sdcp"
[[ "$SDCP_REPO_URL" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$ ]] \
    || { echo "ERROR: SDCP_REPO_URL must be an https://github.com/OWNER/REPO URL."; exit 1; }
DRIVER_COMMIT=$(grep -v '^#' "$SCRIPT_DIR/DRIVER" 2>/dev/null | tr -d '[:space:]')
[[ "$DRIVER_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
    || { echo "ERROR: DRIVER is missing or not a full commit id — run install.sh from the complete fingerprint-fix-sdcp folder."; exit 1; }
# Which commit to build: the tested one, unless asked otherwise. Testing
# another repository (SDCP_REPO_URL) builds its newest commit.
if [[ -n "${SDCP_COMMIT:-}" ]]; then
    WANT_COMMIT="$SDCP_COMMIT"
elif [[ "$SDCP_REPO_URL" != "$DEFAULT_SDCP_REPO_URL" ]]; then
    WANT_COMMIT="latest"
else
    WANT_COMMIT="$DRIVER_COMMIT"
fi
[[ "$WANT_COMMIT" == "latest" || "$WANT_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
    || { echo "ERROR: SDCP_COMMIT must be 'latest' or a full 40-character commit id."; exit 1; }

# ── Paths ─────────────────────────────────────────────────────────────────────
# All of them are in lib/fixpaths.sh, shared with the packages (which use
# /usr instead of /usr/local and /etc).
# shellcheck source=lib/fixpaths.sh
. "$SCRIPT_DIR/lib/fixpaths.sh"
fix_layout local
FPRINT_BUILD_DIR="/tmp/libfprint-egismoc-sdcp"

# Scripts and units come from packaging/files/, filled in with these paths.
render() { bash "$SCRIPT_DIR/packaging/render.sh" local "$1"; }

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
# The same rule as the packages' pre-install scripts: a Samsung (sys_vendor or
# board_vendor), with the Egis reader 1c7a:05a5 / 05a1 (checked in Step 1).
check_hardware() {
    local _vendor
    # 64-bit Intel/AMD only: not ARM, e.g. the Snapdragon Galaxy Book4 Edge.
    if [[ "$(uname -m)" != x86_64 && "${FPRINT_SDCP_FORCE:-0}" != 1 ]]; then
        echo "Unsupported processor: $(uname -m) — fingerprint-fix-sdcp is only for 64-bit Intel/AMD (x86_64) Galaxy Book4 and Book5 laptops"
        return 1
    fi
    _vendor=$(cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/board_vendor 2>/dev/null)
    if ! grep -qi "samsung" <<< "$_vendor"; then
        echo "Unsupported hardware: vendor is '$(head -1 <<< "${_vendor:-unknown}")' — this script is for Samsung Galaxy Book laptops only"
        return 1
    fi
    # Galaxy Book3: can have the same 1c7a:05a1 reader as the Book4, but this
    # fix is only tested on the Book4 and Book5. Same rule as the packages:
    # the family name, or the model code's generation letter after X (laptop)
    # or Q (360) — F = Book3, G = Book4, H = Book5. FPRINT_SDCP_FORCE=1 overrides.
    local _family _model
    _family=$(cat /sys/class/dmi/id/product_family 2>/dev/null)
    _model=$(cat /sys/class/dmi/id/product_name 2>/dev/null)
    if [[ "${FPRINT_SDCP_FORCE:-0}" != 1 ]] \
            && { grep -Eqi 'galaxy ?book ?3($|[^0-9])' <<< "$_family" || grep -Eqi '^(NP)?[0-9]{3}[XQ]F' <<< "$_model"; }; then
        echo "This is a Galaxy Book3 (${_family:-model $_model}). fingerprint-fix-sdcp is only tested on"
        echo "the Galaxy Book4 and Book5, so it isn't installed here. To install anyway:"
        echo "  sudo FPRINT_SDCP_FORCE=1 bash install.sh"
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

# ── Install ───────────────────────────────────────────────────────────────────
detect_distro
check_hardware || exit 1

SENSOR_ON_BUS=$(lsusb 2>/dev/null | grep -iE "1c7a:05a5|1c7a:05a1" || true)

echo
echo "╔════════════════════════════════════════════════════════════╗"
if ! $WANT_MGR; then
echo "║  Installing: Fingerprint Fix (egismoc SDCP driver only)    ║"
elif ! $WANT_DRIVER; then
echo "║  Installing: Galaxy Book Fingerprint Manager only          ║"
else
echo "║       Installing: Fingerprint Fix (egismoc SDCP driver)    ║"
fi
echo "╚════════════════════════════════════════════════════════════╝"
info "fingerprint-fix-sdcp ${FIX_VERSION} — driver commit ${DRIVER_COMMIT:0:12}"

# ── Step 1: Check sensor is present ──────────────────────────────────────────
step "Fingerprint Step 1: Checking sensor is present"
[[ -z "$SENSOR_ON_BUS" ]] && \
    error "EgisTec SDCP fingerprint sensor not found on USB bus.\nExpected: 1c7a:05a5 (Galaxy Book4 / Book5) or 1c7a:05a1 (Galaxy Book4)\nRun 'lsusb' to check what USB devices are present."
info "✓ Sensor found: $SENSOR_ON_BUS"

# ── Step 2: Install dependencies ─────────────────────────────────────────────
step "Fingerprint Step 2: Installing dependencies"
# Build tools only for the driver (the Manager is Python and shell).
if [[ "$DISTRO" == "fedora" ]]; then
    # shellcheck disable=SC2046
    dnf install -y $($WANT_DRIVER && echo \
        git gcc gcc-c++ meson ninja-build pkgconf-pkg-config \
        glib2-devel libgusb-devel cairo-devel openssl-devel systemd-devel) \
        fprintd fprintd-pam libfprint libnotify python3-gobject \
        || error "Failed to install dependencies via dnf.\n  Check your internet connection and that Fedora repos are reachable (dnf repolist)."
elif [[ "$DISTRO" == "arch" ]]; then
    # shellcheck disable=SC2046
    pacman -S --noconfirm --needed $($WANT_DRIVER && echo \
        git base-devel meson ninja pkgconf \
        glib2 glib2-devel libgusb cairo openssl) systemd \
        fprintd libfprint libnotify python-gobject \
        || error "Failed to install dependencies via pacman.\n  Check your internet connection and that Arch repos are reachable (pacman -Sy)."
else
    apt-get update -q \
        || error "apt-get update failed.\n  Check your internet connection and that the repos are reachable."
    # shellcheck disable=SC2046
    apt-get install -y $($WANT_DRIVER && echo \
        git build-essential meson ninja-build pkg-config \
        libglib2.0-dev libgusb-dev libcairo2-dev libssl-dev systemd-dev) \
        fprintd libfprint-2-2 libpam-fprintd libnotify-bin python3-gi gir1.2-fprint-2.0 \
        || error "Failed to install dependencies via apt-get.\n  Check your internet connection and that the repos are reachable."
fi
info "Dependencies installed"

if $WANT_DRIVER; then
# ── Step 3: Check if the distro libfprint already supports our sensor ─────────
step "Fingerprint Step 3: Checking if the distro libfprint already supports the sensor"
# Skipped on a reinstall (our drop-in is active). Only an SDCP driver counts:
# the distro's older egismoc driver also claims 1c7a:05a1, but without SDCP it
# can't keep prints on these readers.
if [[ -f "$FPRINT_DROPIN" || "${FORCE:-0}" == "1" ]]; then
    info "Skipped (reinstall or FORCE=1)"
else
    # Its exit code is part of its answer (non-zero for anything but sdcp):
    # "|| true" keeps set -e from ending the install here.
    _check=$(env -u LD_LIBRARY_PATH python3 "$SCRIPT_DIR/lib/distro-driver-check.py" 2>/dev/null) || true
    _detail=$(sed -n 2p <<< "$_check")
    case "$(head -n1 <<< "$_check")" in
        sdcp)
            info "✓ The distro libfprint already has an SDCP driver for this sensor."
            info "  This fix is probably not needed. If fingerprint login still does not"
            info "  work, install it anyway with:  sudo FORCE=1 bash install.sh"
            exit 0 ;;
        modified|foreign)
            info "An SDCP libfprint from outside your distro is installed (${_detail})."
            info "  Installing this fix anyway: fprintd will use its driver, which distro"
            info "  updates can't replace — proceeding with the fix" ;;
        plain) info "Distro libfprint handles the sensor without SDCP — proceeding with the fix" ;;
        none)  info "Distro libfprint has no driver for the sensor — proceeding with the fix" ;;
        *)     warn "Could not check the distro libfprint — proceeding with the fix" ;;
    esac
fi

# ── Step 4: Fetch the source ──────────────────────────────────────────────────
step "Fingerprint Step 4: Fetching libfprint-egismoc-sdcp ($SDCP_BRANCH)"
info "From: $SDCP_REPO_URL"
rm -rf "$FPRINT_BUILD_DIR"
mkdir -p "$FPRINT_BUILD_DIR"
git -C "$FPRINT_BUILD_DIR" init -q
git -C "$FPRINT_BUILD_DIR" remote add origin "$SDCP_REPO_URL"
if [[ "$WANT_COMMIT" == "latest" ]]; then
    info "Building the newest commit of ${SDCP_BRANCH} (not the one this release is tested with)"
    git -C "$FPRINT_BUILD_DIR" fetch -q --depth 1 origin "$SDCP_BRANCH" \
        || error "Could not fetch branch ${SDCP_BRANCH} from:\n  ${SDCP_REPO_URL}\n  Check your internet connection and that the repository still exists."
else
    # GitHub serves a single commit by its id; if not, look for it in the branch.
    git -C "$FPRINT_BUILD_DIR" fetch -q --depth 1 origin "$WANT_COMMIT" 2>/dev/null \
        || git -C "$FPRINT_BUILD_DIR" fetch -q --depth 500 origin "$SDCP_BRANCH" \
        || error "Could not fetch from:\n  ${SDCP_REPO_URL}\n  Check your internet connection and that the repository still exists."
    git -C "$FPRINT_BUILD_DIR" cat-file -e "${WANT_COMMIT}^{commit}" 2>/dev/null \
        || error "Commit ${WANT_COMMIT:0:12} is not in ${SDCP_REPO_URL}.\n  Sync the fork on GitHub, or check the commit in the DRIVER file."
fi
git -C "$FPRINT_BUILD_DIR" checkout -q "$([[ "$WANT_COMMIT" == latest ]] && echo FETCH_HEAD || echo "$WANT_COMMIT")"
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

# ── Step 5: Build only the egismoc driver ─────────────────────────────────────
step "Fingerprint Step 5: Building libfprint (egismoc driver only)"
cd "$FPRINT_BUILD_DIR"
meson setup build --buildtype=release \
    -Ddrivers=egismoc -Dtod=false -Ddoc=false -Dgtk-examples=false \
    -Dintrospection=false -Dinstalled-tests=false \
    || error "meson setup failed"
meson compile -C build || error "Build failed"
[[ -f build/libfprint/libfprint-2.so.2.0.0 ]] || error "Build finished but libfprint-2.so.2.0.0 was not produced"
info "Build complete"

# ── Step 6: Install the library and the fprintd drop-in ───────────────────────
step "Fingerprint Step 6: Installing the library for fprintd only"
# Another fix's fprintd setup (e.g. a manual install of Abdallah's
# libfprint-egismoc-sdcp, which uses the same folder as this copy): moved
# aside first, so this install can't overwrite it and uninstall.sh can't delete it.
bash "$SCRIPT_DIR/lib/other-fix.sh" takeover
install -Dm755 build/libfprint/libfprint-2.so.2.0.0 "$FPRINT_LIB"
# Before 2.0.0 the Manager and a compiled sensor check lived in this folder:
# the Manager has its own folder now (Step 13), the check is Python.
rm -rf "$FPRINT_LIB_DIR/manager" "$FPRINT_LIB_DIR/sensor-check"
command -v restorecon >/dev/null 2>&1 && restorecon -R "$FPRINT_LIB_DIR" 2>/dev/null || true
cd /
rm -rf "$FPRINT_BUILD_DIR"
# The drop-in runs this each time fprintd starts: it points fprintd at the
# library only while the Galaxy Book's reader is present.
render fprintd-env.sh.in > "$FPRINT_ENV_SCRIPT"
install -m755 -o root -g root "$SCRIPT_DIR/lib/other-fix.sh" "$FPRINT_OTHER_FIX"
chown root:root "$FPRINT_ENV_SCRIPT"; chmod 755 "$FPRINT_ENV_SCRIPT"
command -v restorecon >/dev/null 2>&1 && restorecon "$FPRINT_ENV_SCRIPT" 2>/dev/null || true
mkdir -p "$FPRINT_DROPIN_DIR"
render dropin.conf.in > "$FPRINT_DROPIN"
chmod 644 "$FPRINT_DROPIN"
systemctl daemon-reload
systemctl restart fprintd 2>/dev/null || true
info "✓ Library installed to $FPRINT_LIB_DIR (distro libfprint untouched)"

# ── Step 7: Confirm fprintd loaded our library ────────────────────────────────
step "Fingerprint Step 7: Checking fprintd uses the new driver"
if check_fprintd_functional \
        && grep -q "$FPRINT_LIB_DIR" "/proc/$(pidof fprintd 2>/dev/null | awk '{print $1}')/maps" 2>/dev/null; then
    info "✓ fprintd is running with the egismoc SDCP driver and sees the sensor"
else
    warn "Could not confirm fprintd loaded $FPRINT_LIB.\n       Check with: fprintd-list \"\$USER\"; sudo grep libfprint /proc/\$(pidof fprintd)/maps"
fi

fi   # WANT_DRIVER (Steps 3–7)

# ── Step 8: Record state ──────────────────────────────────────────────────────
step "Fingerprint Step 8: Recording installed state"
# Already installed before (this run updates it): fingerprint login is left
# as it was set (Step 11).
_UPDATING=false
[[ -f "$FPRINT_MARKER" || -f "$MGR_MARKER" ]] && _UPDATING=true
mkdir -p "$FPRINT_STATE_DIR"
SYSLIB=$(system_libfprint)
if [[ -n "$SYSLIB" ]]; then
    sha256sum "$SYSLIB" | awk '{print $1}' > "$FPRINT_SYSLIB_HASH"
    chmod 644 "$FPRINT_SYSLIB_HASH"
fi
$WANT_DRIVER && echo "${SDCP_COMMIT:0:12} ${SDCP_DATE} ${SDCP_SOURCE}${SDCP_FIXES[*]:+ +${SDCP_FIXES[*]}} (installed $(date '+%Y-%m-%d')) fingerprint-fix-sdcp ${FIX_VERSION}" > "$FPRINT_MARKER"
# The Manager's own marker: it, its monitor and its checks are installed.
$WANT_MGR && echo "(installed $(date '+%Y-%m-%d')) galaxybook-fingerprint-manager ${FIX_VERSION}" > "$MGR_MARKER"
info "✓ Markers and distro libfprint hash stored"

# The desktop user: user timers go into their ~/.config/systemd/user.
FPRINT_USER=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$4 == "seat0" {print $3}' | head -1)
FPRINT_USER_ID=$(id -u "$FPRINT_USER" 2>/dev/null || true)
FPRINT_USER_SYSTEMD_DIR="/home/${FPRINT_USER}/.config/systemd/user"

_fp_user_systemctl() {
    sudo -u "$FPRINT_USER" \
        XDG_RUNTIME_DIR="/run/user/${FPRINT_USER_ID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${FPRINT_USER_ID}/bus" \
        systemctl --user "$@"
}

# A user timer (and its service) from packaging/files, for the desktop user.
_fp_user_timer() {   # service-template timer-template service-name timer-name
    [[ -n "$FPRINT_USER" && -n "$FPRINT_USER_ID" ]] || return 1
    mkdir -p "$FPRINT_USER_SYSTEMD_DIR"
    render "$1" > "${FPRINT_USER_SYSTEMD_DIR}/$3"
    render "$2" > "${FPRINT_USER_SYSTEMD_DIR}/$4"
    chown -R "${FPRINT_USER}:${FPRINT_USER}" "$FPRINT_USER_SYSTEMD_DIR"
    _fp_user_systemctl daemon-reload 2>/dev/null || true
    _fp_user_systemctl enable "$4" >/dev/null 2>&1
}

# The driver's hourly check for new releases (skipped while the Manager is
# installed, which has its own).
if $WANT_DRIVER; then
    install -d -m 755 "$FIX_UPDATE_DIR"
    install -m 755 "$SCRIPT_DIR/lib/update_check.py" "$SCRIPT_DIR/lib/notify-update.sh" "$FIX_UPDATE_DIR/"
    install -m 644 "$SCRIPT_DIR/VERSION" "$FPRINT_LIB_DIR/VERSION"
    _fp_user_timer fix-update-check.service.in fix-update-check.timer.in "$FIX_UPDATE_SVC" "$FIX_UPDATE_TIMER" \
        && info "✓ Hourly check for new releases enabled" \
        || warn "Could not set up the hourly check for new releases (no desktop user found)"
fi

# ── Step 9: Monitor — cleanup helper, scripts, polkit rule, services ─────────
step "Fingerprint Step 9: Installing the fingerprint monitor$($WANT_MGR || echo ' — skipped (driver only)')"

# Cleanup helpers, used when a package replaces this copy: the driver's (also
# the Manager's "Remove the driver") and the Manager's. Both keep fingerprints;
# PAM fingerprint auth is left enabled.
if $WANT_DRIVER; then
    render cleanup.sh.in > "$FPRINT_CLEANUP"
    chown root:root "$FPRINT_CLEANUP"
    chmod 750 "$FPRINT_CLEANUP"
fi
if $WANT_MGR; then
render mgr-cleanup.sh.in > "$MGR_CLEANUP"
chown root:root "$MGR_CLEANUP"
chmod 750 "$MGR_CLEANUP"

# System monitor — runs as root when the user check script starts it.
render monitor.sh.in > "$FPRINT_CHECK_SCRIPT"
chown root:root "$FPRINT_CHECK_SCRIPT"; chmod 755 "$FPRINT_CHECK_SCRIPT"

# User check script — run by a user timer 10s after login.
render user-check.sh.in > "$FPRINT_USER_CHECK_SCRIPT"
chown root:root "$FPRINT_USER_CHECK_SCRIPT"; chmod 755 "$FPRINT_USER_CHECK_SCRIPT"

render polkit-monitor.rules.in > "$FPRINT_POLKIT_RULE"
chmod 644 "$FPRINT_POLKIT_RULE"

render monitor.service.in > "${FPRINT_UNIT_DIR}/${FPRINT_MONITOR_SVC}"
systemctl daemon-reload
info "✓ Monitor service and polkit rule installed"

# Boot-time sensor check — runs before fprintd, so it has the sensor to itself.
# Its result is written to FPRINT_BOOT_STATUS and shown by the login check.
render boot-check.sh.in > "$FPRINT_BOOT_CHECK_SCRIPT"
chown root:root "$FPRINT_BOOT_CHECK_SCRIPT"; chmod 755 "$FPRINT_BOOT_CHECK_SCRIPT"

render boot-check.service.in > "${FPRINT_UNIT_DIR}/${FPRINT_BOOT_CHECK_SVC}"
systemctl daemon-reload
systemctl enable "$FPRINT_BOOT_CHECK_SVC" >/dev/null 2>&1 \
    && info "✓ Boot-time sensor check enabled" \
    || warn "Could not enable ${FPRINT_BOOT_CHECK_SVC}"

if [[ -z "$FPRINT_USER" || -z "$FPRINT_USER_ID" ]]; then
    warn "Could not detect logged-in user — skipping user monitor timer install"
else
    mkdir -p "$FPRINT_USER_SYSTEMD_DIR"
    render user-check.service.in > "${FPRINT_USER_SYSTEMD_DIR}/${FPRINT_USER_CHECK_SVC}"
    render user-check.timer.in > "${FPRINT_USER_SYSTEMD_DIR}/${FPRINT_USER_CHECK_TIMER}"
    chown -R "${FPRINT_USER}:${FPRINT_USER}" "$FPRINT_USER_SYSTEMD_DIR"
    _fp_user_systemctl daemon-reload 2>/dev/null || true
    _fp_user_systemctl enable "${FPRINT_USER_CHECK_TIMER}" \
        && info "✓ User timer enabled for $FPRINT_USER" \
        || warn "systemctl --user enable failed for ${FPRINT_USER_CHECK_TIMER}"
    _fp_user_timer mgr-update-check.service.in mgr-update-check.timer.in "$MGR_UPDATE_SVC" "$MGR_UPDATE_TIMER" \
        && info "✓ Hourly check for new releases enabled" \
        || warn "systemctl --user enable failed for ${MGR_UPDATE_TIMER}"
fi

# ── Step 10: Graphical session helper (Xfce and other desktops) ───────────────
step "Fingerprint Step 10: Checking the desktop starts graphical-session.target"
# Shared with other Galaxy Book fixes; each registers a marker and the last one
# uninstalled removes it (same helper as fingerprint-fix and webcam-toggle).
SESSION_HELPER_USERS="/etc/samsung-galaxybook/session-helper.d"

install_session_helper() {
    render session.target.in > "$SESSION_HELPER_TARGET"
    chmod 644 "$SESSION_HELPER_TARGET"

    render session-start.sh.in > "$SESSION_HELPER_SCRIPT"
    chmod 755 "$SESSION_HELPER_SCRIPT"

    mkdir -p "$(dirname "$SESSION_HELPER_AUTOSTART")"
    render session-autostart.desktop.in > "$SESSION_HELPER_AUTOSTART"
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
fi   # WANT_MGR (Steps 9–10)

# ── Step 11: Enable fingerprint authentication ────────────────────────────────
step "Fingerprint Step 11: Enabling fingerprint authentication"
# fingerprint-pam.sh does it the way each distro expects (authselect on
# Fedora, pam-auth-update on Ubuntu/Debian/MX, Mint's fingwit profile on Mint,
# arch-pam.sh on Arch); the Fingerprint Manager uses the same script.
# Like the packages, only once per computer (the first install, by either):
# after that the choice made in the Galaxy Book Fingerprint Manager stays,
# so running install.sh again to update doesn't turn it back on.
# FPRINT_PAM=0 leaves it off.
_PAM_DONE=/var/lib/samsung-galaxybook/fingerprint-login-set-up
if [[ "$DISTRO" != "arch" ]]; then
    if [[ "${FPRINT_PAM:-1}" == 0 ]]; then
        info "FPRINT_PAM=0 — fingerprint login not turned on. To turn it on later: the Galaxy Book Fingerprint Manager, or sudo bash $SCRIPT_DIR/tools/fingerprint-pam.sh enable"
    elif [[ -e "$_PAM_DONE" ]] || $_UPDATING; then
        info "Fingerprint login left as it was set (on or off) — change it in the Galaxy Book Fingerprint Manager"
    else
        bash "$SCRIPT_DIR/tools/fingerprint-pam.sh" enable \
            || warn "Could not enable fingerprint authentication — try: sudo bash $SCRIPT_DIR/tools/fingerprint-pam.sh enable"
    fi
    mkdir -p "$(dirname "$_PAM_DONE")" && touch "$_PAM_DONE"
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
    mkdir -p "$(dirname "$_PAM_DONE")" && touch "$_PAM_DONE"
fi

# ── Step 12: Import fingerprints exported from another install ───────────────
# ~/fingerprint-export.tgz (where export-fingerprint.sh writes it) is imported
# automatically — import-fingerprint.sh first checks its fingerprints are
# still on the sensor. Without it, the user is asked [y/N] (30s, then skip)
# and, only if they say yes, for the path (no timeout).
# FPRINT_IMPORT=FILE imports a file kept anywhere else without asking.
step "Fingerprint Step 12: Importing fingerprints from another install (optional)"
_imp_user="${FPRINT_USER:-${SUDO_USER:-}}"
# Importing needs an SDCP driver: this fix's, or the distro's own.
if ! $WANT_DRIVER && ! fix_installed \
        && [[ "$(env -u LD_LIBRARY_PATH python3 "$SCRIPT_DIR/lib/distro-driver-check.py" 2>/dev/null | head -n1)" != sdcp ]]; then
    info "No SDCP driver here (Manager only) — skipping import"
    _imp_user=""
    _imp_skip=1
fi
_imp_home=""
[[ -n "$_imp_user" ]] && _imp_home=$(getent passwd "$_imp_user" | cut -d: -f6)
_imp_file="${FPRINT_IMPORT:-}"
if [[ -n "${_imp_skip:-}" ]]; then
    :
elif [[ -z "$_imp_user" ]]; then
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

# ── Step 13: Galaxy Book Fingerprint Manager ──────────────────────────────────
# A root-owned copy of the Manager (window + helper + tools + boot check), so
# the helper that pkexec runs as root can't be changed by anything running as
# the user. It has its own folder (MGR_DIR), apart from the driver's, so the
# driver can be removed alone (uninstall.sh --driver-only) once the distro's
# libfprint has SDCP. Its GUI packages are installed here, separately: if they
# fail, the fix itself is still fine.
if $WANT_MGR; then
step "Fingerprint Step 13: Installing the Galaxy Book Fingerprint Manager"
case "$DISTRO" in
    fedora) dnf install -y python3-gobject python3-cairo gtk3 polkit ;;
    arch)   pacman -S --noconfirm --needed python-gobject python-cairo gtk3 polkit ;;
    *)      apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-fprint-2.0 pkexec ;;
esac >/dev/null 2>&1 \
    || warn "Could not install the Fingerprint Manager's packages — it will list what it needs when started."

rm -rf "$MGR_DIR"
install -d -m 755 -o root -g root "$MGR_DIR" "$MGR_DIR/lib" "$MGR_DIR/tools"
install -m 755 -o root -g root "$SCRIPT_DIR/fingerprint-manager.sh" "$MGR_DIR/"
install -m 644 -o root -g root "$SCRIPT_DIR/VERSION" "$MGR_DIR/"
install -m 755 -o root -g root "$SCRIPT_DIR/lib/fingerprint-manager.py" \
    "$SCRIPT_DIR/lib/fingerprint-manager-helper.py" "$SCRIPT_DIR/lib/shared_slots.py" "$MGR_DIR/lib/"
install -m 644 -o root -g root "$SCRIPT_DIR/lib/fixpaths.sh" "$MGR_DIR/lib/"
install -m 755 -o root -g root "$SCRIPT_DIR/lib/update_check.py" "$SCRIPT_DIR/lib/notify-open-manager.sh" \
    "$SCRIPT_DIR/lib/notify-update.sh" "$SCRIPT_DIR/lib/terminal.py" "$SCRIPT_DIR/lib/update-in-terminal.sh" \
    "$SCRIPT_DIR/lib/distro-driver-check.py" "$SCRIPT_DIR/lib/sensor-check.py" "$MGR_DIR/lib/"
install -m 755 -o root -g root "$SCRIPT_DIR"/tools/*.sh "$MGR_DIR/tools/"
mkdir -p "$(dirname "$MGR_BIN")"
ln -sfn "$MGR_DIR/fingerprint-manager.sh" "$MGR_BIN"
install -Dm 644 "$SCRIPT_DIR/lib/${MGR_ID}.svg" "$MGR_ICON"

mkdir -p "$(dirname "$MGR_DESKTOP")"
render manager.desktop.in > "$MGR_DESKTOP"
chmod 644 "$MGR_DESKTOP"

# polkit: the password prompt names this app instead of "run /usr/bin/python3".
# It only applies to the installed helper's exact path.
mkdir -p "$(dirname "$MGR_POLICY")"
render manager.policy.in > "$MGR_POLICY"
chmod 644 "$MGR_POLICY"

command -v restorecon >/dev/null 2>&1 \
    && restorecon -R "$MGR_DIR" "$MGR_BIN" "$MGR_DESKTOP" "$MGR_ICON" "$MGR_POLICY" 2>/dev/null || true
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
info "✓ Galaxy Book Fingerprint Manager installed (app menu, or: ${MGR_ID})"
fi   # WANT_MGR (Step 13)

# ── Done ──────────────────────────────────────────────────────────────────────
info "✓ fingerprint-fix-sdcp ${FIX_VERSION} installed ($($WANT_DRIVER && $WANT_MGR && echo "driver and Fingerprint Manager" || { $WANT_DRIVER && echo "driver only" || echo "Fingerprint Manager only"; })) — no reboot required"
if $WANT_DRIVER; then
info "Built from: $SDCP_REPO_URL"
info "            branch $SDCP_BRANCH, commit ${SDCP_COMMIT:0:12} (${SDCP_DATE})"
[[ "$SDCP_COMMIT" == "$DRIVER_COMMIT" ]] \
    || warn "This is not the driver commit ${FIX_VERSION} is tested with (${DRIVER_COMMIT:0:12}).\n       Run the installer again without SDCP_COMMIT / SDCP_REPO_URL to go back."
[[ ${#SDCP_FIXES[@]} -gt 0 ]] && info "            with fixes from lib/patches: ${SDCP_FIXES[*]}"
[[ "$SDCP_SOURCE" == "fork" ]] \
    || warn "This is a TEST build (not the usual fork). Run the installer again without\n       SDCP_REPO_URL to go back to the fork's build."
fi
echo
echo "  Existing SDCP enrolments are kept."
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
if $WANT_MGR; then
echo "  Galaxy Book Fingerprint Manager — test, enrol, export/import and more"
echo "  in a window: find it in your app menu, or run (as yourself, not sudo):"
echo "      ${MGR_ID}"
else
echo "  The Galaxy Book Fingerprint Manager (window, monitor, boot and login"
echo "  checks) can be added any time:  sudo bash install.sh --manager-only"
fi
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
