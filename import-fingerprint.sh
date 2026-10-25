#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Import fingerprints
# =============================================================================
# Loads fingerprint records exported by export-fingerprint.sh on another Linux
# install on THIS laptop, so both installs share the same fingerprints without
# enrolling again.
#
#   sudo bash import-fingerprint.sh ~/fingerprint-export.tgz
#   sudo bash import-fingerprint.sh --user NAME FILE.tgz
#   sudo bash import-fingerprint.sh --no-check FILE.tgz   (skip the sensor check)
#
# The fingerprints are imported for the user running it (or --user NAME). That
# user does not need the same name as on the install they were exported from.
#
# Checks first that the records are for this laptop's sensor and that the user
# has nothing enrolled (records are never overwritten — that would orphan
# templates on the sensor).
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run with sudo: sudo bash import-fingerprint.sh FILE.tgz"
    exit 1
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

FINGERS=(unknown left-thumb left-index-finger left-middle-finger left-ring-finger
         left-little-finger right-thumb right-index-finger right-middle-finger
         right-ring-finger right-little-finger)

# Built by install.sh; rewrites the owner stored inside a record.
SENSOR_CHECK="/usr/local/lib/libfprint-egismoc-sdcp/sensor-check"

# libfprint's device ID for this sensor is its USB serial number.
sensor_serial() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "1c7a" ]] || continue
        [[ "$(cat "$d/idProduct" 2>/dev/null)" =~ ^05a[15]$ ]] || continue
        cat "$d/serial" 2>/dev/null && return 0
    done
    return 1
}

# ── Arguments ─────────────────────────────────────────────────────────────────
TARGET_USER=""
ARCHIVE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user) TARGET_USER="${2:-}"; shift 2 || error "--user needs a name" ;;
        --no-check) NO_CHECK=1; shift ;;
        -*)     error "Unknown option: $1" ;;
        *)      ARCHIVE="$1"; shift ;;
    esac
done
[[ -n "$ARCHIVE" ]] || error "Usage: sudo bash import-fingerprint.sh [--user NAME] FILE.tgz"
[[ -f "$ARCHIVE" ]] || error "File not found: $ARCHIVE"

TARGET_USER="${TARGET_USER:-${SUDO_USER:-}}"
[[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]] \
    || error "Run this with sudo from the account to import into, or use --user NAME."
[[ "$TARGET_USER" =~ ^[a-z_][a-z0-9_.-]*$ ]] || error "Invalid username: $TARGET_USER"
getent passwd "$TARGET_USER" >/dev/null || error "User '$TARGET_USER' does not exist on this install."

# ── The fix must be installed — the distro libfprint cannot use SDCP records ──
[[ -f /etc/samsung-galaxybook-egismoc-sdcp.installed ]] \
    || error "fingerprint-fix-sdcp is not installed here. Install it first:\n  sudo bash install.sh"

SERIAL=$(sensor_serial) || error "EgisTec fingerprint sensor (1c7a:05a5 / 1c7a:05a1) not found."

# ── Check the archive: only <user>/egismoc/<serial>/<finger> files and dirs ───
tar -tzf "$ARCHIVE" >/dev/null 2>&1 || error "Not a valid .tgz archive: $ARCHIVE"
SRC_USER=""
while read -r perms _ _ _ _ path; do
    path="${path%/}"
    case "${perms:0:1}" in
        d|-) ;;
        *) error "Archive contains something other than files and folders: $path" ;;
    esac
    [[ "$path" =~ ^([a-z_][a-z0-9_.-]*)(/egismoc(/([A-Za-z0-9._-]+)(/([0-9]+))?)?)?$ ]] \
        || error "Unexpected path in archive: $path"
    u="${BASH_REMATCH[1]}"; s="${BASH_REMATCH[4]}"; f="${BASH_REMATCH[6]}"
    [[ -z "$SRC_USER" || "$SRC_USER" == "$u" ]] || error "Archive contains records for more than one user."
    SRC_USER="$u"
    [[ -z "$s" || "$s" == "$SERIAL" ]] \
        || error "These records are for a different fingerprint sensor ($s).\n  This laptop's sensor is $SERIAL — records only work on the sensor they were made on."
    if [[ -n "$f" ]]; then
        [[ "${perms:0:1}" == "-" && "$f" -ge 1 && "$f" -le 10 ]] || error "Unexpected entry in archive: $path"
    fi
done < <(tar -tzvf "$ARCHIVE" 2>/dev/null)
[[ -n "$SRC_USER" ]] || error "Archive is empty: $ARCHIVE"

