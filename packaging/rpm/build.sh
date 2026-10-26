#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — build the .rpm from this checkout
# =============================================================================
#   bash packaging/rpm/build.sh [RELEASE]      (RELEASE: rpm Release number, default 1)
#
# Packages the checkout as it is now (tracked and new files) with the driver
# commit named in DRIVER. The .rpm is written to packaging/out/.
# Needs: sudo dnf install rpm-build gcc meson ninja-build patch glib2-devel \
#            libgusb-devel openssl-devel systemd-rpm-macros
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$REPO/packaging/out"
TOP="$OUT/rpmbuild"
VERSION=$(tr -d '[:space:]' < "$REPO/VERSION")
DRIVER=$(grep -v '^#' "$REPO/DRIVER" | tr -d '[:space:]')

rm -rf "$TOP"
mkdir -p "$TOP/SOURCES"
bash "$REPO/packaging/make-sources.sh" "$TOP/SOURCES" >/dev/null
# shellcheck disable=SC2086  # RPMBUILD_OPTS: extra rpmbuild options, word-split on purpose
rpmbuild -bb ${RPMBUILD_OPTS:-} --define "_topdir $TOP" \
    --define "fixver $VERSION" --define "driver $DRIVER" --define "rel ${1:-1}" \
    "$HERE/fingerprint-fix-sdcp.spec"
for f in "$TOP"/RPMS/*/*.rpm; do
    cp "$f" "$OUT/"
    echo "Built: $OUT/$(basename "$f")"
done
