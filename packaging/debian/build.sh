#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — build the .deb from this checkout
# =============================================================================
#   bash packaging/debian/build.sh [REVISION]    (REVISION: Debian revision, default 1)
#
# Packages the checkout as it is now (tracked and new files) with the driver
# commit named in DRIVER. The two .debs (fingerprint-fix-sdcp, the driver, and
# galaxybook-fingerprint-manager) are written to packaging/out/.
#
# A .deb is for the release it was built on: its library dependencies are
# taken from that system, and Debian / Ubuntu rename library packages between
# releases (e.g. libgusb2 → libgusb2a in Ubuntu 26.04). So the release name is
# part of the version — 1.0.1-1~ubuntu26.04, 1.0.1-1~debian13 — and the release
# workflow builds one per supported release. Mint builds as its Ubuntu base,
# MX as its Debian base.
# Needs: sudo apt install build-essential debhelper meson ninja-build patch \
#            pkgconf libglib2.0-dev libgusb-dev libssl-dev curl
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$REPO/packaging/out"
WORK="$OUT/debbuild"
VERSION=$(tr -d '[:space:]' < "$REPO/VERSION")
DRIVER=$(grep -v '^#' "$REPO/DRIVER" | tr -d '[:space:]')
# The release this is built on: ubuntu24.04, ubuntu26.04, debian13, …
dist_tag() {
    local ID="" VERSION_ID="" UBUNTU_CODENAME=""
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${UBUNTU_CODENAME:-}" in                    # Mint and other Ubuntu-based
        noble)    echo ubuntu24.04; return ;;
        resolute) echo ubuntu26.04; return ;;
    esac
    case "$ID" in
        ubuntu|debian) echo "$ID$VERSION_ID" ;;
        *)             echo "${ID}${VERSION_ID}" ;;
    esac
}
DIST=$(dist_tag)
DEBVER="$VERSION-${1:-1}~$DIST"

rm -rf "$WORK"
mkdir -p "$WORK"
bash "$REPO/packaging/make-sources.sh" "$WORK" >/dev/null

# Source tree: this checkout, the driver in driver/, this folder as debian/
TREE="$WORK/fingerprint-fix-sdcp-$VERSION"
tar -xzf "$WORK/fingerprint-fix-sdcp-$VERSION.tar.gz" -C "$WORK"
mkdir -p "$TREE/driver"
tar -xzf "$WORK/libfprint-egismoc-sdcp-$DRIVER.tar.gz" -C "$TREE/driver" --strip-components=1
mkdir -p "$TREE/debian"
cp -a "$HERE"/{control,rules,copyright,source} "$HERE"/fingerprint-fix-sdcp.* \
      "$HERE"/galaxybook-fingerprint-manager.* "$TREE/debian/"
cat > "$TREE/debian/changelog" <<EOF
fingerprint-fix-sdcp ($DEBVER) unstable; urgency=medium

  * fingerprint-fix-sdcp $VERSION with libfprint-egismoc-sdcp ${DRIVER:0:12}.
    See /usr/share/doc/fingerprint-fix-sdcp/CHANGELOG.md.gz.

 -- David Bartlett <22402006+david-bartlett@users.noreply.github.com>  $(date -R)
EOF

( cd "$TREE" && dpkg-buildpackage -b -us -uc )
for f in "$WORK"/*.deb; do
    cp "$f" "$OUT/"
    echo "Built: $OUT/$(basename "$f")"
done