# Records exported by another username need their owner rewritten.
if [[ "$SRC_USER" != "$TARGET_USER" && ! -x "$SENSOR_CHECK" ]]; then
    error "These fingerprints were exported by '$SRC_USER'. Importing them for '$TARGET_USER'\n  needs $SENSOR_CHECK, which is missing.\n  Reinstall the fix (sudo bash install.sh) and try again."
fi

# ── Never overwrite existing records ──────────────────────────────────────────
DEST="/var/lib/fprint/${TARGET_USER}"
if [[ -d "$DEST" ]] && [[ -n "$(find "$DEST" -type f 2>/dev/null | head -1)" ]]; then
    error "${TARGET_USER} already has fingerprints enrolled on this install — not importing.\n  Overwriting them would leave their templates orphaned on the sensor.\n  To replace them: fprintd-delete ${TARGET_USER}, then run this again."
fi

# ── Extract to a temporary folder, then install with fprintd's permissions ────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
tar -C "$TMP" --no-same-owner --no-same-permissions -xzf "$ARCHIVE"
SRC="$TMP/${SRC_USER}/egismoc/${SERIAL}"
shopt -s nullglob
FILES=("$SRC"/*)
shopt -u nullglob
[[ ${#FILES[@]} -gt 0 ]] || error "Archive contains no fingerprint records."

# Prepare every record first, so a failure leaves nothing half-imported.
mkdir -p "$TMP/ready"
for f in "${FILES[@]}"; do
    n=$(basename "$f")
    if [[ "$SRC_USER" == "$TARGET_USER" ]]; then
        cp "$f" "$TMP/ready/$n"
    else
        "$SENSOR_CHECK" --set-owner "$TARGET_USER" "$f" "$TMP/ready/$n" \
            || error "Could not convert record $n for $TARGET_USER — nothing was imported."
    fi
done

# ── Are these fingerprints still on the sensor? ───────────────────────────────
# An old export (made before re-enrolling, or before Windows wiped the sensor)
# points at templates that no longer exist and would never match. Check with
# the sensor before importing. fprintd is stopped briefly so the check has the
# sensor to itself. --no-check skips this.
if [[ "${NO_CHECK:-0}" != "1" ]]; then
    if [[ -x "$SENSOR_CHECK" ]]; then
        mkdir -p "$TMP/store/$TARGET_USER/egismoc/$SERIAL"
        cp "$TMP/ready"/* "$TMP/store/$TARGET_USER/egismoc/$SERIAL/"
        systemctl stop fprintd 2>/dev/null || true
        set +e
        CHECK_OUT=$(FPRINT_STORE="$TMP/store" timeout 15 "$SENSOR_CHECK" 2>&1); CHECK_RC=$?
        set -e
        case $CHECK_RC in
            0) info "✓ These fingerprints are still stored on the sensor" ;;
            1) systemctl start fprintd 2>/dev/null || true
               error "This export is out of date — its fingerprints are no longer stored on the sensor\n  (re-enrolled since, or removed by Windows). Nothing was imported.\n  Enrol instead (fprintd-enroll), or export again on the install where they work." ;;
            *) warn "Could not check the sensor (${CHECK_OUT##*$'\n'}) — importing anyway." ;;
        esac
    else
        warn "Cannot check the sensor ($SENSOR_CHECK missing) — importing without checking."
    fi
fi

mkdir -p /var/lib/fprint
install -d -m 700 -o root -g root "$DEST" "$DEST/egismoc" "$DEST/egismoc/$SERIAL"
NAMES=()
for f in "$TMP/ready"/*; do
    n=$(basename "$f")
    install -m 600 -o root -g root "$f" "$DEST/egismoc/$SERIAL/$n"
    NAMES+=("${FINGERS[$n]}")
done
command -v restorecon >/dev/null 2>&1 && restorecon -R "$DEST" 2>/dev/null || true

systemctl restart fprintd 2>/dev/null || true
if [[ "$SRC_USER" == "$TARGET_USER" ]]; then
    info "Imported ${NAMES[*]} for ${TARGET_USER}"
else
    info "Imported ${NAMES[*]} for ${TARGET_USER} (exported by ${SRC_USER})"
fi
echo
echo "  Check it works (touch the sensor when asked):"
echo "      fprintd-verify ${TARGET_USER}"
echo
echo "  These fingerprints are now shared with the install they came from:"
echo "   • Do NOT enrol the same finger on either install — fprintd would delete"
echo "     the other install's template and break it there."
echo "   • When uninstalling the fix on one install, answer N to deleting"
echo "     fingerprints, or the other install loses them too."
