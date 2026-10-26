#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — build the driver for a package (all formats)
# =============================================================================
#   bash packaging/build-driver.sh DRIVER_SOURCE_DIR
#
# In DRIVER_SOURCE_DIR (libfprint-egismoc-sdcp at the DRIVER commit):
#   1. applies lib/patches/*.patch that are still needed  → .fix-patches
#   2. builds only the egismoc driver                     → build/libfprint/libfprint-2.so.2.0.0
#   3. builds the boot-time sensor check against it       → build/sensor-check
#   4. notes the driver commit's date                     → .driver-date
# The distro's CFLAGS / LDFLAGS are used when set (makepkg, rpmbuild, dh).
# install.sh does the same steps itself, with its own messages.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SRC="$(cd "${1:?Usage: bash $0 DRIVER_SOURCE_DIR}" && pwd)"
# shellcheck source-path=SCRIPTDIR source=../lib/fixpaths.sh
. "$REPO/lib/fixpaths.sh"
fix_layout package
cd "$SRC"

# ── 1. Driver fixes kept in lib/patches/ until they are in the fork ───────────
# Same rule as install.sh: apply if needed, skip if already in, stop if it no
# longer fits. Done once, so the build can be repeated.
if [[ ! -f .fix-patches ]]; then
    : > .fix-patches.tmp
    for p in "$REPO"/lib/patches/*.patch; do
        [[ -f "$p" ]] || continue
        name=$(basename "$p" .patch)
        # patch, not git apply: the source may be an unpacked tarball inside
        # another git checkout, where git apply would use the wrong root.
        if patch -p1 -N -f -s --dry-run < "$p" >/dev/null 2>&1; then
            patch -p1 -N -f -s < "$p"
            echo "$name" >> .fix-patches.tmp
            echo "Applied fix: $name"
        elif patch -p1 -R -f -s --dry-run < "$p" >/dev/null 2>&1; then
            echo "Fix already in the source: $name"
        else
            echo "Fix $name no longer fits this driver source — update or remove lib/patches/$name.patch" >&2
            exit 1
        fi
    done
    mv .fix-patches.tmp .fix-patches
fi

# ── 2. Only the egismoc driver ────────────────────────────────────────────────
export CFLAGS="${CFLAGS:--O2 -g}"
if [[ ! -f build/build.ninja ]]; then
    meson setup build --prefix=/usr --buildtype=plain --wrap-mode=nodownload -Db_pie=true \
        -Ddrivers=egismoc -Dtod=false -Ddoc=false -Dgtk-examples=false \
        -Dintrospection=false -Dinstalled-tests=false \
        -Dudev_rules=disabled -Dudev_hwdb=disabled
fi
meson compile -C build
[[ -f build/libfprint/libfprint-2.so.2.0.0 ]] \
    || { echo "Build finished but libfprint-2.so.2.0.0 was not produced" >&2; exit 1; }

# ── 3. Boot-time sensor check ─────────────────────────────────────────────────
# Its runpath makes it load the library from the package folder, never the
# distro libfprint.
# shellcheck disable=SC2046,SC2086  # flags and pkg-config output must be word-split
${CC:-gcc} ${CPPFLAGS:-} $CFLAGS -Wall -o build/sensor-check "$REPO/lib/sensor-check.c" \
    -Ilibfprint -Ibuild/libfprint \
    $(pkg-config --cflags glib-2.0 gio-2.0 gobject-2.0 gusb) \
    ${LDFLAGS:-} -Lbuild/libfprint -lfprint-2 \
    $(pkg-config --libs glib-2.0 gio-2.0 gobject-2.0) \
    -Wl,-rpath,"$FPRINT_LIB_DIR"

# ── 4. The driver commit's date, for the install marker ───────────────────────
# From git when there is a checkout; a GitHub or git-archive tarball stamps
# every file with the commit's time instead.
if [[ -e .git ]]; then
    git log -1 --format=%cs > .driver-date
else
    date -u -r meson.build +%F > .driver-date
fi
echo "Driver built ($(<.driver-date))"
