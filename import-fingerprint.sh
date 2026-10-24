#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Import fingerprints
# =============================================================================
# Loads fingerprint records exported by export-fingerprint.sh on another Linux
# install on THIS laptop, so both installs share the same fingerprints without
# enrolling again.
#
#   sudo bash import-fingerprint.sh ~/fprint-<user>.tgz
#
# Checks first that the records are for this laptop's sensor, that the user
# exists here, and that the user has nothing enrolled (records are never
# overwritten — that would orphan templates on the sensor).
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

ARCHIVE="${1:-}"
[[ -n "$ARCHIVE" ]] || error "Usage: sudo bash import-fingerprint.sh FILE.tgz"
[[ -f "$ARCHIVE" ]] || error "File not found: $ARCHIVE"

# ── The fix must be installed — the distro libfprint cannot use SDCP records ──
[[ -f /etc/samsung-galaxybook-egismoc-sdcp.installed ]] \
    || error "fingerprint-fix-sdcp is not installed here. Install it first:\n  sudo bash install.sh"

SERIAL=$(sensor_serial) || error "EgisTec fingerprint sensor (1c7a:05a5 / 1c7a:05a1) not found."

# ── Check the archive: only <user>/egismoc/<serial>/<finger> files and dirs ───
tar -tzf "$ARCHIVE" >/dev/null 2>&1 || error "Not a valid .tgz archive: $ARCHIVE"
USER_NAME=""
while read -r perms _ _ _ _ path; do
    path="${path%/}"
    case "${perms:0:1}" in
        d|-) ;;
        *) error "Archive contains something other than files and folders: $path" ;;
    esac
    [[ "$path" =~ ^([a-z_][a-z0-9_.-]*)(/egismoc(/([A-Za-z0-9._-]+)(/([0-9]+))?)?)?$ ]] \
        || error "Unexpected path in archive: $path"
    u="${BASH_REMATCH[1]}"; s="${BASH_REMATCH[4]}"; f="${BASH_REMATCH[6]}"
    [[ -z "$USER_NAME" || "$USER_NAME" == "$u" ]] || error "Archive contains records for more than one user."
    USER_NAME="$u"
    [[ -z "$s" || "$s" == "$SERIAL" ]] \
        || error "These records are for a different fingerprint sensor ($s).\n  This laptop's sensor is $SERIAL — records only work on the sensor they were made on."
    if [[ -n "$f" ]]; then
        [[ "${perms:0:1}" == "-" && "$f" -ge 1 && "$f" -le 10 ]] || error "Unexpected entry in archive: $path"
    fi
done < <(tar -tzvf "$ARCHIVE" 2>/dev/null)
[[ -n "$USER_NAME" ]] || error "Archive is empty: $ARCHIVE"

getent passwd "$USER_NAME" >/dev/null \
    || error "The records are for user '$USER_NAME', who does not exist on this install.\n  Records can only be imported for the same username."

# ── Never overwrite existing records ──────────────────────────────────────────
DEST="/var/lib/fprint/${USER_NAME}"
if [[ -d "$DEST" ]] && [[ -n "$(find "$DEST" -type f 2>/dev/null | head -1)" ]]; then
    error "${USER_NAME} already has fingerprints enrolled on this install — not importing.\n  Overwriting them would leave their templates orphaned on the sensor.\n  To replace them: fprintd-delete ${USER_NAME}, then run this again."
fi

# ── Extract to a temporary folder, then install with fprintd's permissions ────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
tar -C "$TMP" --no-same-owner --no-same-permissions -xzf "$ARCHIVE"
SRC="$TMP/${USER_NAME}/egismoc/${SERIAL}"
shopt -s nullglob
FILES=("$SRC"/*)
shopt -u nullglob
[[ ${#FILES[@]} -gt 0 ]] || error "Archive contains no fingerprint records."

mkdir -p /var/lib/fprint
install -d -m 700 -o root -g root "$DEST" "$DEST/egismoc" "$DEST/egismoc/$SERIAL"
NAMES=()
for f in "${FILES[@]}"; do
    n=$(basename "$f")
    install -m 600 -o root -g root "$f" "$DEST/egismoc/$SERIAL/$n"
    NAMES+=("${FINGERS[$n]}")
done
command -v restorecon >/dev/null 2>&1 && restorecon -R "$DEST" 2>/dev/null || true

systemctl restart fprintd 2>/dev/null || true
info "Imported ${NAMES[*]} for ${USER_NAME}"
echo
echo "  Check it works (touch the sensor when asked):"
echo "      fprintd-verify ${USER_NAME}"
echo
echo "  These fingerprints are now shared with the install they came from:"
echo "   • Do NOT enrol the same finger on either install — fprintd would delete"
echo "     the other install's template and break it there."
echo "   • When uninstalling the fix on one install, answer N to deleting"
echo "     fingerprints, or the other install loses them too."
