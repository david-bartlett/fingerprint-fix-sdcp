#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — source tarballs for the rpm and deb builds
# =============================================================================
#   bash packaging/make-sources.sh OUTDIR
#
# Writes to OUTDIR:
#   fingerprint-fix-sdcp-<VERSION>.tar.gz           this checkout as it is now
#                                                   (tracked + new files, not ignored ones)
#   libfprint-egismoc-sdcp-<DRIVER>.tar.gz          the driver commit named in DRIVER
#                                                   (GitHub's archive; git if that fails)
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
OUT="$(mkdir -p "${1:?Usage: bash $0 OUTDIR}" && cd "$1" && pwd)"
VERSION=$(tr -d '[:space:]' < "$REPO/VERSION")
DRIVER=$(grep -v '^#' "$REPO/DRIVER" | tr -d '[:space:]')
DRIVER_URL="https://github.com/david-bartlett/libfprint-egismoc-sdcp"

# ── This checkout ─────────────────────────────────────────────────────────────
FIX_TAR="$OUT/fingerprint-fix-sdcp-$VERSION.tar.gz"
( cd "$REPO" && git ls-files -co --exclude-standard -z \
    | tar --null -T - --transform "s|^|fingerprint-fix-sdcp-$VERSION/|" -czf "$FIX_TAR" )
echo "$FIX_TAR"

# ── The driver ────────────────────────────────────────────────────────────────
DRV_TAR="$OUT/libfprint-egismoc-sdcp-$DRIVER.tar.gz"
if [[ ! -s "$DRV_TAR" ]]; then
    if ! curl -fsSL -o "$DRV_TAR.part" "$DRIVER_URL/archive/$DRIVER.tar.gz" 2>/dev/null; then
        # Same contents and file times as GitHub's archive.
        tmp=$(mktemp -d)
        git -C "$tmp" init -q
        git -C "$tmp" fetch -q --depth 1 "$DRIVER_URL.git" "$DRIVER"
        git -C "$tmp" archive --format=tar.gz --prefix="libfprint-egismoc-sdcp-$DRIVER/" \
            -o "$DRV_TAR.part" "$DRIVER"
        rm -rf "$tmp"
    fi
    mv "$DRV_TAR.part" "$DRV_TAR"
fi
echo "$DRV_TAR"
