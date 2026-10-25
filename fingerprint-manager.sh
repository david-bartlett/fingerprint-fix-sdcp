#!/bin/bash
# =============================================================================
# Samsung Galaxy Book Fixes — Galaxy Book Fingerprint Manager (fingerprint-fix-sdcp)
# =============================================================================
# Starts the Galaxy Book Fingerprint Manager window (lib/fingerprint-manager.py)
# after checking everything it needs is installed.
#
#   ./fingerprint-manager.sh      run it from the fix folder (as yourself, not sudo)
#
# install.sh also installs a root-owned copy, started from the app menu
# ("Galaxy Book Fingerprint Manager") or with: galaxybook-fingerprint-manager
# (that command is a link to the installed copy of this script).
# =============================================================================

HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APP="$HERE/lib/fingerprint-manager.py"
NAME="Galaxy Book Fingerprint Manager"

# Always print; from the app menu (no terminal) also show a notification.
say() {
    echo -e "$*" >&2
    if [[ ! -t 2 ]] && command -v notify-send >/dev/null 2>&1; then
        notify-send -a "$NAME" -i dialog-error "$NAME" "$(echo -e "$*")"
    fi
}

case "${1:-}" in
    -h|--help)
        sed -n '5,12p' "$0" | sed 's/^# \{0,1\}//'
        exit 0 ;;
esac

# ── Run as the user: the window asks for the password itself when needed ──────
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    say "Run the $NAME as yourself, not with sudo."
    exit 1
fi

# ── The fix must be installed ─────────────────────────────────────────────────
if [[ ! -f /etc/samsung-galaxybook-egismoc-sdcp.installed \
      || ! -f /usr/local/lib/libfprint-egismoc-sdcp/libfprint-2.so.2 ]]; then
    say "fingerprint-fix-sdcp is not installed. Install it first:\n  sudo bash install.sh   (in the fingerprint-fix-sdcp folder)"
    exit 1
fi

# ── Packages the window needs ─────────────────────────────────────────────────
. /etc/os-release 2>/dev/null
case " ${ID,,} ${ID_LIKE,,} " in
    *" fedora "*)                 PM="sudo dnf install -y"; P_PY=python3; P_GI=python3-gobject; P_GTK=gtk3; P_FP=libfprint; P_PK=polkit; P_CA=python3-cairo ;;
    *" debian "*|*" ubuntu "*)    PM="sudo apt install -y"; P_PY=python3; P_GI=python3-gi; P_GTK=gir1.2-gtk-3.0; P_FP=gir1.2-fprint-2.0; P_PK=pkexec; P_CA=python3-gi-cairo ;;
    *" arch "*)                   PM="sudo pacman -S --needed"; P_PY=python; P_GI=python-gobject; P_GTK=gtk3; P_FP=libfprint; P_PK=polkit; P_CA=python-cairo ;;
    *)                            PM=""; P_PY=python3; P_GI="PyGObject"; P_GTK="GTK 3"; P_FP="libfprint introspection data"; P_PK=pkexec; P_CA="PyGObject cairo support" ;;
esac

missing=()
if ! command -v python3 >/dev/null 2>&1; then
    missing+=("$P_PY" "$P_GI" "$P_GTK" "$P_FP" "$P_CA")
else
    python3 -c 'import gi' 2>/dev/null || missing+=("$P_GI")
    python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null \
        || missing+=("$P_GTK")
    python3 -c 'import gi; gi.require_version("FPrint", "2.0")' 2>/dev/null || missing+=("$P_FP")
    python3 -c 'import gi; gi.require_foreign("cairo")' 2>/dev/null || missing+=("$P_CA")
fi
command -v pkexec >/dev/null 2>&1 || missing+=("$P_PK")
# keep each package once
mapfile -t missing < <(printf '%s\n' "${missing[@]}" | awk 'NF && !seen[$0]++')

if [[ ${#missing[@]} -gt 0 ]]; then
    if [[ -n "$PM" ]]; then
        cmd="$PM ${missing[*]}"
        if [[ -t 0 && -t 1 ]]; then
            echo "The $NAME needs: ${missing[*]}"
            read -r -p "Install them now ($cmd)? [Y/n] " ans
            if [[ -z "$ans" || "${ans,,}" == y* ]]; then
                $cmd || { echo "Install failed — run it yourself: $cmd"; exit 1; }
            else
                exit 1
            fi
        else
            say "The $NAME needs: ${missing[*]}\nInstall with:\n  $cmd"
            exit 1
        fi
    else
        say "The $NAME needs: ${missing[*]}"
        exit 1
    fi
fi

[[ -f "$APP" ]] || { say "Missing $APP — keep the whole fingerprint-fix-sdcp folder together."; exit 1; }
exec python3 "$APP" "$@"
