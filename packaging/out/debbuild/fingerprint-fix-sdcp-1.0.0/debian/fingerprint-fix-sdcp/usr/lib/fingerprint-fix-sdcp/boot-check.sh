#!/bin/bash
# Samsung Galaxy Book — check enrolled fingerprints are still on the sensor
# (runs at boot as root, before fprintd). Never fails the boot.
SENSOR_CHECK="/usr/lib/fingerprint-fix-sdcp/sensor-check"
STATUS="/run/samsung-galaxybook/fprint-sdcp-boot-status"
[[ -f "/usr/lib/fingerprint-fix-sdcp/installed" && -x "$SENSOR_CHECK" ]] || exit 0
mkdir -p "$(dirname "$STATUS")"; chmod 755 "$(dirname "$STATUS")"
rm -f "$STATUS"

# Nothing enrolled at all: nothing to check.
[[ -n "$(find /var/lib/fprint -type f 2>/dev/null | head -1)" ]] || exit 0

# Wait up to 8 seconds for the sensor to appear on USB.
found=false
for _ in $(seq 1 40); do
    for d in /sys/bus/usb/devices/*; do
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "1c7a" ]] || continue
        [[ "$(cat "$d/idProduct" 2>/dev/null)" =~ ^05a[15]$ ]] && found=true && break 2
    done
    sleep 0.2
done
$found || { echo "Fingerprint sensor not found — skipping check"; exit 0; }

OUT=$(timeout 8 "$SENSOR_CHECK" 2>&1); RC=$?
echo "$OUT"
[[ $RC -eq 1 ]] || exit 0

FINGERS=(unknown left-thumb left-index-finger left-middle-finger left-ring-finger
         left-little-finger right-thumb right-index-finger right-middle-finger
         right-ring-finger right-little-finger)
LOST=()
# Dead records are MOVED (not deleted) to a dated safety folder, so a false
# alarm could be undone by moving them back. The last 5 folders are kept.
REMOVED="/var/lib/samsung-galaxybook/removed-fingerprints/$(date +%Y-%m-%d_%H%M%S)"
ALL_CLEARED=true
while read -r _tag _user _finger _path; do
    [[ "$_tag" == "MISSING" ]] || continue
    _name="$_finger"
    # fprintd names records by finger number in hex: 1-9, a = right little finger
    [[ "$_finger" =~ ^[1-9a]$ ]] && _name="${FINGERS[$((16#$_finger))]}"
    LOST+=("${_name} (${_user})")
    # Only ever touch records inside fprintd's own folder.
    _done=false
    if [[ "$_path" == /var/lib/fprint/* && "$_path" != *..* && -f "$_path" ]]; then
        _dest="$REMOVED/${_path#/var/lib/fprint/}"
        mkdir -p "$(dirname "$_dest")" && mv -f "$_path" "$_dest" \
            && echo "Moved dead record $_path to $_dest" && _done=true
    fi
    $_done || { ALL_CLEARED=false; echo "Did not clear record: $_path"; }
done <<< "$OUT"
[[ ${#LOST[@]} -gt 0 ]] || exit 0
chmod -R go-rwx "/var/lib/samsung-galaxybook/removed-fingerprints" 2>/dev/null
ls -1dt "/var/lib/samsung-galaxybook/removed-fingerprints"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
_list=$(printf '%s, ' "${LOST[@]}"); _list="${_list%, }"
if $ALL_CLEARED; then
    _next="They have been cleared from this system — please enrol them again."
else
    _next="Please remove them in your fingerprint settings (or run: fprintd-delete USER) and enrol them again."
fi
printf '%s\n%s\n%s\n' "dialog-warning" \
    "Samsung Galaxy Book — Fingerprint Removed From Sensor" \
    "These fingerprints are no longer stored on the sensor: ${_list}. This usually happens after booting Windows with its fingerprint device enabled. ${_next}" \
    > "$STATUS"
chmod 644 "$STATUS"
exit 0
