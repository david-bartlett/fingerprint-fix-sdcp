#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — the notes of a GitHub release
# =============================================================================
#   bash .github/release-notes.sh VERSION > notes.md
#
# Written by the release workflow when it creates a release:
#   1. the box at the top of .github/release-install.md (everything before
#      its first "## " heading)
#   2. What's new: the lines of this version's CHANGELOG.md section that start
#      with a bold headline — "- **Two packages:** …" — the ones worth
#      reading; then the whole section, collapsed under "Full changelog"
#   3. the rest of .github/release-install.md: 1. Install, 2. Update
# A section with no bold lines is shown in full under What's new instead.
# Same layout as galaxybook-fan's release pages.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
version="${1:?Usage: bash .github/release-notes.sh VERSION}"

section=$(awk -v h="## $version" 'index($0, h " ") == 1 || $0 == h { f = 1; next }
                                  f && /^## / { exit } f' CHANGELOG.md | sed '/^[[:space:]]*$/d')
highlights=$(grep -E '^- \*\*' <<< "$section" || true)

install=$(sed "s/@VERSION@/$version/g" .github/release-install.md)
awk '/^## /{exit} {print}' <<< "$install"      # the box at the top
echo "## What's new"
echo
if [[ -z "$section" ]]; then
    echo "See [CHANGELOG.md](CHANGELOG.md)."
elif [[ -z "$highlights" ]]; then
    echo "$section"
else
    echo "$highlights"
    echo
    echo "<details>"
    echo "<summary>Full changelog</summary>"
    echo
    echo "$section"
    echo
    echo "</details>"
fi
echo
awk '/^## /{f = 1} f' <<< "$install"           # 1. Install, 2. Update
