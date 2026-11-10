#!/bin/bash
# =============================================================================
# Check that every reader check accepts exactly the readers in FPRINT_READERS
# =============================================================================
#   bash tools/dev/check-readers.sh
#
# The list of accepted readers (USB 1c7a:<id>) lives in lib/fixpaths.sh, but
# each check keeps its own copy: package scripts run before any file of ours is
# installed, so they can't read it. This finds every check, in the four forms
# they're written in, and fails if one lists different readers, or if a file
# that should have a check has none. The release workflow runs it first.
# =============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# shellcheck disable=SC1091
FPRINT_READERS=$(bash -c '. lib/fixpaths.sh; fix_layout package >/dev/null 2>&1; echo "$FPRINT_READERS"')
[[ -n "$FPRINT_READERS" ]] || { echo "FPRINT_READERS is empty or missing in lib/fixpaths.sh" >&2; exit 1; }

# Each of these must have at least one check.
MUST=(
    install.sh lib/fixpaths.sh
    lib/fingerprint-manager.py lib/fingerprint-manager-helper.py lib/distro-driver-check.py
    packaging/files/fprintd-env.sh.in packaging/files/boot-check.sh.in packaging/files/monitor.sh.in
    packaging/debian/fingerprint-fix-sdcp.preinst packaging/debian/galaxybook-fingerprint-manager.preinst
    packaging/rpm/fingerprint-fix-sdcp.spec packaging/arch/PKGBUILD.release.in
    packaging/arch/fingerprint-fix-sdcp.install packaging/arch/galaxybook-fingerprint-manager.install
    tools/export-fingerprint.sh tools/import-fingerprint.sh
)

python3 - "$FPRINT_READERS" "${MUST[@]}" <<'PY'
import re, subprocess, sys
want = sorted(sys.argv[1].split())
must = sys.argv[2:]
ID = r"0[0-9a-f]{3}"
FORMS = [
    re.compile(rf"\bin ((?:{ID}\|)+{ID}|{ID})\)"),          # case … in 05a5|05a1) ;;
    re.compile(rf"=~ \^\(((?:{ID}\|)*{ID})\)\$"),           # [[ … =~ ^(05a5|05a1)$ ]]
    re.compile(rf"\bin \(((?:\"{ID}\",? ?)+)\)"),           # if pid in ("05a5", "05a1"):
    re.compile(rf"\"((?:1c7a:{ID}\|)*1c7a:{ID})\""),        # "1c7a:05a5|1c7a:05a1"
]
files = subprocess.run(["git", "ls-files", "--", "*.sh", "*.py", "*.in", "*.spec", "*.install",
                        "*.preinst", "install.sh", "uninstall.sh"],
                       capture_output=True, text=True, check=True).stdout.split()
files = [f for f in files if not f.startswith(("lib/patches/", "tools/dev/check-readers"))]
bad, seen = [], {}
for f in files:
    for n, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        for form in FORMS:
            for m in form.finditer(line):
                ids = re.findall(ID, m.group(1).replace("1c7a:", ""))
                seen[f] = seen.get(f, 0) + 1
                if sorted(ids) != want:
                    bad.append(f"{f}:{n}: accepts {' '.join(ids)}")
missing = [f for f in must if not seen.get(f)]
total = sum(seen.values())
for b in bad:
    print(b)
for f in missing:
    print(f"{f}: no reader check found (was it rewritten in another form?)")
if bad or missing:
    print(f"\nFPRINT_READERS in lib/fixpaths.sh is: {sys.argv[1]}")
    sys.exit(1)
print(f"OK: {total} reader checks in {len(seen)} files all accept {sys.argv[1]}")
PY
