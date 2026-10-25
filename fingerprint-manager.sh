#!/bin/bash
# =============================================================================
# Samsung Galaxy Book — Fingerprint Fix (egismoc SDCP) — Fingerprint Manager
# =============================================================================
# Starts the Fingerprint Manager window (lib/fingerprint-manager.py) after
# checking everything it needs is installed.
#
#   ./fingerprint-manager.sh                    start it (as yourself, not sudo)
#   ./fingerprint-manager.sh --add-to-menu      add "Fingerprint Manager" to
#                                               your app menu
#   ./fingerprint-manager.sh --remove-from-menu take it out again
#
# The menu entry points at this folder, so keep the folder where it is (or run
# --add-to-menu again after moving it).
# =============================================================================

HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APP="$HERE/lib/fingerprint-manager.py"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/samsung-galaxybook-fingerprint-manager.desktop"

# Always print; from the app menu (no terminal) also show a notification.
say() {
    echo -e "$*" >&2
    if [[ ! -t 2 ]] && command -v notify-send >/dev/null 2>&1; then
        notify-send -a "Fingerprint Manager" -i dialog-error "Fingerprint Manager" "$(echo -e "$*")"
    fi
}

case "${1:-}" in
    --add-to-menu)
        mkdir -p "$(dirname "$DESKTOP")"
        cat > "$DESKTOP" << EOF
[Desktop Entry]
Type=Application
Name=Fingerprint Manager
Comment=Test, enrol, share and tidy fingerprints on the Galaxy Book sensor
Exec="$HERE/fingerprint-manager.sh"
Icon=fingerprint-gui
StartupWMClass=samsung-galaxybook-fingerprint-manager
Terminal=false
Categories=Settings;HardwareSettings;
Keywords=fingerprint;fprint;sensor;login;
EOF
        chmod 644 "$DESKTOP"
        command -v update-desktop-database >/dev/null 2>&1 \
            && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null
        echo "Added \"Fingerprint Manager\" to your app menu ($DESKTOP)."
        exit 0 ;;
    --remove-from-menu)
        rm -f "$DESKTOP"
        echo "Removed \"Fingerprint Manager\" from your app menu."
        exit 0 ;;
    -h|--help)
        sed -n '7,14p' "$0" | sed 's/^# \{0,1\}//'
        exit 0 ;;
esac

# ── Run as the user: the window asks for the password itself when needed ──────
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    say "Run the Fingerprint Manager as yourself, not with sudo:\n  $HERE/fingerprint-manager.sh"
    exit 1
fi

# ── The fix must be installed ─────────────────────────────────────────────────
if [[ ! -f /etc/samsung-galaxybook-egismoc-sdcp.installed \
      || ! -f /usr/local/lib/libfprint-egismoc-sdcp/libfprint-2.so.2 ]]; then
    say "fingerprint-fix-sdcp is not installed. Install it first:\n  sudo bash $HERE/install.sh"
    exit 1
fi

# ── Packages the window needs ─────────────────────────────────────────────────
. /etc/os-release 2>/dev/null
case " ${ID,,} ${ID_LIKE,,} " in
    *" fedora "*)                 PM="sudo dnf install -y"; P_PY=python3; P_GI=python3-gobject; P_GTK=gtk3; P_FP=libfprint; P_PK=polkit ;;
    *" debian "*|*" ubuntu "*)    PM="sudo apt install -y"; P_PY=python3; P_GI=python3-gi; P_GTK=gir1.2-gtk-3.0; P_FP=gir1.2-fprint-2.0; P_PK=pkexec ;;
    *" arch "*)                   PM="sudo pacman -S --needed"; P_PY=python; P_GI=python-gobject; P_GTK=gtk3; P_FP=libfprint; P_PK=polkit ;;
    *)                            PM=""; P_PY=python3; P_GI="PyGObject"; P_GTK="GTK 3"; P_FP="libfprint introspection data"; P_PK=pkexec ;;
esac

missing=()
if ! command -v python3 >/dev/null 2>&1; then
    missing+=("$P_PY" "$P_GI" "$P_GTK" "$P_FP")
else
    python3 -c 'import gi' 2>/dev/null || missing+=("$P_GI")
    python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null \
        || missing+=("$P_GTK")
    python3 -c 'import gi; gi.require_version("FPrint", "2.0")' 2>/dev/null || missing+=("$P_FP")
fi
command -v pkexec >/dev/null 2>&1 || missing+=("$P_PK")
# keep each package once
mapfile -t missing < <(printf '%s\n' "${missing[@]}" | awk 'NF && !seen[$0]++')

if [[ ${#missing[@]} -gt 0 ]]; then
    if [[ -n "$PM" ]]; then
        cmd="$PM ${missing[*]}"
        if [[ -t 0 && -t 1 ]]; then
            echo "The Fingerprint Manager needs: ${missing[*]}"
            read -r -p "Install them now ($cmd)? [Y/n] " ans
            if [[ -z "$ans" || "${ans,,}" == y* ]]; then
                $cmd || { echo "Install failed — run it yourself: $cmd"; exit 1; }
            else
                exit 1
            fi
        else
            say "The Fingerprint Manager needs: ${missing[*]}\nInstall with:\n  $cmd"
            exit 1
        fi
    else
        say "The Fingerprint Manager needs: ${missing[*]}"
        exit 1
    fi
fi

[[ -f "$APP" ]] || { say "Missing $APP — keep the whole fingerprint-fix-sdcp folder together."; exit 1; }
exec python3 "$APP" "$@"
