#!/bin/bash
# Samsung Galaxy Book — egismoc SDCP fingerprint fix monitor (system service, root)
# Writes any notification to FPRINT_STATUS_FILE; the user check script shows it.
FPRINT_LIB="/usr/lib/fingerprint-fix-sdcp/libfprint-2.so.2"
FPRINT_DROPIN="/usr/lib/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf"
FPRINT_MARKER="/usr/lib/fingerprint-fix-sdcp/installed"
FPRINT_SYSLIB_HASH="/var/lib/samsung-galaxybook/libfprint-system.sha256"
FPRINT_CLEANUP=""
HARDWARE_USB_ID="1c7a:05a5|1c7a:05a1"
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
        # A package's drop-in (under /usr/lib) is switched off by masking it
        # from /run, so a crash or reboot can never leave it off; install.sh's
        # drop-in in /etc is moved aside.
        RUN_MASK="/run/systemd/system/fprintd.service.d/${FPRINT_DROPIN##*/}"
        restore_dropin() {
            rm -f "$RUN_MASK"
            [[ -f "${FPRINT_DROPIN}.testing" ]] && mv -f "${FPRINT_DROPIN}.testing" "$FPRINT_DROPIN"
            systemctl daemon-reload; systemctl restart fprintd 2>/dev/null || true
        }
        trap restore_dropin EXIT
        if [[ "$FPRINT_DROPIN" == /usr/lib/* ]]; then
            mkdir -p "${RUN_MASK%/*}"; ln -sfn /dev/null "$RUN_MASK"
        else
            mv -f "$FPRINT_DROPIN" "${FPRINT_DROPIN}.testing"
        fi
        systemctl daemon-reload; systemctl stop fprintd 2>/dev/null || true
        if [[ -n "$SENSOR_ON_BUS" ]] && check_sensor_usable; then
            trap - EXIT
            if [[ -z "$FPRINT_CLEANUP" ]]; then
                # Installed as a package: only the package manager may remove
                # it. Keep the fix running and say so once.
                restore_dropin
                echo "$CURRENT_HASH" > "$FPRINT_SYSLIB_HASH"
                notify_user "Samsung Galaxy Book — Fingerprint Fix No Longer Needed" \
                    "Your distro's libfprint now supports the fingerprint sensor, so the fingerprint-fix-sdcp package can be removed. It keeps working until you remove it. If fingerprint login stops working afterwards, re-enrol your fingerprints." \
                    "dialog-information"
                exit 0
            fi
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
