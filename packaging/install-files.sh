#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — put a package's files in place (all formats)
# =============================================================================
#   bash packaging/install-files.sh DESTDIR DRIVER_SOURCE_DIR PACKAGE_VERSION FORMAT PART
#
#   DESTDIR            the package's staging root ($pkgdir, %{buildroot}, debian/<pkg>)
#   DRIVER_SOURCE_DIR  built by packaging/build-driver.sh
#   PACKAGE_VERSION    e.g. 1.0.1-1, shown in the install marker
#   FORMAT             pacman | rpm | deb, shown in the install marker
#   PART               driver   — fingerprint-fix-sdcp: the libfprint build and
#                                 fprintd's drop-in
#                      manager  — galaxybook-fingerprint-manager: the window,
#                                 helper, tools, monitor, boot and login checks
#
# FIX_PACKAGE_SCRIPT_DIR / MGR_PACKAGE_SCRIPT_DIR (optional) put each part's
# scripts somewhere other than its library folder (Fedora: /usr/libexec/<name>).
# Paths come from lib/fixpaths.sh, file contents from packaging/files/ via render.sh.
# Distro-specific extras (systemd presets, docs, folder permissions) are left
# to each format's own packaging.
# =============================================================================
set -euo pipefail
umask 022

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
[[ $# -eq 5 ]] || { echo "Usage: bash $0 DESTDIR DRIVER_SOURCE_DIR PACKAGE_VERSION FORMAT driver|manager" >&2; exit 2; }
D="$1"; SRC="$2"; PKGVERSION="$3"; FORMAT="$4"; PART="$5"
# shellcheck source-path=SCRIPTDIR source=../lib/fixpaths.sh
. "$REPO/lib/fixpaths.sh"
fix_layout package

render() { bash "$HERE/render.sh" package "$1"; }       # *_PACKAGE_SCRIPT_DIR pass through
put()    { install -d "$D$(dirname "$2")"; render "$1" > "$D$2"; chmod "${3:-644}" "$D$2"; }

VERSION=$(tr -d '[:space:]' < "$REPO/VERSION")
DRIVER=$(grep -v '^#' "$REPO/DRIVER" | tr -d '[:space:]')

case "$PART" in
driver)
    # ── The driver library, for fprintd only ──────────────────────────────────
    install -Dm755 "$SRC/build/libfprint/libfprint-2.so.2.0.0" "$D$FPRINT_LIB"
    put dropin.conf.in "$FPRINT_DROPIN"
    # Run by the drop-in each time fprintd starts: the driver only with the reader.
    put fprintd-env.sh.in "$FPRINT_ENV_SCRIPT" 755
    # Moves another fingerprint fix's fprintd setup aside (run by the install
    # scripts), and lists it for the monitor.
    install -Dm755 "$REPO/lib/other-fix.sh" "$D$FPRINT_OTHER_FIX"
    # Its own copy of the fingerprint-login scripts: installed without the
    # Manager, the driver's install script turns fingerprint login on itself
    # (once per computer, pam-first-install.sh).
    for t in fingerprint-pam.sh arch-pam.sh pam-first-install.sh; do
        install -Dm755 "$REPO/tools/$t" "$D$FPRINT_LIB_DIR/pam/$t"
    done
    # Install marker, in install.sh's format (the Manager shows it):
    # '<driver commit> <driver date> <source> … fingerprint-fix-sdcp <version>'
    fixes=$(paste -sd' ' "$SRC/.fix-patches" 2>/dev/null || true)
    printf '%s %s fork%s (%s package %s) fingerprint-fix-sdcp %s\n' \
        "${DRIVER:0:12}" "$(<"$SRC/.driver-date")" "${fixes:+ +$fixes}" \
        "$FORMAT" "$PKGVERSION" "$VERSION" > "$D$FPRINT_MARKER"
    chmod 644 "$D$FPRINT_MARKER"
    ;;
manager)
    # Install marker: how the Manager was installed (its Update reads it) —
    # '(<format> package <package version>) galaxybook-fingerprint-manager <version>'
    install -d "$D$(dirname "$MGR_MARKER")"
    printf '(%s package %s) galaxybook-fingerprint-manager %s\n' \
        "$FORMAT" "$PKGVERSION" "$VERSION" > "$D$MGR_MARKER"
    chmod 644 "$D$MGR_MARKER"

    # ── Monitor, boot-time sensor check, login check ──────────────────────────
    put monitor.sh.in       "$FPRINT_CHECK_SCRIPT" 755
    put user-check.sh.in    "$FPRINT_USER_CHECK_SCRIPT" 755
    put boot-check.sh.in    "$FPRINT_BOOT_CHECK_SCRIPT" 755
    put monitor.service.in    "$FPRINT_UNIT_DIR/$FPRINT_MONITOR_SVC"
    put boot-check.service.in "$FPRINT_UNIT_DIR/$FPRINT_BOOT_CHECK_SVC"
    put user-check.service.in "$FPRINT_USER_UNIT_DIR/$FPRINT_USER_CHECK_SVC"
    put user-check.timer.in   "$FPRINT_USER_UNIT_DIR/$FPRINT_USER_CHECK_TIMER"
    put polkit-monitor.rules.in "$FPRINT_POLKIT_RULE"
    # Starts graphical-session.target on desktops that don't (Xfce and others),
    # so the login check runs there too.
    put session-start.sh.in   "$SESSION_HELPER_SCRIPT" 755
    # Run by the package's install script: the login check right away for users
    # already logged in.
    put notify-users.sh.in    "$MGR_SCRIPT_DIR/notify-users.sh" 755
    put session.target.in     "$SESSION_HELPER_TARGET"
    put session-autostart.desktop.in "$SESSION_HELPER_AUTOSTART"

    # ── Galaxy Book Fingerprint Manager ───────────────────────────────────────
    install -Dm755 "$REPO/fingerprint-manager.sh" "$D$MGR_DIR/fingerprint-manager.sh"
    install -Dm644 "$REPO/VERSION" "$D$MGR_DIR/VERSION"
    install -Dm755 -t "$D$MGR_DIR/lib" "$REPO/lib/fingerprint-manager.py" "$REPO/lib/fingerprint-manager-helper.py" \
        "$REPO/lib/update_check.py" "$REPO/lib/notify-open-manager.sh" "$REPO/lib/distro-driver-check.py" \
        "$REPO/lib/sensor-check.py"
    install -Dm644 -t "$D$MGR_DIR/lib" "$REPO/lib/fixpaths.sh"
    install -d "$D$MGR_DIR/tools"
    for t in fingerprint-pam.sh arch-pam.sh pam-first-install.sh export-fingerprint.sh import-fingerprint.sh; do
        install -m755 "$REPO/tools/$t" "$D$MGR_DIR/tools/"
    done
    install -d "$D$(dirname "$MGR_BIN")"
    ln -sfn "$MGR_DIR/fingerprint-manager.sh" "$D$MGR_BIN"
    install -Dm644 "$REPO/lib/$MGR_ID.svg" "$D$MGR_ICON"
    put manager.desktop.in "$MGR_DESKTOP"
    put manager.policy.in  "$MGR_POLICY"
    ;;
*)
    echo "install-files.sh: PART must be driver or manager, not '$PART'" >&2
    exit 2 ;;
esac
