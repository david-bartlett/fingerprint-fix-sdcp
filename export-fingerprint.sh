#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Export fingerprints
# =============================================================================
# Saves your enrolled fingerprint records so another Linux install on THIS
# laptop can use the same fingerprints (see import-fingerprint.sh).
#
#   sudo bash export-fingerprint.sh            → ~/fingerprint-export.tgz
#   sudo bash export-fingerprint.sh FILE.tgz   → FILE.tgz
#
# The records hold only the ID of each template stored on the sensor — no
# fingerprint image and no secret. Nothing on the system is changed.
# =============================================================================

set -e

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run with sudo: sudo bash export-fingerprint.sh"
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

USER_NAME="${SUDO_USER:-}"
[[ -n "$USER_NAME" && "$USER_NAME" != "root" ]] \
    || error "Run this with sudo from your own account (not as root directly)."
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)

[[ -f /etc/samsung-galaxybook-egismoc-sdcp.installed ]] \
    || warn "fingerprint-fix-sdcp does not seem to be installed — exporting anyway."

SERIAL=$(sensor_serial) || error "EgisTec fingerprint sensor (1c7a:05a5 / 1c7a:05a1) not found."
REL="${USER_NAME}/egismoc/${SERIAL}"
SRC="/var/lib/fprint/${REL}"

shopt -s nullglob
FILES=("$SRC"/*)
shopt -u nullglob
[[ ${#FILES[@]} -gt 0 ]] || error "No fingerprints enrolled for ${USER_NAME} on this sensor — nothing to export."

OUT="${1:-${USER_HOME}/fingerprint-export.tgz}"
[[ "$OUT" == *.tgz || "$OUT" == *.tar.gz ]] || OUT="${OUT}.tgz"

tar -C /var/lib/fprint -czf "$OUT" "$REL"
chown "$USER_NAME:" "$OUT"
chmod 600 "$OUT"

NAMES=()
for f in "${FILES[@]}"; do
    n=$(basename "$f")
    [[ "$n" =~ ^([1-9]|10)$ ]] && NAMES+=("${FINGERS[$n]}") || NAMES+=("$n")
done
info "Exported ${NAMES[*]} for ${USER_NAME} to ${OUT}"
echo
echo "  On the other install, copy it to the same place in your home folder"
echo "  (~/fingerprint-export.tgz) and the installer offers to import it, or run:"
echo "      sudo bash import-fingerprint.sh ~/$(basename "$OUT")"
echo "  It is imported for whoever runs it — the username there can differ."
echo
echo "  Re-export after deleting or re-enrolling these fingers — the old file"
echo "  will point at templates that no longer exist."
