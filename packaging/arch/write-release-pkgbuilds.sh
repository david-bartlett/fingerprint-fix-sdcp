#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — write a release's PKGBUILDs from PKGBUILD.release.in
# =============================================================================
#   bash packaging/arch/write-release-pkgbuilds.sh VERSION DRIVER SHA256 OUTDIR
#
#   PKGBUILD           both packages: makepkg -si
#   PKGBUILD-driver    only the driver: makepkg -si -p PKGBUILD-driver
#   PKGBUILD-manager   only the Manager, with nothing to compile:
#                      makepkg -si -p PKGBUILD-manager
#
# All three come from one template, so they can't drift apart. PKGBUILD stays
# as it was: every earlier version's Update looks for that name, and it's the
# one build that installs both packages.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -eq 4 ]] || { echo "Usage: bash $0 VERSION DRIVER SHA256 OUTDIR" >&2; exit 2; }
VERSION="$1"; DRIVER="$2"; SHA="$3"; OUT="$4"
mkdir -p "$OUT"

sed -e "s/@VERSION@/$VERSION/g" -e "s/@DRIVER@/$DRIVER/g" -e "s/@SHA256@/$SHA/g" \
    "$HERE/PKGBUILD.release.in" > "$OUT/PKGBUILD"

# Leave out one shell function, from its opening line to its closing brace
without_function() {
    awk -v name="$1() {" '$0 == name { skip = 1; next } skip { if ($0 == "}") skip = 0; next } { print }'
}

# For both variants: this file's own name in its instructions and messages,
# and the one .install file it needs
one_package() {     # FILE INSTALL_FILE WHAT
    sed -e "s/makepkg -si\$/makepkg -si -p $1/" \
        -e "s/makepkg -si\"/makepkg -si -p $1\"/" \
        -e "s/makepkg -si builds/makepkg -si -p $1 builds/" \
        -e '/The Manager is optional: `makepkg -si` installs both/d' \
        -e "s/^#   Put this file, fingerprint-fix-sdcp.install and\$/#   Put this file and $2 in one folder, then:/" \
        -e '/^#   galaxybook-fingerprint-manager.install in one folder, then:$/d' \
        -e "/^# Two packages from one build:/,/^# makepkg -si.*installs both/c\\# $3 Either package works without the other."
}

without_function package_galaxybook-fingerprint-manager < "$OUT/PKGBUILD" \
    | one_package PKGBUILD-driver fingerprint-fix-sdcp.install "Only the driver." \
    | sed -e 's/^pkgname=.*/pkgname=(fingerprint-fix-sdcp)/' \
          -e 's/^\(pkgdesc=.*\), with the Galaxy Book Fingerprint Manager"$/\1"/' \
    > "$OUT/PKGBUILD-driver"

# The Manager is Python and shell: nothing to compile, and no driver source
without_function package_fingerprint-fix-sdcp < "$OUT/PKGBUILD" \
    | without_function build \
    | one_package PKGBUILD-manager galaxybook-fingerprint-manager.install "Only the Manager." \
    | sed -e 's/^pkgname=.*/pkgname=(galaxybook-fingerprint-manager)/' \
          -e '/^pkgdesc=/c\pkgdesc="Galaxy Book Fingerprint Manager, with boot-time and login checks (Samsung Galaxy Book Egis reader)"' \
          -e "s/^arch=.*/arch=('any')/" \
          -e '/^_driver=/d' \
          -e '/^makedepends=/d' \
          -e '/^source=/s/$/)/' \
          -e '/^ *"libfprint-egismoc-sdcp::git+/d' \
          -e '/^sha256sums=/s/$/)/' \
          -e "/^ *'SKIP')/d" \
    > "$OUT/PKGBUILD-manager"

# A template change that these edits no longer fit shouldn't reach a release
for f in PKGBUILD-driver PKGBUILD-manager; do
    bash -n "$OUT/$f"
    if grep -qE 'makepkg -si$|Two packages from one build' "$OUT/$f"; then
        echo "$0: $f still has text for both packages" >&2; exit 1
    fi
done
grep -q '^pkgname=(fingerprint-fix-sdcp)$' "$OUT/PKGBUILD-driver"
grep -q '^pkgname=(galaxybook-fingerprint-manager)$' "$OUT/PKGBUILD-manager"
if grep -qE '^build\(\)|libfprint-egismoc-sdcp::git' "$OUT/PKGBUILD-manager"; then
    echo "$0: PKGBUILD-manager still builds the driver" >&2; exit 1
fi
