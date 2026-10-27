#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — fingerprint-fix-sdcp: another fingerprint fix's fprintd
# setup (run as root)
# =============================================================================
#   other-fix.sh list       what it finds, one per line:
#                             dropin <path>     an admin fprintd drop-in (in /etc)
#                                               that changes which libfprint fprintd
#                                               loads — e.g. the manual install from
#                                               abdallah-alkanani/libfprint-egismoc-sdcp's
#                                               README (egismoc-sdcp.conf)
#                             pkgdropin <path>  the same, from another package (/usr/lib):
#                                               left alone, only reported
#                             lib <folder>      /usr/local/lib/libfprint-egismoc-sdcp
#                                               that isn't this fix's install.sh copy
#   other-fix.sh takeover   moves the "dropin" and "lib" ones to
#                           /var/lib/samsung-galaxybook/other-fingerprint-fix/<date>/
#                           (with RESTORE.txt saying how to put them back), and says
#                           what it did. Nothing is deleted, fingerprints are kept.
#
# This fix's own drop-in is samsung-galaxybook-egismoc-sdcp.conf, and its
# install.sh copy has the marker /etc/samsung-galaxybook-egismoc-sdcp.installed:
# anything else is someone else's. Used by install.sh and the packages' install
# scripts (takeover), and by the monitor (list). Never fails.
# =============================================================================
OUR_DROPIN="samsung-galaxybook-egismoc-sdcp.conf"
LOCAL_MARKER="/etc/samsung-galaxybook-egismoc-sdcp.installed"
LOCAL_LIB="/usr/local/lib/libfprint-egismoc-sdcp"
ADMIN_DIR="/etc/systemd/system/fprintd.service.d"
PKG_DIR="/usr/lib/systemd/system/fprintd.service.d"
BACKUP_ROOT="/var/lib/samsung-galaxybook/other-fingerprint-fix"

# A drop-in that decides which libfprint fprintd loads, or runs another daemon.
affects_library() {
    grep -qE 'LD_LIBRARY_PATH|LD_PRELOAD|^[[:space:]]*ExecStart=' "$1" 2>/dev/null
}

list() {
    local f
    for f in "$ADMIN_DIR"/*.conf; do
        [[ -f "$f" && "${f##*/}" != "$OUR_DROPIN" ]] && affects_library "$f" && echo "dropin $f"
    done
    for f in "$PKG_DIR"/*.conf; do
        [[ -f "$f" && "${f##*/}" != "$OUR_DROPIN" ]] && affects_library "$f" && echo "pkgdropin $f"
    done
    # The same folder as this fix's install.sh copy: someone else's when that
    # copy's marker isn't there (it is removed with the copy).
    if [[ -d "$LOCAL_LIB" && ! -f "$LOCAL_MARKER" ]] \
            && compgen -G "$LOCAL_LIB/libfprint-2.so*" >/dev/null; then
        echo "lib $LOCAL_LIB"
    fi
    return 0
}

takeover() {
    local found kind path backup moved=()
    found=$(list)
    [[ -n "$found" ]] || return 0
    backup="$BACKUP_ROOT/$(date +%Y-%m-%d_%H%M%S)"
    while read -r kind path; do
        case "$kind" in
            dropin)
                mkdir -p "$backup/fprintd.service.d" \
                    && mv -f "$path" "$backup/fprintd.service.d/" && moved+=("$path") ;;
            lib)
                mkdir -p "$backup" && mv -f "$path" "$backup/" && moved+=("$path") ;;
            pkgdropin)
                local owner
                owner=$( (rpm -qf "$path" || dpkg -S "$path" || pacman -Qqo "$path") 2>/dev/null | head -1)
                echo "Note: another fingerprint setting for fprintd, from a package (${owner:-unknown}):"
                echo "  $path"
                echo "  fingerprint-fix-sdcp's drop-in normally takes priority; if fingerprints don't"
                echo "  work, remove that package." ;;
        esac
    done <<< "$found"
    [[ ${#moved[@]} -gt 0 ]] || return 0
    rmdir "$ADMIN_DIR" 2>/dev/null || true
    {
        echo "Moved aside by fingerprint-fix-sdcp on $(date '+%Y-%m-%d %H:%M'): another"
        echo "fingerprint fix's fprintd setup (e.g. a manual install of"
        echo "abdallah-alkanani/libfprint-egismoc-sdcp from its README)."
        echo
        printf '  %s\n' "${moved[@]}"
        echo
        echo "To put it back (after removing fingerprint-fix-sdcp), as root:"
        [[ -d "$backup/fprintd.service.d" ]] && echo "  mkdir -p $ADMIN_DIR && mv $backup/fprintd.service.d/* $ADMIN_DIR/"
        [[ -d "$backup/${LOCAL_LIB##*/}" ]] && echo "  mv $backup/${LOCAL_LIB##*/} ${LOCAL_LIB%/*}/"
        echo "  systemctl daemon-reload && systemctl restart fprintd"
    } > "$backup/RESTORE.txt"
    chmod -R go-w "$backup" 2>/dev/null
    systemctl daemon-reload 2>/dev/null || true
    echo "Another fingerprint fix's fprintd setup was found and moved aside, so it can't"
    echo "override or be deleted by fingerprint-fix-sdcp (enrolled fingerprints are kept):"
    printf '  %s\n' "${moved[@]}"
    echo "  Backup and how to restore it: $backup/RESTORE.txt"
    return 0
}

case "${1:-}" in
    list)     list ;;
    takeover) takeover ;;
    *)        echo "Usage: $0 list|takeover" >&2 ;;
esac
exit 0
