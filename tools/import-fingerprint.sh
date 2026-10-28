#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Import fingerprints
# =============================================================================
# Loads fingerprint records exported by export-fingerprint.sh on another Linux
# install on THIS laptop, so both installs share the same fingerprints without
# enrolling again.
#
#   sudo bash import-fingerprint.sh                  (uses ~/fingerprint-export.tgz)
#   sudo bash import-fingerprint.sh FILE.tgz
#   sudo bash import-fingerprint.sh --user NAME [FILE.tgz]   (default: NAME's home)
#   sudo bash import-fingerprint.sh --no-check [FILE.tgz]    (skip the sensor check)
#   sudo bash import-fingerprint.sh --fingers 7,1 [FILE.tgz] (only these fingers:
#                       fprintd's numbers, 1-9 and a)
#   sudo bash import-fingerprint.sh --replace [FILE.tgz]     (replace this install's
#                       records; old ones are moved aside, the sensor is not touched)
#   sudo bash import-fingerprint.sh --dead 2,7 [FILE.tgz]    (these records here are
#                       dead — their template is gone from the sensor: replace them)
#
# The fingerprints are imported for the user running it (or --user NAME). That
# user does not need the same name as on the install they were exported from.
#
# Fingers the user already has here are kept, and only the missing ones are
# imported (all of them are replaced with --replace; dead ones named with
# --dead, e.g. by the Fingerprint Manager, count as missing). Checks first that the
# records are for this laptop's sensor and still stored on it: fingers whose
# template is gone are left out.
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run with sudo: sudo bash $0 [FILE.tgz]"
    exit 1
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Where the fix is installed: a package (/usr) or install.sh (/usr/local).
# shellcheck source-path=SCRIPTDIR source=../lib/fixpaths.sh
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../lib/fixpaths.sh" 2>/dev/null \
    || error "lib/fixpaths.sh not found — keep the whole fingerprint-fix-sdcp folder together."
fix_detect

FINGERS=(unknown left-thumb left-index-finger left-middle-finger left-ring-finger
         left-little-finger right-thumb right-index-finger right-middle-finger
         right-ring-finger right-little-finger)

# Built with the fix; rewrites the owner stored inside a record.
SENSOR_CHECK="$FPRINT_SENSOR_CHECK"

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
        --replace)  REPLACE=1; shift ;;
        --dead)     DEAD="${2:-}"; shift 2 || error "--dead needs a list, e.g. --dead 7"
                    [[ -z "$DEAD" || "$DEAD" =~ ^[1-9a](,[1-9a])*$ ]] \
                        || error "--dead takes fprintd's finger numbers 1-9 and a, comma-separated" ;;
        --fingers)  ONLY="${2:-}"; shift 2 || error "--fingers needs a list, e.g. --fingers 7,1"
                    [[ "$ONLY" =~ ^[1-9a](,[1-9a])*$ ]] \
                        || error "--fingers takes fprintd's finger numbers 1-9 and a, comma-separated" ;;
        -*)     error "Unknown option: $1" ;;
        *)      ARCHIVE="$1"; shift ;;
    esac
done
TARGET_USER="${TARGET_USER:-${SUDO_USER:-}}"
[[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]] \
    || error "Run this with sudo from the account to import into, or use --user NAME."
[[ "$TARGET_USER" =~ ^[a-z_][a-z0-9_.-]*$ ]] || error "Invalid username: $TARGET_USER"
getent passwd "$TARGET_USER" >/dev/null || error "User '$TARGET_USER' does not exist on this install."

# No file given: use ~/fingerprint-export.tgz of the user importing, which is
# where export-fingerprint.sh writes it.
if [[ -z "$ARCHIVE" ]]; then
    ARCHIVE="$(getent passwd "$TARGET_USER" | cut -d: -f6)/fingerprint-export.tgz"
    [[ -f "$ARCHIVE" ]] \
        || error "No file given and $ARCHIVE not found.\n  Copy the export there, or give its path:\n  sudo bash $0 /path/to/fingerprint-export.tgz"
    info "Using $ARCHIVE"
fi
[[ -f "$ARCHIVE" ]] || error "File not found: $ARCHIVE"

# ── fprintd, libfprint and this fix must all be in place ──────────────────────
# The distro libfprint cannot use SDCP records, so the fix's library and the
# drop-in that makes fprintd load it are needed too.
command -v fprintd-list >/dev/null 2>&1 && systemctl cat fprintd.service >/dev/null 2>&1 \
    || error "fprintd is not installed. Install the fix first (it installs fprintd):\n  sudo bash install.sh"
ldconfig -p 2>/dev/null | grep -q 'libfprint-2\.so\.2 ' \
    || error "libfprint is not installed. Install the fix first:\n  sudo bash install.sh"
sdcp_available \
    || error "fingerprint-fix-sdcp's driver is not installed (or incomplete) here, and your\n  distro's libfprint has no SDCP driver for the reader. Install fingerprint-fix-sdcp first."

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
    [[ "$path" =~ ^([a-z_][a-z0-9_.-]*)(/egismoc(/([A-Za-z0-9._-]+)(/([1-9a]))?)?)?$ ]] \
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

# ── Existing records: kept, unless --replace ──────────────────────────────────
# Without --replace, fingers the user already has here are left alone and only
# the missing ones are imported. --replace moves this install's records aside
# (it does NOT delete anything on the sensor: other installs may share those
# templates). fprintd-delete would delete the templates too, breaking every
# install that shares them.
DEST="/var/lib/fprint/${TARGET_USER}"
HAS_RECORDS=false
if [[ -d "$DEST" ]] && [[ -n "$(find "$DEST" -type f 2>/dev/null | head -1)" ]]; then
    HAS_RECORDS=true
