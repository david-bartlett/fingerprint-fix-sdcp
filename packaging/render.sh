#!/bin/bash
# =============================================================================
# fingerprint-fix-sdcp — fill in a file from packaging/files/ for one layout
# =============================================================================
#   bash packaging/render.sh local|package TEMPLATE   → the file on stdout
#
# Templates name paths as @FPRINT_LIB_DIR@, @MGR_BIN@ and so on; the values come
# from lib/fixpaths.sh, so install.sh (local) and the packages (package) install
# the same scripts and units, each with its own paths.
# =============================================================================
set -euo pipefail
shopt -u patsub_replacement 2>/dev/null || true     # bash 5.2: keep '&' literal

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -eq 2 ]] || { echo "Usage: bash $0 local|package TEMPLATE" >&2; exit 2; }
# shellcheck source-path=SCRIPTDIR source=../lib/fixpaths.sh
. "$HERE/../lib/fixpaths.sh"
fix_layout "$1"
TPL="$HERE/files/$2"
[[ -f "$TPL" ]] || { echo "render.sh: no template $TPL" >&2; exit 1; }

VARS=(FPRINT_LIB_DIR FPRINT_LIB FPRINT_SENSOR_CHECK FPRINT_MARKER MGR_MARKER MGR_CLEANUP
      FPRINT_UNIT_DIR FPRINT_DROPIN_DIR FPRINT_DROPIN
      FPRINT_CHECK_SCRIPT FPRINT_USER_CHECK_SCRIPT FPRINT_BOOT_CHECK_SCRIPT
      FPRINT_CLEANUP FPRINT_POLKIT_RULE FPRINT_ENV_SCRIPT FPRINT_ENV_FILE FPRINT_OTHER_FIX
      MGR_DIR MGR_BIN MGR_ICON MGR_DESKTOP MGR_POLICY SESSION_HELPER_SCRIPT
      FIX_UPDATE_DIR FIX_UPDATE_SVC MGR_UPDATE_SVC MGR_PACKAGE_MARKER MGR_LOCAL_MARKER)

text="$(<"$TPL")"
for v in "${VARS[@]}"; do
    text="${text//"@${v}@"/"${!v}"}"
done
if left=$(grep -o '@[A-Z][A-Z_]*@' <<< "$text" | sort -u | tr '\n' ' ') && [[ -n "$left" ]]; then
    echo "render.sh: $2 still has unknown names: $left" >&2
    exit 1
fi
printf '%s\n' "$text"
