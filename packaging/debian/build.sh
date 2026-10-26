#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — build the .deb from this checkout
# =============================================================================
#   bash packaging/debian/build.sh [REVISION]    (REVISION: Debian revision, default 1)
#
# Packages the checkout as it is now (tracked and new files) with the driver
# commit named in DRIVER. The .deb is written to packaging/out/.
# Build on the oldest release it should run on — Ubuntu 24.04 (the driver
# needs glib 2.80) — and the result also installs on Ubuntu 26.04, Mint 22 / 27
# and Debian 13 / MX 25.
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
DEBVER="$VERSION-${1:-1}"

rm -rf "$WORK"
mkdir -p "$WORK"
bash "$REPO/packaging/make-sources.sh" "$WORK" >/dev/null

# Source tree: this checkout, the driver in driver/, this folder as debian/
TREE="$WORK/fingerprint-fix-sdcp-$VERSION"
tar -xzf "$WORK/fingerprint-fix-sdcp-$VERSION.tar.gz" -C "$WORK"
mkdir -p "$TREE/driver"
tar -xzf "$WORK/libfprint-egismoc-sdcp-$DRIVER.tar.gz" -C "$TREE/driver" --strip-components=1
mkdir -p "$TREE/debian"
cp -a "$HERE"/{control,rules,copyright,docs,preinst,postinst,prerm,postrm,source} "$TREE/debian/"
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