fi
name_of() { echo "${FINGERS[$((16#$1))]}"; }          # hex: a = right little finger
list_of() { local n out=""; for n in "$@"; do out+="${out:+, }$(name_of "$n")"; done; echo "$out"; }

# ── Extract to a temporary folder, then install with fprintd's permissions ────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
tar -C "$TMP" --no-same-owner --no-same-permissions -xzf "$ARCHIVE"
SRC="$TMP/${SRC_USER}/egismoc/${SERIAL}"
shopt -s nullglob
ALL=("$SRC"/*)
shopt -u nullglob
[[ ${#ALL[@]} -gt 0 ]] || error "Archive contains no fingerprint records."

# Which to import: --fingers narrows it down; fingers already here are kept,
# except dead ones (--dead), which this export replaces.
FILES=(); KEPT=(); SWAP=()
for f in "${ALL[@]}"; do
    n=$(basename "$f")
    [[ -z "${ONLY:-}" || ",$ONLY," == *",$n,"* ]] || continue
    if [[ "${REPLACE:-0}" != "1" && -e "$DEST/egismoc/$SERIAL/$n" ]]; then
        if [[ ",${DEAD:-}," == *",$n,"* ]]; then
            SWAP+=("$n")
        else
            KEPT+=("$n"); continue
        fi
    fi
    FILES+=("$f")
done
[[ ${#KEPT[@]} -gt 0 ]] && info "Already on this install — kept as they are: $(list_of "${KEPT[@]}")"
if [[ ${#FILES[@]} -eq 0 ]]; then
    [[ -n "${ONLY:-}" && ${#KEPT[@]} -eq 0 ]] && error "The export has none of the fingers asked for ($ONLY)."
    info "Nothing to import — ${TARGET_USER} already has every fingerprint in this file."
    exit 0
fi

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
            1) # Leave out the fingers whose template is gone; import the rest.
               GONE=()
               while read -r _tag _user n _path; do
                   [[ "$_tag" == MISSING && "$n" =~ ^[1-9a]$ ]] || continue
                   GONE+=("$n"); rm -f "$TMP/ready/$n"
               done <<< "$CHECK_OUT"
               if [[ -z "$(ls -A "$TMP/ready")" ]]; then
                   systemctl start fprintd 2>/dev/null || true
                   [[ ${#KEPT[@]} -gt 0 ]] && error "The other fingerprints in this export are no longer stored on the sensor\n  (re-enrolled since, or removed by Windows): $(list_of "${GONE[@]}"). Nothing was imported.\n  Enrol them instead, or export again on the install where they work."
                   error "This export is out of date — its fingerprints are no longer stored on the sensor\n  (re-enrolled since, or removed by Windows). Nothing was imported.\n  Enrol instead (fprintd-enroll), or export again on the install where they work."
               fi
               warn "Not imported — no longer stored on the sensor (re-enrolled since, or removed by\n       Windows): $(list_of "${GONE[@]}")" ;;
            *) warn "Could not check the sensor (${CHECK_OUT##*$'\n'}) — importing anyway." ;;
        esac
    else
        warn "Cannot check the sensor ($SENSOR_CHECK missing) — importing without checking."
    fi
fi

mkdir -p /var/lib/fprint
if $HAS_RECORDS && [[ "${REPLACE:-0}" == "1" ]]; then
    # Every check has passed: move the old records aside (records only — the
    # sensor is not touched), so they could be put back if ever needed.
    # The last 5 folders are kept.
    REPLACED_DIR="/var/lib/samsung-galaxybook/replaced-fingerprints"
    OLD="${REPLACED_DIR}/$(date +%Y-%m-%d_%H%M%S)"
    mkdir -p "$OLD"
    chmod 700 "$REPLACED_DIR"
    mv "$DEST" "$OLD/"
    ls -1dt "$REPLACED_DIR"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
    info "Moved ${TARGET_USER}'s previous records to $OLD"
elif [[ ${#SWAP[@]} -gt 0 ]]; then
    # Dead records this export replaces (only those that passed the check):
    # moved aside the same way.
    REPLACED_DIR="/var/lib/samsung-galaxybook/replaced-fingerprints"
    OLD="${REPLACED_DIR}/$(date +%Y-%m-%d_%H%M%S)/${TARGET_USER}/egismoc/${SERIAL}"
    MOVED=()
    for n in "${SWAP[@]}"; do
        [[ -e "$TMP/ready/$n" ]] || continue
        mkdir -p "$OLD"
        chmod 700 "$REPLACED_DIR"
        mv "$DEST/egismoc/$SERIAL/$n" "$OLD/"
        MOVED+=("$n")
    done
    ls -1dt "$REPLACED_DIR"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
    [[ ${#MOVED[@]} -gt 0 ]] && info "Replacing records gone from the sensor: $(list_of "${MOVED[@]}") (old ones moved to $REPLACED_DIR)"
fi
install -d -m 700 -o root -g root "$DEST" "$DEST/egismoc" "$DEST/egismoc/$SERIAL"
NAMES=()
for f in "$TMP/ready"/*; do
    n=$(basename "$f")
    install -m 600 -o root -g root "$f" "$DEST/egismoc/$SERIAL/$n"
    NAMES+=("$n")
done
command -v restorecon >/dev/null 2>&1 && restorecon -R "$DEST" 2>/dev/null || true

systemctl restart fprintd 2>/dev/null || true
if [[ "$SRC_USER" == "$TARGET_USER" ]]; then
    info "Imported $(list_of "${NAMES[@]}") for ${TARGET_USER}"
else
    info "Imported $(list_of "${NAMES[@]}") for ${TARGET_USER} (exported by ${SRC_USER})"
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
