#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book Fixes — Galaxy Book Fingerprint Manager (fingerprint-fix-sdcp)
# =============================================================================
# A small window for the fingerprints on this laptop's sensor:
#   • which fingers are enrolled on this install, and whether each one is
#     still stored on the sensor (or was wiped, e.g. by Windows)
#   • every template on the sensor, and which of them this install uses
#   • test a fingerprint, remove dead records, delete templates, wipe the sensor
#   • export / import fingerprints to share them with another install
#
#   galaxybook-fingerprint-manager   (installed by install.sh; also in the app
#                                     menu as "Galaxy Book Fingerprint Manager")
#   ./fingerprint-manager.sh         (from the fix folder, e.g. while developing)
#
# It asks for your password once (pkexec) to start fingerprint-manager-helper.py,
# which does the root work. Needs fingerprint-fix-sdcp installed, PyGObject
# with GTK 3, and libfprint's GObject introspection data.
# =============================================================================
import glob
import os
import shutil
import subprocess
import sys
import threading
import json
import re
import uuid

# The application ID. It makes the window a single instance (a second launch
# brings the running window forward instead), and on Wayland it is the
# window's app ID: the panel/taskbar takes the window's icon from the .desktop
# file with this name (install.sh installs it). It is also set as the program
# name before GTK starts, so X11 desktops match the window to it too.
APP_ID = "io.github.david_bartlett.GalaxyBookFingerprintManager"
ICON_NAME = "galaxybook-fingerprint-manager"     # the icon, and the settings folder name

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Galaxy Book Fingerprint Manager")
    from gi.repository import Gtk, Gdk, Gio, Pango
    Gdk.set_program_class(APP_ID)     # X11 WM_CLASS, matched by StartupWMClass
except (ImportError, ValueError) as e:
    sys.exit(f"Fingerprint Manager needs PyGObject with GTK 3 ({e}).\n"
             "  Fedora:  sudo dnf install python3-gobject gtk3\n"
             "  Debian / Ubuntu / Mint / MX:  sudo apt install python3-gi gir1.2-gtk-3.0\n"
             "  Arch / CachyOS:  sudo pacman -S python-gobject gtk3")

HERE = os.path.dirname(os.path.realpath(__file__))
HELPER = os.path.join(HERE, "fingerprint-manager-helper.py")
TITLE = "Galaxy Book Fingerprint Manager"
# The mark before each right-click menu option.
MENU_MARK = "›"


def app_version():
    """This copy's fingerprint-fix-sdcp version (the VERSION file next to lib/)."""
    try:
        with open(os.path.join(HERE, "..", "VERSION")) as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


# Where the fix installs the Manager, and the command that starts that copy
# (lib/fixpaths.sh: package layout first, then install.sh's). The running
# Manager watches these copies' VERSION files, so it notices a new version
# however it was installed — a software centre, dnf / apt / pacman, install.sh.
INSTALLED_COPIES = (("/usr/lib/fingerprint-fix-sdcp/manager", "/usr/bin/galaxybook-fingerprint-manager"),
                    ("/usr/local/lib/libfprint-egismoc-sdcp/manager",
                     "/usr/local/bin/galaxybook-fingerprint-manager"))


# install.sh's own clean-up (lib/fixpaths.sh, local layout): removes that copy
# without asking, keeping enrolled fingerprints.
LOCAL_CLEANUP = "/usr/local/bin/samsung-galaxybook-fprint-sdcp-cleanup.sh"


def installed_copy():
    """(version, command) of the installed Manager, package first; (None, None)."""
    for folder, command in INSTALLED_COPIES:
        try:
            with open(os.path.join(folder, "VERSION")) as f:
                version = f.read().strip()
        except OSError:
            continue
        if version:
            return version, command
    return None, None


def parse_marker(marker):
    """(installed version, driver commit, driver date) from the install marker:
    '<commit> <date> <source> … (installed <date>) fingerprint-fix-sdcp <version>'.
    Installs from before versions existed have no version."""
    parts = (marker or "").split()
    m = re.search(r"fingerprint-fix-sdcp (\S+)", marker or "")
    return (m.group(1) if m else None,
            parts[0] if parts else None,
            parts[1] if len(parts) > 1 else None)
EXPORT_NAME = "fingerprint-export.tgz"
# Cards view: all ten fingers, right hand then left (index … little, thumb).
GRID_FINGERS = ["right-index-finger", "right-middle-finger", "right-ring-finger",
                "right-little-finger", "right-thumb", "left-index-finger",
                "left-middle-finger", "left-ring-finger", "left-little-finger", "left-thumb"]
FINGERS = ["right-index-finger", "right-middle-finger", "right-thumb", "right-ring-finger",
           "right-little-finger", "left-index-finger", "left-middle-finger", "left-thumb",
           "left-ring-finger", "left-little-finger"]
GREEN, RED, AMBER = "#26a269", "#c01c28", "#e5a50a"


def reader_present():
    """True when the Galaxy Book's Egis reader (1c7a:05a5 / 1c7a:05a1) is on USB.
    The same rule as packaging/files/fprintd-env.sh.in, which keeps fprintd on
    the distro libfprint without it. Read from sysfs: no password needed."""
    for d in glob.glob("/sys/bus/usb/devices/*"):
        try:
            with open(os.path.join(d, "idVendor")) as f:
                if f.read().strip() != "1c7a":
                    continue
            with open(os.path.join(d, "idProduct")) as f:
                if f.read().strip() in ("05a5", "05a1"):
                    return True
        except OSError:
            continue
    return False


def remove_command():
    """How to remove the fix the way it was installed."""
    if os.path.isfile("/usr/lib/fingerprint-fix-sdcp/installed"):
        for tool, cmd in (("dnf", "sudo dnf remove fingerprint-fix-sdcp"),
                          ("pacman", "sudo pacman -R fingerprint-fix-sdcp"),
                          ("apt", "sudo apt remove fingerprint-fix-sdcp")):
            if shutil.which(tool):
                return cmd
    return "sudo bash uninstall.sh   (in the fingerprint-fix-sdcp folder)"


def no_reader_dialog():
    """Explain, without asking for a password, that this computer doesn't have
    the reader this app is for."""
    dlg = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE,
                            text="No Galaxy Book fingerprint reader found")
    dlg.set_title(TITLE)
    dlg.set_icon_name(ICON_NAME)
    dlg.format_secondary_markup(
        "This app and fingerprint-fix-sdcp are only for the Egis fingerprint reader of "
        "Samsung Galaxy Book 3, 4 and 5 laptops (USB <tt>1c7a:05a5</tt> or <tt>1c7a:05a1</tt>), "
        "and it isn't on this computer.\n\n"
        "Without it, fprintd uses your distro's own driver, so any other fingerprint reader "
        "keeps working: set it up in your desktop's settings.\n\n"
        "If this is a Galaxy Book, the reader may be switched off in the BIOS — check, then "
        "restart. Otherwise you can remove the fix:\n"
        f"<tt>{GLib.markup_escape_text(remove_command())}</tt>")
    dlg.run()
    dlg.destroy()


class NoAccess(RuntimeError):
    """The root helper couldn't start: no administrator access was given."""


# ── The root helper, started once ─────────────────────────────────────────────
class Helper:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        py = sys.executable or shutil.which("python3")
        if os.geteuid() == 0:
            cmd = [py, HELPER]
        else:
            if not shutil.which("pkexec"):
                raise RuntimeError("pkexec is not installed (it comes with polkit).")
            # Run the helper itself (not "python3 helper"), so polkit can show
            # this app's own message: install.sh installs a policy for the
            # installed helper's path.
            cmd = ["pkexec", HELPER] if os.access(HELPER, os.X_OK) else ["pkexec", py, HELPER]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
        line = self.proc.stdout.readline()
        if not line:
            err = (self.proc.stderr.read() or "").strip()
            rc = self.proc.wait()
            self.proc = None
            if "authentication agent" in err.lower():
                raise NoAccess("No password prompt is available: this desktop has no polkit "
                               "authentication agent running. Start one (e.g. polkit-gnome or "
                               "lxpolkit) or log in to a full desktop.")
            if rc in (126, 127):
                raise NoAccess("The password prompt was cancelled or the password was refused.")
            raise RuntimeError(err or f"The helper did not start (exit code {rc}).")

    def call(self, action, **kw):
        with self.lock:
            self.start()
            self.proc.stdin.write(json.dumps(dict(kw, action=action)) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                err = (self.proc.stderr.read() or "").strip()
                self.proc = None
                raise RuntimeError(err or "The helper stopped unexpectedly.")
            reply = json.loads(line)
            if not reply.get("ok"):
                raise RuntimeError(reply.get("error") or "Unknown error")
            return reply["result"]

    def cancel(self):
        """Stop a running fingerprint test (no reply; the test call returns)."""
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write(json.dumps({"action": "cancel"}) + "\n")
                self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            except Exception:
                pass


# ── Window ────────────────────────────────────────────────────────────────────
CSS = b"""
/* The Update button stands out like the suggested buttons in galaxybook-tools-gui:
   a red ring with a soft glow, bold text ("button." beats the theme's own shadow) */
button.fpm-update { border-color: #e74c3c; font-weight: bold; margin: 0 4px;
    box-shadow: 0 0 0 1px rgba(231,76,60,0.85), 0 0 6px rgba(231,76,60,0.45); }
button.fpm-update:hover { box-shadow: 0 0 0 1px rgba(231,76,60,1.0), 0 0 8px rgba(231,76,60,0.6); }
button.fpm-update:disabled { box-shadow: none; font-weight: normal; }
.fpm-card { border: 1px solid alpha(currentColor, 0.15); border-radius: 8px; padding: 10px 12px; }
.fpm-hint { font-size: 100%; }
menu.fpm-menu { padding: 3px 0; min-width: 0; background-color: @theme_bg_color; }
menu.fpm-menu menuitem { padding: 5px 14px 5px 10px; min-width: 0; min-height: 0; }
menu.fpm-menu separator.fpm-menu-sep { margin: 2px 6px; min-height: 0; padding: 0; background: none;
    border-top: 1px solid shade(@theme_bg_color, 0.75);
    border-bottom: 1px solid shade(@theme_bg_color, 1.25); }
.fpm-status { font-size: 100%; }
.fpm-soft { color: alpha(@theme_fg_color, 0.72); }   /* easier to read than dim-label */
.fpm-fcard { background-color: @theme_base_color; border: 1px solid alpha(@theme_fg_color, 0.15);
             border-radius: 10px; padding: 10px 6px 9px 6px; }
.fpm-add { background-color: transparent; border: 1px dashed @theme_selected_bg_color; }
.fpm-add label { color: @theme_selected_bg_color; }
.fpm-plus { font-size: 26px; }
.fpm-lcard { background-color: @theme_base_color; border: 1px solid alpha(@theme_fg_color, 0.15);
             border-radius: 8px; padding: 6px 10px; }
.fpm-name { font-weight: bold; }
.fpm-small { font-size: 85%; }
.fpm-pill { border-radius: 9px; padding: 1px 8px; font-size: 85%; font-weight: bold; }
.fpm-ok { background-color: alpha(#26a269, 0.18); color: #26a269; }
.fpm-dead { background-color: alpha(#e01b24, 0.16); color: #e01b24; }
.fpm-unknown { background-color: alpha(@theme_fg_color, 0.10); }
.fpm-removed { background-color: alpha(#e5a50a, 0.20); color: #9c6e00; }
flowbox.fpm-cards, list.fpm-list { background-color: transparent; }
flowbox.fpm-cards flowboxchild { padding: 3px; background-color: transparent; }
flowbox.fpm-cards flowboxchild:selected { background-color: transparent; }
flowbox.fpm-cards flowboxchild.fpm-selected .fpm-fcard { border: 2px solid @theme_selected_bg_color; padding: 9px 5px 8px 5px;
                                                       background-color: alpha(@theme_selected_bg_color, 0.08); }
list.fpm-list row { padding: 0; margin-bottom: 6px; background-color: transparent; }
list.fpm-list row:selected, list.fpm-list row:hover, list.fpm-list row:active { background-color: transparent; }
list.fpm-list row.fpm-selected .fpm-lcard { border-color: @theme_selected_bg_color;
                                        background-color: alpha(@theme_selected_bg_color, 0.10); }
.fpm-empty { background-color: transparent; border: 1px dashed alpha(@theme_fg_color, 0.30); }
.fpm-empty label { color: alpha(@theme_fg_color, 0.55); }
.fpm-free { background-color: transparent; border: 1px dashed alpha(@theme_fg_color, 0.30); }
.fpm-free label { color: alpha(@theme_fg_color, 0.45); }
.fpm-id { font-family: monospace; font-size: 80%; }
.fpm-slots { font-weight: bold; }
"""

# The egismoc sensor stores up to this many templates (EGISMOC_MAX_ENROLL_NUM).
SENSOR_SLOTS = 10

# ── Windows on the same laptop ───────────────────────────────────────────────
# Windows Hello deletes the sensor templates it didn't create when Windows
# starts with the reader enabled, so a Linux install sharing the laptop with
# Windows loses its fingerprints unless the reader is disabled in Windows.
# Detected without a password and without mounting anything: a UEFI boot entry
# for Windows Boot Manager whose partition still exists, and Windows' own
# partitions (an NTFS / BitLocker one plus the Microsoft Reserved or Windows
# Recovery partition only the Windows installer makes).
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"   # vendor GUID of the Boot#### variables
WINDOWS_PART_TYPES = ("e3c9e316-0b5c-4db8-817d-f92df00215ae",   # Microsoft Reserved
                      "de94bba4-06d1-4d40-a16a-bfd50179d6ac")   # Windows Recovery
WINDOWS_TIP = ("When Windows starts with the fingerprint reader enabled, Windows Hello deletes "
               "the fingerprints it didn't create — including your Linux ones.\n\n"
               "In Windows, open Device Manager → Biometric devices, right-click the fingerprint "
               "sensor and choose Disable device. Linux then keeps its fingerprints.\n\n"
               "If they do disappear, a notification tells you at the next login, and you can "
               "enrol them again.")


def efi_boot_entries():
    """[(description, partition GUID or None, file path or None)] of the UEFI
    boot entries this user can read; None when there are none to read (legacy
    boot, or the firmware variables aren't readable)."""
    entries, seen = [], False
    for path in glob.glob(f"/sys/firmware/efi/efivars/Boot[0-9A-Fa-f][0-9A-Fa-f]"
                          f"[0-9A-Fa-f][0-9A-Fa-f]-{EFI_GLOBAL}"):
        try:
            with open(path, "rb") as f:
                data = f.read()[4:]               # skip efivarfs' attribute word
        except OSError:
            continue
        seen = True
        if len(data) < 8:
            continue
        # EFI_LOAD_OPTION: attributes (4), device path length (2), UTF-16
        # description ending in a NUL, then the device path.
        dp_len = int.from_bytes(data[4:6], "little")
        end = 6
        while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
            end += 2
        desc = data[6:end].decode("utf-16-le", "replace")
        dp = data[end + 2:end + 2 + dp_len]
        guid = file = None
        i = 0
        while i + 4 <= len(dp):
            kind, subkind = dp[i], dp[i + 1]
            length = int.from_bytes(dp[i + 2:i + 4], "little")
            if length < 4 or kind == 0x7F:            # bad node, or end of path
                break
            node = dp[i:i + length]
            if kind == 4 and subkind == 1 and length >= 42 and node[41] == 2:
                guid = str(uuid.UUID(bytes_le=bytes(node[24:40])))    # GPT partition
            elif kind == 4 and subkind == 4:
                file = node[4:].decode("utf-16-le", "replace").rstrip("\0")
            i += length
        entries.append((desc, guid, file))
    return entries if seen else None


def windows_partitions():
    """True when a disk has Windows' partitions: NTFS or BitLocker, plus the
    Microsoft Reserved or Windows Recovery partition."""
    try:
        out = subprocess.run(["lsblk", "-J", "-l", "-o", "FSTYPE,PARTTYPE"], capture_output=True,
                             text=True, timeout=5).stdout
        devs = json.loads(out).get("blockdevices", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    fs = any((d.get("fstype") or "").lower() in ("ntfs", "bitlocker") for d in devs)
    marker = any((d.get("parttype") or "").lower() in WINDOWS_PART_TYPES for d in devs)
    return fs and marker


def windows_installed():
    """Best guess, without root, whether Windows is installed on this laptop."""
    entries = efi_boot_entries()
    if entries is not None:
        def is_windows(desc, file):
            return ("windows boot manager" in desc.lower()
                    or "\\microsoft\\boot\\bootmgfw.efi" in (file or "").lower())
        if not any(is_windows(d, f) and (g is None or os.path.exists(f"/dev/disk/by-partuuid/{g}"))
                   for d, g, f in entries):
            return False                         # no Windows entry, or only a stale one
    return windows_partitions()


# ── fingerprint pictures, names and the remembered view ─────────────────────
SETTINGS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        ICON_NAME, "settings")


def load_settings():
    """key=value lines: view (icons/list), sensor_tab (1 = shown)."""
    try:
        with open(SETTINGS) as f:
            return dict(l.strip().split("=", 1) for l in f if "=" in l)
    except OSError:
        return {}


def save_setting(key, value):
    try:
        cfg = load_settings()
        cfg[key] = str(value)
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w") as f:
            f.writelines(f"{k}={v}\n" for k, v in cfg.items())
    except OSError:
        pass


def load_view():
    return "list" if load_settings().get("view") == "list" else "icons"


def save_view(view):
    save_setting("view", view)


# ── new releases on GitHub: lib/update_check.py, shared with the login check ─
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import update_check  # noqa: E402


# The fingerprint drawing (64×64 units): start point, then cubic segments.
FP_PATHS = [
    ((14, 22), [(19, 12, 32, 8, 42, 12), (47, 14, 51, 18, 53, 23)]),
    ((12, 33), [(12, 23, 21, 17, 31, 17), (42, 17, 50, 24, 50, 33), (50, 37, 49.5, 40, 48.5, 43)]),
    ((18, 47), [(16, 42, 17, 35, 19, 31), (22, 25, 28, 23, 33, 24.5), (38, 26, 41, 30, 41, 35),
                (41, 40, 40, 45, 38, 49)]),
    ((24, 50), [(22, 45, 22, 39, 24, 34), (25.5, 30.5, 28.5, 29, 31.5, 30), (34.5, 31, 35.5, 34, 35.5, 37),
                (35.5, 42, 34, 47, 32, 51)]),
    ((30, 36), [(30.5, 42, 29.5, 47, 27, 52)]),
]
FP_COLOURS = {"ok": (0.149, 0.635, 0.412), "dead": (0.878, 0.106, 0.141),
              "unknown": (0.60, 0.60, 0.59), "empty": (0.74, 0.74, 0.73), "add": (0.208, 0.518, 0.894)}


try:                                  # drawing needs PyGObject's cairo support
    gi.require_foreign("cairo")
    HAVE_CAIRO = True
except Exception:                     # (python3-gi-cairo on Debian/Ubuntu)
    HAVE_CAIRO = False


class FingerprintIcon(Gtk.DrawingArea):
    def __init__(self, kind, size):
        super().__init__()
        self.kind = kind
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        if HAVE_CAIRO:
            self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        sc = min(w, h) / 46.0                       # the drawing spans about 46 units
        cr.translate(w / 2 - 32.5 * sc, h / 2 - 30 * sc)
        cr.scale(sc, sc)
        cr.set_source_rgb(*FP_COLOURS.get(self.kind, FP_COLOURS["unknown"]))
        cr.set_line_width(3.2)
        cr.set_line_cap(1)                          # round
        for (x, y), segs in FP_PATHS:
            cr.move_to(x, y)
            for seg in segs:
                cr.curve_to(*seg)
            cr.stroke()
        return False


def short_finger(name):
    """right-index-finger -> Right index; left-thumb -> Left thumb"""
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] in ("left", "right"):
        return f"{parts[0].capitalize()} {parts[1]}"
    return name


def os_name():
    """Short name of this install's distro, from /etc/os-release:
    "Fedora Linux" -> Fedora, "Ubuntu" -> Ubuntu, "Linux Mint" -> Linux Mint,
    "CachyOS Linux" -> CachyOS, "Debian GNU/Linux" -> Debian."""
    if os.path.exists("/etc/mx-version"):           # MX keeps Debian's os-release
        return "MX Linux"
    fields = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                fields[k] = v.strip('"\'')
    except OSError:
        pass
    name = fields.get("NAME") or fields.get("ID", "").capitalize()
    for suffix in (" GNU/Linux", " Linux"):
        if name.endswith(suffix) and name != suffix.strip():
            name = name[: -len(suffix)]
    return name.strip() or "this install"


OS_NAME = os_name()


def _login_screen():
    """The display manager, from display-manager.service: gdm, sddm,
    plasmalogin, lightdm… ('' when unknown)."""
    try:
        target = os.path.realpath("/etc/systemd/system/display-manager.service")
        return os.path.basename(target).split(".")[0].lower()
    except OSError:
        return ""


def pam_scope(method):
    """(title, tooltip) for the fingerprint switch: what it covers here. It
    depends on the login screen and desktop as well as the PAM tool.
    Checked: GDM; Linux Mint (Fingwit); Fedora KDE (authselect: the lock
    screen follows it, SDDM / Plasma Login don't take fingerprints);
    Arch / CachyOS (arch-pam.sh sets sudo and polkit-1 only, KDE's lock
    screen uses its own kde-fingerprint stack)."""
    dm = _login_screen()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    kde = "kde" in desktop or dm in ("sddm", "plasmalogin")
    mint = os.path.exists("/etc/linuxmint/info")
    admin = "sudo and admin prompts (pkexec, polkit)"
    if method == "arch-pam.sh":
        tip = f"Covers {admin}."
        if kde:
            tip += (" KDE's lock screen accepts your fingerprint on its own, whether this is "
                    "on or off; KDE's login screen doesn't support fingerprints.")
        return "Use fingerprint for sudo and admin prompts", tip
    if kde:
        return ("Use fingerprint for the lock screen and sudo",
                f"Covers the lock screen and {admin}. KDE's login screen doesn't support "
                "fingerprints, so it always asks for your password.")
    if dm == "gdm" or mint:
        return ("Use fingerprint for login, the lock screen and sudo",
                f"Covers the login screen, the lock screen and {admin}.")
    return ("Use fingerprint for sudo and admin prompts",
            f"Covers {admin}. The login and lock screens may accept it too, if they "
            "support fingerprints.")


def long_finger(name):
    """right-index-finger -> Right index finger"""
    return name.replace("-", " ").capitalize()


def nice_date(d, year=False):
    try:
        import datetime
        return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%-d %b %Y" if year else "%-d %b")
    except (ValueError, TypeError):
        return d or ""


def rec_kind(r):
    if r.get("error"):
        return "unknown", "Unreadable"
    return ("ok", "On the sensor") if r["on_sensor"] else ("dead", "Gone from sensor")


def summarise(text):
    """One line from a script's output: its last [INFO]/[ERROR] line, or the
    last line. The full text is kept for the Details button."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    tagged = [l for l in lines if l.startswith(("[INFO]", "[ERROR]", "[WARN]"))]
    pick = (tagged or lines or [""])[-1]
    for tag in ("[INFO]", "[ERROR]", "[WARN]"):
        pick = pick.replace(tag, "").strip()
    return pick


class Manager(Gtk.Window):
    def __init__(self, application=None):
        super().__init__(title=TITLE, application=application)
        self.set_default_size(620, -1)     # height: the Sensor tab plus room for a message
        self.set_icon_name(ICON_NAME)
        self.helper = Helper()
        self.status = None
        self.busy = False
        self._pam_syncing = False
        self._msg_timer = 0
        self._msg_details = None

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # ── header bar: refresh · [Fingerprints | Sensor] · menu ──
        hb = Gtk.HeaderBar(show_close_button=True)
        self.set_titlebar(hb)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        # every page as tall as the tallest, so the window never changes height
        # The tabs; with the Sensor tab hidden (the default) just a title.
        self.switcher = Gtk.StackSwitcher(stack=self.stack)
        self.title_lbl = Gtk.Label(label="Fingerprints")
        self.title_lbl.get_style_context().add_class("title")
        title_box = Gtk.Box()
        title_box.pack_start(self.switcher, False, False, 0)
        title_box.pack_start(self.title_lbl, False, False, 0)
        hb.set_custom_title(title_box)
        self.refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_btn.set_tooltip_text("Read the sensor again")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh())
        hb.pack_start(self.refresh_btn)
        self.spinner = Gtk.Spinner()
        hb.pack_start(self.spinner)

        menu = Gtk.Menu()
        self.export_item = self._menu_item(menu, "Export fingerprints…", self.on_export)
        self.import_item = self._menu_item(menu, "Import fingerprints…", self.on_import)
        menu.append(Gtk.SeparatorMenuItem())
        self.restore_item = self._menu_item(menu, "Restore removed records…", self.on_restore)
        menu.append(Gtk.SeparatorMenuItem())
        self.sensor_item = Gtk.CheckMenuItem(label="Show the Sensor tab (advanced)")
        self.sensor_item.set_tooltip_text("Every template stored on the sensor — including other "
                                          "installs' and Windows Hello's — with delete and wipe")
        self.sensor_item.set_active(load_settings().get("sensor_tab") == "1")
        self.sensor_item.connect("toggled", lambda i: self._show_sensor_tab(i.get_active()))
        menu.append(self.sensor_item)
        self.update_item = Gtk.CheckMenuItem(label="Check for new versions")
        self.update_item.set_tooltip_text("Asks GitHub each time the Manager starts whether "
                                          "a newer fingerprint-fix-sdcp has been released")
        self.update_item.set_active(load_settings().get("update_check", "1") == "1")
        self.update_item.connect("toggled", self._on_update_toggled)
        menu.append(self.update_item)
        self.windows_item = Gtk.CheckMenuItem(label="Remind me about Windows")
        self.windows_item.set_tooltip_text("When Windows is installed on this laptop, show a "
                                           "reminder to disable its fingerprint reader there")
        self.windows_item.set_active(load_settings().get("windows_hint", "1") == "1")
        self.windows_item.connect("toggled", self._on_windows_toggled)
        self.windows_item.set_no_show_all(True)     # only shown once Windows is found
        menu.append(self.windows_item)
        menu.append(Gtk.SeparatorMenuItem())
        self._menu_item(menu, "About", self.on_about)
        menu.show_all()
        self.menu_btn = Gtk.MenuButton(popup=menu)
        self.menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        self.menu_btn.set_tooltip_text("Export, import, restore")
        hb.pack_end(self.menu_btn)
        # Shown only when a newer release exists (see check_for_update)
        self.update_btn = Gtk.Button(label="Update")
        self.update_btn.set_image(Gtk.Image.new_from_icon_name("software-update-available-symbolic",
                                                               Gtk.IconSize.BUTTON))
        self.update_btn.set_always_show_image(True)
        self.update_btn.get_style_context().add_class("fpm-update")
        self.update_btn.set_valign(Gtk.Align.CENTER)   # the tabs' height, not the header bar's
        self.update_btn.connect("clicked", self.on_update)
        self.update_btn.set_no_show_all(True)
        self._new_version = None
        self._new_assets = []
        self._export_offered = None
        hb.pack_end(self.update_btn)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.add(outer)

        # ── top card: login/sudo switch + sensor line ──
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.get_style_context().add_class("fpm-card")
        row = Gtk.Box(spacing=12)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pam_title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self._set_pam_title("")
        texts.pack_start(self.pam_title, False, False, 0)
        self.pam_detail = Gtk.Label(xalign=0, wrap=True)
        self.pam_detail.get_style_context().add_class("fpm-soft")
        self.pam_detail.get_style_context().add_class("fpm-hint")
        texts.pack_start(self.pam_detail, False, False, 0)
        row.pack_start(texts, True, True, 0)
        self.pam_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.pam_switch.connect("state-set", self.on_pam_switch)
        row.pack_end(self.pam_switch, False, False, 0)
        card.pack_start(row, False, False, 0)
        card.pack_start(Gtk.Separator(), False, False, 0)
        self.info = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.info.get_style_context().add_class("fpm-soft")
        self.info.get_style_context().add_class("fpm-status")
        card.pack_start(self.info, False, False, 0)
        # Windows on the same laptop: a reminder to disable the reader there, at
        # the bottom of the window, under the buttons. Hidden until the check
        # (run once the window is up) finds Windows.
        self.win_row = Gtk.Box(spacing=8)
        win_label = Gtk.Label(xalign=0, wrap=True)
        win_label.set_markup(f'<span foreground="{AMBER}" weight="bold">⚠</span>  Windows found on '
                             "this laptop — disable its fingerprint reader there")
        win_label.get_style_context().add_class("fpm-status")
        win_label.set_tooltip_text(WINDOWS_TIP)
        self.win_row.pack_start(win_label, True, True, 0)
        win_ok = Gtk.Button(label="Got it", relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER)
        win_ok.set_tooltip_text("Hide this reminder (Menu → Remind me about Windows brings it back)")
        win_ok.connect("clicked", lambda *_: self.windows_item.set_active(False))
        self.win_row.pack_end(win_ok, False, False, 0)
        self.win_row.show_all()
        self.win_row.set_no_show_all(True)
        self.win_row.hide()
        self._windows = False
        outer.pack_start(card, False, False, 0)

        # ── message bar: one short line, Details… for the full text ──
        self.msg_bar = Gtk.InfoBar(show_close_button=True)
        self.msg_bar.connect("response", self._on_msg_response)
        self.msg_label = Gtk.Label(xalign=0, wrap=True, lines=2,
                                   ellipsize=Pango.EllipsizeMode.END)
        msg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        msg_box.pack_start(self.msg_label, False, False, 0)
        msg_btns = Gtk.Box(spacing=6)
        self.msg_action_btn = Gtk.Button(label="")
        self.msg_action_btn.connect("clicked", lambda *_: self._on_msg_response(None, 2))
        msg_btns.pack_start(self.msg_action_btn, False, False, 0)
        self.msg_details_btn = Gtk.Button(label="Details…")
        self.msg_details_btn.connect("clicked", lambda *_: self._on_msg_response(None, 1))
        msg_btns.pack_start(self.msg_details_btn, False, False, 0)
        msg_box.pack_start(msg_btns, False, False, 0)
        self.msg_bar.get_content_area().add(msg_box)
        self.msg_bar.set_no_show_all(True)
        msg_box.show_all()
        self._msg_action = None

        outer.pack_start(self.stack, True, True, 0)
        # Messages go at the bottom, in a slot that always keeps their room, so
        # nothing moves or resizes when one appears.
        self.msg_slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.msg_slot.pack_end(self.msg_bar, False, False, 0)   # just above the buttons
        outer.pack_start(self.msg_slot, False, False, 0)
        # Each tab's buttons sit under the message slot, at the very bottom.
        self.btn_stack = Gtk.Stack()
        outer.pack_start(self.btn_stack, False, False, 0)
        outer.pack_start(self.win_row, False, False, 0)
        self.stack.connect("notify::visible-child-name",
                           lambda st, _p: self.btn_stack.set_visible_child_name(
                               st.get_visible_child_name()))

        # ── page 1: fingerprints on this install — cards (icons) or rows (list) ──
        self.records = []                 # the status records shown, in order
        self.sel_keys = set()             # selected (user, finger) — shared by both views
        self._syncing_sel = False
        self.enrol_ok = False
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top = Gtk.Box(spacing=6)
        hint = Gtk.Label(label="Test: double-click · Enrol: click a grey finger · More: right-click",
                         xalign=0, wrap=True)
        hint.get_style_context().add_class("fpm-hint")
        top.pack_start(hint, True, True, 0)
        self.view_switches = []           # (cards button, list button) per tab
        switch, self.view_icons, self.view_list = self._view_switch()
        top.pack_end(switch, False, False, 0)
        # In a card like the one above, so the hint lines up with its text.
        hint_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hint_card.get_style_context().add_class("fpm-card")
        hint_card.pack_start(top, False, False, 0)
        page.pack_start(hint_card, False, False, 0)
        self.others_note = Gtk.Label(xalign=0, wrap=True)   # other users: list view only
        self.others_note.get_style_context().add_class("dim-label")
        self.others_note.get_style_context().add_class("fpm-hint")
        self.others_note.set_no_show_all(True)
        page.pack_start(self.others_note, False, False, 0)

        # Selection is ours, not GTK's: a click toggles a card/row on and off.
        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                 min_children_per_line=5, max_children_per_line=5,
                                 column_spacing=4, row_spacing=4, valign=Gtk.Align.START,
                                 activate_on_single_click=True)
        self.cards.get_style_context().add_class("fpm-cards")
        self.cards.connect("child-activated", self._on_card_clicked)
        self.cards.connect("button-press-event", self._on_fingers_double_click)
        self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                activate_on_single_click=True)
        self.rows.get_style_context().add_class("fpm-list")
        self.rows.connect("row-activated", self._on_card_clicked)
        self.rows.connect("button-press-event", self._on_fingers_double_click)
        self.rec_views = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        # every page as tall as the tallest, so the window never changes height
        for name, widget in (("icons", self.cards), ("list", self.rows)):
            # Cards: always both rows in full, never a scroll bar. Lists: as
            # tall as the cards, scrolling if there are more rows than fit.
            cards = name == "icons"
            sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                    vscrollbar_policy=Gtk.PolicyType.NEVER if cards
                                    else Gtk.PolicyType.AUTOMATIC)
            if not cards:
                sw.set_min_content_height(200)
            sw.add(widget)
            self.rec_views.add_named(sw, name)
        page.pack_start(self.rec_views, True, True, 0)

        row = Gtk.Box(spacing=6)
        self.test_btn = self._button(row, "Test all fingerprints", self.on_test,
                                     "Touch the sensor with any of your fingers — checked against "
                                     "all of them, as login and sudo do. Double-click a finger to "
                                     "test just that one.")
        # Remove is in the right-click menu (and the Delete key), not a button.
        for w in (self.cards, self.rows):
            w.connect("key-press-event", self._on_fingers_key)
        self.btn_stack.add_named(row, "fingers")
        self.stack.add_titled(page, "fingers", "Fingerprints")

        # ── page 2: templates on the sensor — cards with free slots, or a list ──
        self.templates = []
        self.tsel = set()                 # selected template ids
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top = Gtk.Box(spacing=6)
        self.slots_label = Gtk.Label(xalign=0)
        self.slots_label.get_style_context().add_class("fpm-slots")
        top.pack_start(self.slots_label, True, True, 0)
        switch, self.tview_icons, self.tview_list = self._view_switch()
        top.pack_end(switch, False, False, 0)
        # Slots, bar and key together in a card like the one above.
        slots_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        slots_card.get_style_context().add_class("fpm-card")
        slots_card.pack_start(top, False, False, 0)
        self.slots_bar = Gtk.ProgressBar()
        slots_card.pack_start(self.slots_bar, False, False, 0)
        hint = Gtk.Label(label=f"Green: used by {OS_NAME} · Grey: another distro, Windows Hello "
                               "or a reinstall · Removed here: can be restored · Dashed: free · "
                               "More: right-click", xalign=0, wrap=True)
        hint.get_style_context().add_class("fpm-hint")
        slots_card.pack_start(hint, False, False, 0)
        page.pack_start(slots_card, False, False, 0)
        self.tcards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                  min_children_per_line=5, max_children_per_line=5,
                                  column_spacing=4, row_spacing=4, valign=Gtk.Align.START,
                                  activate_on_single_click=True)
        self.tcards.get_style_context().add_class("fpm-cards")
        self.tcards.connect("child-activated", self._on_tcard_clicked)
        self.tcards.connect("button-press-event", self._tpl_menu)
        self.trows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                 activate_on_single_click=True)
        self.trows.get_style_context().add_class("fpm-list")
        self.trows.connect("row-activated", self._on_tcard_clicked)
        self.trows.connect("button-press-event", self._tpl_menu)
        self.tpl_views = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        # every page as tall as the tallest, so the window never changes height
        for name, widget in (("icons", self.tcards), ("list", self.trows)):
            # Cards: always both rows in full, never a scroll bar. Lists: as
            # tall as the cards, scrolling if there are more rows than fit.
            cards = name == "icons"
            sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                    vscrollbar_policy=Gtk.PolicyType.NEVER if cards
                                    else Gtk.PolicyType.AUTOMATIC)
            if not cards:
                sw.set_min_content_height(200)
            sw.add(widget)
            self.tpl_views.add_named(sw, name)
        page.pack_start(self.tpl_views, True, True, 0)
        row = Gtk.Box(spacing=6)
        self.del_btn = self._button(row, "Delete…", self.on_delete_templates,
                                    "Delete the selected templates from the sensor")
        self.wipe_btn = Gtk.Button(label="Wipe sensor…")
        self.wipe_btn.get_style_context().add_class("destructive-action")
        self.wipe_btn.set_tooltip_text("Delete every template on the sensor — every install and Windows")
        self.wipe_btn.connect("clicked", self.on_wipe)
        row.pack_end(self.wipe_btn, False, False, 0)
        self.btn_stack.add_named(row, "sensor")
        self.stack.add_titled(page, "sensor", "Sensor")
        self.sensor_page = page
        self.pages = {"fingers": "Fingerprints", "sensor": "Sensor"}

        self._set_view(load_view(), save=False)
        self.connect("destroy", self.on_quit)
        self.show_all()
        self._show_sensor_tab(self.sensor_item.get_active(), save=False)
        self.message("Measuring the message area: ",
                     Gtk.MessageType.WARNING,
                     details="x", action=("Undo", lambda: None))
        self.msg_slot.set_size_request(-1, self.msg_bar.get_preferred_height_for_width(596)[1])
        self._hide_message()
        self._set_view(load_view(), save=False)
        self._update_buttons()
        GLib.idle_add(self.refresh)
        GLib.idle_add(self._check_windows)
        if self.update_item.get_active():
            self.check_for_update(max_age=0)        # once, at start-up
        self._watch_install()

    # ── building blocks ──
    def _table(self, store, titles):
        view = Gtk.TreeView(model=store)
        view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        for i, t in enumerate(titles):
            last = i == len(titles) - 1
            cell = Gtk.CellRendererText(
                ellipsize=Pango.EllipsizeMode.END if last else Pango.EllipsizeMode.NONE)
            col = Gtk.TreeViewColumn(t, cell, text=i)
            col.set_resizable(True)
            col.set_expand(last)
            view.append_column(col)
        return view

    def _page(self, view, hint):
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        h = Gtk.Label(label=hint, xalign=0, wrap=True)
        h.get_style_context().add_class("dim-label")
        h.get_style_context().add_class("fpm-hint")
        vb.pack_start(h, False, False, 0)
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.set_min_content_height(160)
        sw.add(view)
        vb.pack_start(sw, True, True, 0)
        return vb

    def _section(self, title, view, hint):            # used by dialogs
        return self._page(view, hint)

    def _button(self, row, label, cb, tip):
        b = Gtk.Button(label=label)
        b.set_tooltip_text(tip)
        b.connect("clicked", cb)
        row.pack_start(b, False, False, 0)
        return b

    def _menu_item(self, menu, label, cb):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", cb)
        menu.append(item)
        return item

    def _selected(self, view, col):
        model, paths = view.get_selection().get_selected_rows()
        return [model[p] for p in paths]

    # ── fingerprint cards / rows ──
    def _selected_recs(self):
        """Selected records as [user, short name, enrolled, state, finger no., on sensor]."""
        out = []
        for r in self.records:
            if (r["user"], r["finger"]) in self.sel_keys:
                out.append([r["user"], r["name"], r["enrolled"], rec_kind(r)[1], r["finger"],
                            1 if r["on_sensor"] else 0])
        return out

    def _view_switch(self):
        """A linked Cards | List button pair. Both tabs share the choice."""
        box = Gtk.Box()
        box.get_style_context().add_class("linked")
        icons = Gtk.RadioButton(draw_indicator=False)
        self._icon_or_text(icons, ["view-grid-symbolic", "view-app-grid-symbolic",
                                   "view-list-icons-symbolic", "view-grid"], "▦")
        icons.set_tooltip_text("Cards")
        lst = Gtk.RadioButton(group=icons, draw_indicator=False)
        self._icon_or_text(lst, ["view-list-symbolic", "view-list-details-symbolic",
                                 "view-list-details", "view-list-text"], "☰")
        lst.set_tooltip_text("List")
        box.pack_start(icons, False, False, 0)
        box.pack_start(lst, False, False, 0)
        icons.connect("toggled", lambda b: self._set_view("icons" if b.get_active() else "list"))
        self.view_switches.append((icons, lst))
        return box, icons, lst

    def _show_sensor_tab(self, show, save=True):
        """The Sensor tab is for troubleshooting, so it's hidden unless chosen."""
        if not show and self.stack.get_visible_child_name() == "sensor":
            self.stack.set_visible_child_name("fingers")
        # The page stays (unreachable) so the window keeps the Sensor tab's
        # height either way; only the tab buttons are hidden.
        self.switcher.set_visible(show)
        self.title_lbl.set_visible(not show)
        if save:
            save_setting("sensor_tab", 1 if show else 0)

    def _set_view(self, view, save=True):
        if getattr(self, "_setting_view", False):
            return
        self._setting_view = True
        for icons, lst in self.view_switches:
            (lst if view == "list" else icons).set_active(True)
        for stack in (getattr(self, "rec_views", None), getattr(self, "tpl_views", None)):
            if stack is not None and stack.get_child_by_name(view):
                stack.set_visible_child_name(view)
        self._setting_view = False
        if save:
            save_view(view)

    # ── sensor cards / rows ──
    def _selected_tpls(self):
        """Selected templates as [id, used-by text, used here (1/0)]."""
        return [[t["id"], ", ".join(t["used_by"]) or "Not used here", 1 if t["used_by"] else 0]
                for t in self.templates if t["id"] in self.tsel]

    @staticmethod
    def _mark(widget, on):
        ctx = widget.get_style_context()
        (ctx.add_class if on else ctx.remove_class)("fpm-selected")

    def _on_tcard_clicked(self, _box, child):
        """Click a template card or row: select it (only one at a time), or
        deselect it if it is already selected."""
        tid = getattr(child, "tid", None)
        if tid is None:                                   # a free slot
            return
        self._set_tsel(set() if tid in self.tsel else {tid})

    def _set_tsel(self, ids):
        self.tsel = set(ids)
        for w in self.tcards.get_children() + self.trows.get_children():
            self._mark(w, getattr(w, "tid", None) in self.tsel)
        self._update_buttons()

    def _tpl_tip(self, t):
        """Hover text for a template on the Sensor tab."""
        if t["used_by"]:
            return f"Template {t['id']} — used by {', '.join(t['used_by'])}"
        rm = t.get("removed")
        if rm:
            how = "removed from" if rm["kind"] == "removed" else "replaced on"
            return (f"Template {t['id']} — {rm['user']}'s {long_finger(rm['name']).lower()}, "
                    f"{how} {OS_NAME} on {nice_date(rm['date'], True)}. The template is still "
                    "on the sensor: right-click to restore it, or delete it to free the slot.")
        return (f"Template {t['id']} — not used by {OS_NAME}: probably another distro; "
                "it could also be Windows Hello's own, or left over from a reinstall")

    def _fill_templates(self, templates):
        self.templates = templates
        for w in self.tcards.get_children() + self.trows.get_children():
            w.destroy()
        used = len(templates)
        cap = max(SENSOR_SLOTS, used)
        self.slots_label.set_text(f"{used} of {cap} slots used" if templates or self.status else "")
        self.slots_bar.set_fraction(used / cap if cap else 0)
        for t in templates:
            owners = [u.split(" ", 1) for u in t["used_by"]]        # [user, finger]
            if owners:
                kind, pill = "ok", "Used here"
                title = short_finger(owners[0][1]) if len(owners[0]) > 1 else owners[0][0]
                sub = ", ".join(sorted({o[0] for o in owners}))
                long_title = long_finger(owners[0][1]) if len(owners[0]) > 1 else title
            elif t.get("removed"):
                rm = t["removed"]
                kind, pill = "unknown", "Removed here"
                title, long_title = short_finger(rm["name"]), long_finger(rm["name"])
                sub = (f"Removed from {OS_NAME}" if rm["kind"] == "removed"
                       else f"Replaced on {OS_NAME}")
            else:
                kind, pill = "unknown", "Not used here"
                title, long_title = "Unknown", "Unknown template"
                sub = "Another distro?"
            # card
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.get_style_context().add_class("fpm-fcard")
            box.pack_start(FingerprintIcon(kind, 40), False, False, 2)
            box.pack_start(self._label(title, "fpm-name", justify=Gtk.Justification.CENTER,
                                       wrap=True, max_width_chars=8), False, False, 0)
            card_sub = t["removed"]["user"] if t.get("removed") else sub   # cards are narrow
            box.pack_start(self._label(card_sub, "dim-label", "fpm-small", justify=Gtk.Justification.CENTER,
                                       ellipsize=Pango.EllipsizeMode.END, max_width_chars=10),
                           False, False, 0)
            box.pack_start(self._pill("removed" if t.get("removed") else kind, pill),
                           False, False, 4)
            child = Gtk.FlowBoxChild()
            child.tid = t["id"]
            child.set_tooltip_text(self._tpl_tip(t))
            child.add(box)
            self.tcards.add(child)
            # row
            hb = Gtk.Box(spacing=10)
            hb.get_style_context().add_class("fpm-lcard")
            hb.pack_start(FingerprintIcon(kind, 32), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            texts.pack_start(self._label(long_title, "fpm-name", xalign=0), False, False, 0)
            detail = (sub if owners or t.get("removed")
                      else "Another distro, Windows Hello, or left over from a reinstall?")
            texts.pack_start(self._label(f"{detail} · template {t['id']}", "dim-label", "fpm-small",
                                         xalign=0, ellipsize=Pango.EllipsizeMode.END), False, False, 0)
            hb.pack_start(texts, True, True, 0)
            hb.pack_start(self._pill("removed" if t.get("removed") else kind, pill),
                          False, False, 0)
            row = Gtk.ListBoxRow()
            row.tid = t["id"]
            row.set_tooltip_text(self._tpl_tip(t))
            row.add(hb)
            self.trows.add(row)
        # free slots (cards only)
        if self.status:
            for _ in range(max(0, cap - used)):
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                for c in ("fpm-fcard", "fpm-free"):
                    box.get_style_context().add_class(c)
                box.pack_start(self._label("·", "fpm-plus", height_request=40), False, False, 2)
                box.pack_start(self._label("Free", "fpm-name"), False, False, 0)
                child = Gtk.FlowBoxChild()
                child.is_free = True
                child.set_tooltip_text("A free slot on the sensor")
                child.add(box)
                self.tcards.add(child)
        self.tcards.show_all()
        self.trows.show_all()
        self._set_tsel({i for i in self.tsel if any(t["id"] == i for t in templates)})

    def _on_card_clicked(self, _box, child):
        """Click a finger card or row: select it (only one at a time), or
        deselect it if it is already selected. The Enrol card / row opens
        enrolment; a grey (not enrolled) finger opens it with that finger."""
        if getattr(child, "is_add", False) or getattr(child, "empty_finger", None):
            finger = getattr(child, "empty_finger", None)
            if self.enrol_ok and not getattr(self, "_enrol_pending", False):
                self._enrol_pending = True        # a double click opens it only once

                def open_enrol():
                    self._enrol_pending = False
                    self.on_enrol(None, finger=finger)
                    return False
                GLib.timeout_add(250, open_enrol)
            return
        key = getattr(child, "key", None)
        if key is not None:
            self._set_selection(set() if key in self.sel_keys else {key})

    def _on_fingers_double_click(self, widget, event):
        """Double-click a finger card or row: test that finger.
        Right-click: select it and show a menu."""
        if widget is self.cards:
            child = self.cards.get_child_at_pos(int(event.x), int(event.y))
        else:
            child = self.rows.get_row_at_y(int(event.y))
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            return self._finger_menu(child, event)
        if event.type != Gdk.EventType._2BUTTON_PRESS or event.button != 1:
            return False
        key = getattr(child, "key", None)
        rec = next((r for r in self.records if (r["user"], r["finger"]) == key), None)
        if rec is None or self.busy or self.status is None:
            return False

        def go():
            self._set_selection({key})        # the two clicks toggled it; keep it selected
            if rec["user"] != self.status["user"]:
                self.message("You can only test your own fingers.", Gtk.MessageType.WARNING)
            elif not rec["on_sensor"]:
                self.message(f"{short_finger(rec['name'])} is no longer on the sensor, so it "
                             "can't be tested — remove it, then import or enrol it again.",
                             Gtk.MessageType.WARNING)
            else:
                self.on_test(None, rec=rec)
            return False
        # after the second click's release has toggled the selection
        GLib.timeout_add(120, go)
        return False

    def _popup(self, entries, event):
        """Show a right-click menu. entries: (label, callback, sensitive, tooltip)."""
        menu = Gtk.Menu()
        menu.get_style_context().add_class("fpm-menu")
        menu.set_reserve_toggle_size(False)            # no empty check-box column
        for label, cb, sensitive, tip in entries:
            if menu.get_children():                    # a two-tone line between options
                sep = Gtk.SeparatorMenuItem()
                sep.get_style_context().add_class("fpm-menu-sep")
                menu.append(sep)
            mi = Gtk.MenuItem(label="")
            # a mark before each option, to set them apart
            mi.get_child().set_markup(MENU_MARK + "  " + GLib.markup_escape_text(label))
            mi.set_sensitive(sensitive)
            if tip:
                mi.set_tooltip_text(tip)
            mi.connect("activate", lambda _m, cb=cb: GLib.idle_add(lambda: cb() and False))
            menu.append(mi)
        menu.show_all()
        menu.attach_to_widget(self, None)
        menu.popup_at_pointer(event)
        return True

    def _finger_menu(self, child, event):
        """Right-click menu for a finger: what you can do with that one."""
        if child is None or self.busy or self.status is None:
            return False
        entries = []

        def item(label, cb, sensitive=True, tip=None):
            entries.append((label, cb, sensitive, tip))

        empty = getattr(child, "empty_finger", None)
        key = getattr(child, "key", None)
        rec = next((r for r in self.records if (r["user"], r["finger"]) == key), None)
        if empty:
            item(f"Enrol {long_finger(empty).lower()}…",
                 lambda: self.on_enrol(None, finger=empty), self.enrol_ok)
            item("Restore removed record…", lambda: self.restore_finger(empty),
                 tip="Put back a record of this finger that was removed earlier, "
                     "if its template is still on the sensor")
        elif rec is not None:
            self._set_selection({key})
            mine = rec["user"] == self.status["user"]
            if rec["on_sensor"]:
                item("Test", lambda: self.on_test(None, rec=rec), mine,
                     None if mine else "You can only test your own fingers")
                if mine:
                    item("Enrol again…", lambda: self.enrol_again(rec),
                         tip="Replace this finger with a fresh enrolment — "
                             "useful if it doesn't match reliably")
                if self.sensor_item.get_active() and rec.get("template"):
                    item("Show on sensor", lambda: self.show_template(rec["template"]))
                item(f"Remove from {OS_NAME}", lambda: self.on_remove_selected(None))
            else:
                item("Remove dead record…", lambda: self.on_remove_dead(None, [rec]))
                if mine:
                    item("Enrol this finger again…", lambda: self.reenrol(rec),
                         tip="Remove the dead record, then enrol the finger again")
        else:
            return False
        return self._popup(entries, event)

    def _tpl_menu(self, widget, event):
        """Right-click a template on the Sensor tab: select it and show a menu."""
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False
        if widget is self.tcards:
            child = self.tcards.get_child_at_pos(int(event.x), int(event.y))
        else:
            child = self.trows.get_row_at_y(int(event.y))
        tid = getattr(child, "tid", None)
        if tid is None or self.busy or self.status is None:
            return False                                   # a free slot
        self._set_tsel({tid})
        t = next((t for t in self.templates if t["id"] == tid), {})
        keys = [tuple(k) for k in t.get("keys", [])]
        entries = []
        rm = t.get("removed")
        if keys:
            entries.append(("Show finger", lambda: self.show_finger(keys[0]), True, None))
        elif rm:
            entries.append((f"Restore to {OS_NAME}",
                            lambda: self.undo_remove([rm["path"]], what="Restored"),
                            rm["restorable"],
                            None if rm["restorable"] else
                            f"That finger is enrolled on {OS_NAME} again"))
        entries.append(("Delete from sensor…", lambda: self.on_delete_templates(None),
                        self.status["features"].get("STORAGE_DELETE", False), None))
        return self._popup(entries, event)

    def show_template(self, tid):
        """From a finger: the Sensor tab with its template selected."""
        self.stack.set_visible_child_name("sensor")
        self._set_tsel({tid})

    def show_finger(self, key):
        """From a template: the Fingerprints tab with its finger selected."""
        self.stack.set_visible_child_name("fingers")
        if key[0] != self.status["user"]:
            self._set_view("list", save=False)    # other users' fingers are only in the list
        self._set_selection({key})

    def enrol_again(self, rec):
        """Replace one of your fingers: delete its template, then enrol it afresh."""
        name = long_finger(rec["name"]).lower()
        if not self.confirm(f"Enrol your {name} again?",
                            f"Its template is deleted from the sensor and you enrol the "
                            f"finger afresh. Any other distro sharing this finger stops "
                            f"matching it until you export from here and import there again.",
                            "Enrol again"):
            return
        if not rec.get("template"):
            return self.reenrol(rec)

        def done(_res, err):
            if err:
                return self.refresh(lambda: self.error(err))
            self.refresh(lambda: self.status and self.on_enrol(None, finger=rec["name"]))
        self.run_job("delete_templates", done, ids=[rec["template"]])

    def restore_finger(self, name):
        """Put back the newest removed record of one of your fingers, if its
        template is still on the sensor."""
        me = self.status["user"]

        def listed(res, err):
            if err:
                return self.error(err)
            recs = [r for r in res["records"]
                    if r["user"] == me and r["name"] == name and r["on_sensor"]
                    and r["user_ok"] and not r["exists"]]
            if not recs:
                return self.message(f"There is no removed record of your "
                                    f"{long_finger(name).lower()} that can be put back "
                                    f"(its template is no longer on the sensor).")
            self.undo_remove([recs[0]["path"]], what="Restored")
        self.run_job("list_moved", listed)

    def _on_fingers_key(self, _w, event):
        """Delete key: remove the selected finger (as the right-click menu does)."""
        if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete) and self.sel_keys \
                and not self.busy and self.status is not None:
            self.on_remove_selected(None)
            return True
        return False

    def reenrol(self, rec):
        """A dead finger: move its record aside, then enrol that finger again."""
        def done(_res, err):
            if err:
                return self.refresh(lambda: self.error(err))
            self.refresh(lambda: self.status and self.on_enrol(None, finger=rec["name"]))
        self.run_job("remove_records", done,
                     records=[{"user": rec["user"], "finger": rec["finger"]}])

    def _set_selection(self, keys):
        """Keep both views showing the same selection."""
        self.sel_keys = set(keys)
        for w in self.cards.get_children() + self.rows.get_children():
            self._mark(w, getattr(w, "key", None) in self.sel_keys)
        self._update_buttons()

    def _icon_or_text(self, button, names, text):
        """The first of these icons the theme has (themes name them differently),
        or a text symbol."""
        theme = Gtk.IconTheme.get_default()
        for n in names:
            if theme.has_icon(n):
                button.set_image(Gtk.Image.new_from_icon_name(n, Gtk.IconSize.BUTTON))
                return
        button.set_label(text)

    def _pill(self, kind, text):
        pill = Gtk.Label(label=text, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        for c in ("fpm-pill", "fpm-" + kind):
            pill.get_style_context().add_class(c)
        return pill

    def _label(self, text, *classes, **kw):
        lbl = Gtk.Label(label=text, **kw)
        for c in classes:
            lbl.get_style_context().add_class(c)
        return lbl

    def _finger_card(self, r):
        """Card for one of your enrolled fingers."""
        kind, status = rec_kind(r)
        when = nice_date(r["enrolled"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("fpm-fcard")
        over = Gtk.Overlay()
        over.add(FingerprintIcon(kind, 40))
        if kind == "dead":
            over.add_overlay(Gtk.Label(label="⚠", halign=Gtk.Align.END, valign=Gtk.Align.START))
        box.pack_start(over, False, False, 2)
        box.pack_start(self._label(short_finger(r["name"]), "fpm-name",
                                   justify=Gtk.Justification.CENTER, wrap=True), False, False, 0)
        box.pack_start(self._label(f"Enrolled {when}" if when else " ", "dim-label", "fpm-small"),
                       False, False, 0)
        box.pack_start(self._pill(kind, status), False, False, 4)
        child = Gtk.FlowBoxChild()
        child.key = (r["user"], r["finger"])
        child.set_tooltip_text(long_finger(r["name"])
                               + (f", enrolled {nice_date(r['enrolled'], True)}" if r["enrolled"] else "")
                               + " — double-click to test")
        child.add(box)
        return child

    def _empty_card(self, name):
        """Card for a finger you haven't enrolled: click it to enrol it."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for c in ("fpm-fcard", "fpm-empty"):
            box.get_style_context().add_class(c)
        box.pack_start(FingerprintIcon("empty", 40), False, False, 2)
        box.pack_start(self._label(short_finger(name), "fpm-name",
                                   justify=Gtk.Justification.CENTER, wrap=True), False, False, 0)
        box.pack_start(self._label("Not enrolled", "fpm-small"), False, False, 0)
        child = Gtk.FlowBoxChild()
        child.empty_finger = name
        child.set_tooltip_text(long_finger(name) + " — click to enrol it")
        child.add(box)
        return child

    def _fill_records(self, records, me):
        self.records = records
        self.enrol_ok = len([r for r in records if r["user"] == me]) < 10
        for w in self.cards.get_children() + self.rows.get_children():
            w.destroy()
        # cards: all ten of your fingers (grey = not enrolled); other users: list only
        mine = {r["name"]: r for r in records if r["user"] == me}
        for name in GRID_FINGERS + [n for n in mine if n not in GRID_FINGERS]:
            r = mine.get(name)
            self.cards.add(self._finger_card(r) if r else self._empty_card(name))
        others = sorted({r["user"] for r in records if r["user"] != me})
        self.others_note.set_text("Fingerprints of " + ", ".join(others)
                                  + " are shown in the list view." if others else "")
        self.others_note.set_visible(bool(others))
        for r in records:
            kind, status = rec_kind(r)
            key = (r["user"], r["finger"])
            # row
            hb = Gtk.Box(spacing=10)
            hb.get_style_context().add_class("fpm-lcard")
            hb.pack_start(FingerprintIcon(kind, 36), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            texts.pack_start(self._label(long_finger(r["name"]), "fpm-name", xalign=0), False, False, 0)
            detail = r["user"] + (f" · enrolled {nice_date(r['enrolled'], True)}" if r["enrolled"] else "")
            if kind == "dead":
                detail += " · template gone"
            texts.pack_start(self._label(detail, "dim-label", "fpm-small", xalign=0,
                                         ellipsize=Pango.EllipsizeMode.END), False, False, 0)
            hb.pack_start(texts, True, True, 0)
            hb.pack_start(self._pill(kind, status), False, False, 0)
            test = Gtk.Button(label="Test", valign=Gtk.Align.CENTER)
            test.set_sensitive(r["user"] == me and bool(r["on_sensor"]))
            test.set_tooltip_text("Test this finger")
            test.connect("clicked", lambda _b, rr=r: self.on_test(None, rec=rr))
            hb.pack_start(test, False, False, 0)
            row = Gtk.ListBoxRow()
            row.key = key
            row.add(hb)
            self.rows.add(row)
        if self.enrol_ok:
            # "Enrol a finger" row (in the cards view the grey fingers do this)
            hb = Gtk.Box(spacing=10)
            for c in ("fpm-lcard", "fpm-add"):
                hb.get_style_context().add_class(c)
            hb.pack_start(self._label("＋  Enrol a finger…", "fpm-name", xalign=0), True, True, 0)
            row = Gtk.ListBoxRow(selectable=False)
            row.is_add = True
            row.add(hb)
            self.rows.add(row)
        self.cards.show_all()
        self.rows.show_all()
        self._set_selection({k for k in self.sel_keys
                             if any((r["user"], r["finger"]) == k for r in records)})

    def _update_buttons(self):
        st = self.status
        ready = st is not None and not self.busy
        recs = st["records"] if st else []
        mine = [r for r in recs if r["user"] == (st or {}).get("user")]
        self.refresh_btn.set_sensitive(not self.busy)
        self.test_btn.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.cards.set_sensitive(st is not None)
        self.rows.set_sensitive(st is not None)
        self.del_btn.set_sensitive(bool(ready and st["features"].get("STORAGE_DELETE", False)
                                        and self.tsel))
        self.wipe_btn.set_sensitive(bool(ready and (st["templates"] or recs)))
        self.export_item.set_sensitive(ready and any(r["on_sensor"] for r in mine))
        self.import_item.set_sensitive(ready)
        self.restore_item.set_sensitive(ready)
        pam = (st or {}).get("pam", {}).get("state")
        self.pam_switch.set_sensitive(ready and pam in ("enabled", "disabled", "partial"))

    # ── messages ──
    def message(self, text, kind=Gtk.MessageType.INFO, details=None, action=None):
        """Show a short message. details: full text behind a Details… button.
        action: (label, callback) for a button. Plain info messages fade after 10 s."""
        if self._msg_timer:
            GLib.source_remove(self._msg_timer)
            self._msg_timer = 0
        self.msg_bar.set_message_type(kind)
        self.msg_label.set_text(text)
        self.msg_label.set_tooltip_text(text if len(text) > 80 else None)
        self._msg_details = details if details and details.strip() != text.strip() else None
        self.msg_details_btn.set_visible(bool(self._msg_details))
        self._msg_action = action
        self.msg_action_btn.set_visible(bool(action))
        self.msg_action_btn.get_parent().set_visible(bool(action or self._msg_details))
        if action:
            self.msg_action_btn.set_label(action[0])
        self.msg_bar.show()
        if kind == Gtk.MessageType.INFO and not action:
            self._msg_timer = GLib.timeout_add_seconds(10, self._hide_message)

    def _hide_message(self):
        self._msg_timer = 0
        self.msg_bar.hide()
        return False

    def _on_msg_response(self, _bar, resp):
        if resp == 1 and self._msg_details:
            self.show_output("Details", self._msg_details)
        elif resp == 2 and self._msg_action:
            self._msg_action[1]()
        else:
            self._hide_message()

    def confirm(self, title, text, ok_label, destructive=True):
        d = Gtk.MessageDialog(transient_for=self, modal=True, buttons=Gtk.ButtonsType.NONE, text=title,
                              message_type=Gtk.MessageType.WARNING if destructive
                              else Gtk.MessageType.QUESTION)
        d.format_secondary_text(text)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button(ok_label, Gtk.ResponseType.OK)
        if destructive:
            ok.get_style_context().add_class("destructive-action")
        d.set_default_response(Gtk.ResponseType.CANCEL)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.OK

    def show_output(self, title, text, kind=Gtk.MessageType.INFO):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind,
                              buttons=Gtk.ButtonsType.CLOSE, text=title)
        d.format_secondary_text(text)
        d.run()
        d.destroy()

    # ── running helper jobs off the GUI thread ──
    def run_job(self, action, done=None, **kw):
        self.busy = True
        self.spinner.start()
        self._update_buttons()

        def work():
            try:
                res, err = self.helper.call(action, **kw), None
            except NoAccess as e:
                GLib.idle_add(no_access, str(e))
                return
            except Exception as e:
                res, err = None, str(e)
            GLib.idle_add(finish, res, err)

        def finish(res, err):
            self.busy = False
            self.spinner.stop()
            self._update_buttons()
            if done:
                done(res, err)
            return False

        def no_access(why):
            self.busy = False
            self.spinner.stop()
            self._update_buttons()
            self._no_access(why)
            return False

        threading.Thread(target=work, daemon=True).start()

    def _no_access(self, why):
        """Without administrator access the window can't do anything, so offer
        to try again or close it."""
        d = Gtk.MessageDialog(transient_for=self, modal=True,
                              message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.NONE,
                              text="The Fingerprint Manager needs administrator access")
        d.format_secondary_text(why + "\n\nIt reads and manages the fingerprint sensor, "
                                "which only an administrator can do.")
        d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.add_button("Try again", Gtk.ResponseType.OK).get_style_context().add_class(
            "suggested-action")
        d.set_default_response(Gtk.ResponseType.OK)
        again = d.run() == Gtk.ResponseType.OK
        d.destroy()
        if again:
            self.refresh()
        else:
            self.destroy()

    def error(self, err):
        """Show a script/helper error: its key line, full text under Details…"""
        self.message(summarise(err) or err, Gtk.MessageType.ERROR, details=err)

    def refresh(self, after=None):
        if self.msg_bar.get_message_type() != Gtk.MessageType.INFO:
            self._hide_message()            # old errors/warnings; new ones follow

        def done(st, err):
            if err:
                self.status = None
                self._fill_records([], None)
                self._fill_templates([])
                self.info.set_text("")
                self.pam_detail.set_text("")
                self.error(err)
            else:
                self.show_status(st)
            self._update_buttons()
            if after:
                after()

        self.info.set_text("Reading the sensor…")
        self.run_job("status", done, export=True)
        return False

    def show_status(self, st):
        self.status = st
        if st.get("export_offer"):
            GLib.idle_add(self._offer_export, st["export_offer"])
        self._fill_records(st["records"], st["user"])
        self._fill_templates(st["templates"])
        for name, n in (("fingers", len(st["records"])), ("sensor", len(st["templates"]))):
            self.stack.child_set_property(self.stack.get_child_by_name(name), "title",
                                          f"{self.pages[name]} ({n})")
        self.title_lbl.set_text(f"Fingerprints ({len(st['records'])})")
        marker = st.get("marker") or "unknown"
        version, driver, _date = parse_marker(marker)
        self.info.set_text(f"Sensor: {st['usb_id']} · Serial: {st['serial']} · "
                           + f"Driver commit: {(driver or 'unknown')[:7]}"
                           + (f" · v{version}" if version else ""))
        self.info.set_tooltip_text(f"{st.get('device_name', '')}\nfingerprint-fix-sdcp: {marker}")
        self.show_pam(st.get("pam") or {})
        dead = [r for r in st["records"] if r["on_sensor"] is False]
        if dead:
            names = ", ".join(f"{long_finger(r['name'])} ({r['user']})" for r in dead)
            self.message(f"No longer on the sensor: {names}.", Gtk.MessageType.WARNING,
                         details="These records point at templates the sensor no longer has "
                                 "(re-enrolled elsewhere, or removed by Windows), so they can "
                                 "never match. Remove them, then import a current export or "
                                 "enrol again.",
                         action=("Remove dead records", lambda: self.on_remove_dead(None)))

    def _set_pam_title(self, method):
        """The switch's title and tooltip for this system (pam_scope)."""
        self._pam_title, tip = pam_scope(method)
        self.pam_title.set_markup(f"<b>{GLib.markup_escape_text(self._pam_title)}</b>")
        self.pam_title.set_tooltip_text(tip)

    def show_pam(self, pam):
        state = pam.get("state", "unavailable")
        self._set_pam_title(pam.get("method", ""))
        self._pam_syncing = True
        on = state == "enabled"
        self.pam_switch.set_active(on)
        self.pam_switch.set_state(on)
        self._pam_syncing = False
        how = " — ".join(x for x in (pam.get("method"), pam.get("detail")) if x)
        lead = {"enabled": "On", "disabled": "Off", "partial": "Partly on"}.get(state, "Not available")
        self.pam_detail.set_text(f"{lead} · {how}" if how else lead)

    def on_pam_switch(self, _sw, want_on):
        if self._pam_syncing:
            return False
        if not want_on and not self.confirm(
                self._pam_title.replace("Use fingerprint", "Turn off fingerprint", 1) + "?",
                "These will ask for your password only. Your enrolled fingerprints are kept, "
                "and you can turn this back on at any time.", "Turn off"):
            self.show_pam(self.status.get("pam", {}))
            return True
        op = "enable" if want_on else "disable"

        def done(res, err):
            if err:
                self.refresh(lambda: self.error(err))
            else:
                word = "on" if op == "enable" else "off"
                self.refresh(lambda: self.message(self._pam_title.replace("Use fingerprint", "Fingerprint", 1) + f" is now {word}."))
        self.run_job("pam", done, op=op)
        return True                       # the switch follows the real state after refresh

    def after_job(self, title, undo=False):
        """undo: offer an Undo button that moves the records back (only for
        Remove — their templates are still on the sensor)."""
        def done(res, err):
            if err:
                self.refresh(lambda: self.error(err))
                return
            parts = []
            if res.get("output"):
                parts.append(summarise(res["output"]))
            if res.get("deleted") not in (None, [], 0):
                n = res["deleted"] if isinstance(res["deleted"], int) else len(res["deleted"])
                parts.append(f"Deleted {n} template(s) from the sensor.")
            if res.get("left"):
                parts.append(f"{res['left']} template(s) could not be deleted.")
            if res.get("moved"):
                head, sep, tail = res["moved"][0].partition("/removed-fingerprints/")
                folder = f"{head}{sep}{tail.split('/')[0]}/" if sep \
                    else os.path.dirname(res["moved"][0]) + "/"
                parts.append(f"Moved {len(res['moved'])} record(s) aside.")
                extra = f"\n\nMoved to {folder}"
            else:
                extra = ""
            summary = " ".join(p for p in parts if p) or "Done."
            summary = summary.replace(os.path.expanduser("~") + "/", "~/")
            first = title.split()[0].lower()
            text = summary if summary.lower().startswith(first) else f"{title}: {summary}"
            moved = res.get("moved") or []
            action = ("Undo", lambda: self.undo_remove(moved)) if undo and moved else None
            self.refresh(lambda: self.message(text, action=action,
                                              details=(res.get("output") or "") + extra or None))
        return done

    def undo_remove(self, paths, what="Undone"):
        """Put records back that Remove has just moved aside."""
        self._hide_message()

        def done(res, err):
            if err:
                return self.refresh(lambda: self.error(err))
            n, k = len(res["restored"]), len(res["skipped"])
            text = f"{what} — put back {n} record(s)." if n else "Nothing was put back."
            if k:
                text += f" {k} could not be put back."
            details = "\n".join((["Put back: " + ", ".join(res["restored"])] if n else [])
                                 + (["Not put back: " + "; ".join(res["skipped"])] if k else []))
            self.refresh(lambda: self.message(text, details=details or None))
        self.run_job("restore", done, paths=paths)

    # ── actions ──
    def on_test(self, _btn, rec=None):
        """Test one finger (the selected one) or any of yours, as login does,
        and show which finger matched.

        The helper asks the sensor directly: fprintd only reports match / no
        match when it checks all fingers, never which finger it was."""
        me = self.status["user"]
        # The button tests all your fingers; double-clicking a finger passes it as rec.
        picked = [[rec["user"], rec["name"], rec["enrolled"], "", rec["finger"], 1]] if rec else []
        finger = picked[0][4] if picked else None
        what = picked[0][1] if picked else "any of your fingers (as login and sudo do)"

        d = Gtk.Dialog(title="Test fingerprint", transient_for=self, modal=True)
        d.set_default_size(420, -1)
        close_btn = d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        again_btn = d.add_button("Test again", 1)
        again_btn.set_no_show_all(True)
        area = d.get_content_area()
        area.set_spacing(8)
        area.set_border_width(18)
        icon = Gtk.Label()
        head = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        sub = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, selectable=True)
        for w in (icon, head, sub):
            area.pack_start(w, False, False, 0)
        state = {"proc": None}

        def show(symbol, colour, title, detail):
            span = f' foreground="{colour}"' if colour else ""
            icon.set_markup(f'<span size="48000"{span}>{symbol}</span>')
            head.set_markup(f'<span size="x-large" weight="bold"{span}>'
                            f'{GLib.markup_escape_text(title)}</span>')
            sub.set_text(detail)

        def start():
            show("☝", None, "Touch the fingerprint sensor", f"Testing: {what}")
            close_btn.set_label("Cancel")
            again_btn.hide()
            state["running"] = True
            self.busy = True
            self._update_buttons()

            def work():
                try:
                    res, err = self.helper.call("test", finger=finger), None
                except Exception as e:
                    res, err = None, str(e)
                GLib.idle_add(finished, res, err)

            threading.Thread(target=work, daemon=True).start()

        def finished(res, err):
            state["running"] = False
            self.busy = False
            self._update_buttons()
            if state.get("closed"):
                return False
            result = (res or {}).get("result")
            if result == "match":
                show("✓", "#26a269", f"Match — {res['name']}", f"Tested: {what}")
            elif result == "no-match":
                show("✗", "#c01c28", "No match",
                     f"Tested: {what}\nThat finger didn't match. Try again, or test another finger.")
            elif result == "timeout":
                show("!", "#e5a50a", "No touch", "Nothing touched the sensor within 60 seconds.")
            elif result == "retry":
                show("!", "#e5a50a", "Couldn't read your finger",
                     f"{res.get('message') or ''}\nTouch the sensor flat and try again.".strip())
            elif result == "cancelled":
                return False
            else:
                show("!", "#e5a50a", "Test did not complete", err or "Unknown result")
            close_btn.set_label("Close")
            again_btn.show()
            return False

        d.show_all()
        start()
        while True:
            r = d.run()
            if r == 1 and not state.get("running"):
                start()
                continue
            break
        state["closed"] = True
        if state.get("running"):
            self.helper.cancel()
        d.destroy()

    def on_enrol(self, _btn, finger=None):
        """Enrol a new finger for the user with fprintd-enroll, with progress.
        With a finger (a grey card was clicked) it starts straight away."""
        if not shutil.which("fprintd-enroll"):
            return self.message("fprintd-enroll is not installed.", Gtk.MessageType.ERROR)
        st = self.status
        mine = {r["name"] for r in st["records"] if r["user"] == st["user"]}
        free = [f for f in FINGERS if f not in mine]
        others = [t for t in st["templates"] if not t["used_by"]]
        # fprintd's first touch is a duplicate check, then the driver's stages.
        total = (st.get("enroll_stages") or 0) + 1

        d = Gtk.Dialog(title="Enrol a finger", transient_for=self, modal=True)
        d.set_default_size(440, -1)
        close_btn = d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        start_btn = d.add_button("Start", 1)
        start_btn.get_style_context().add_class("suggested-action")
        area = d.get_content_area()
        area.set_spacing(10)
        area.set_border_width(18)

        pick = Gtk.Box(spacing=8)
        pick.pack_start(Gtk.Label(label="Finger:"), False, False, 0)
        combo = Gtk.ComboBoxText()
        for f in free:
            combo.append(f, long_finger(f))
        combo.set_active(free.index(finger) if finger in free else 0)
        pick.pack_start(combo, True, True, 0)
        area.pack_start(pick, False, False, 0)

        warn = ("If this finger is already enrolled on another Linux install or in Windows "
                "Hello, enrolling it here deletes it from the sensor, so it stops working "
                "there. To use the same finger on several installs, enrol it once and use "
                "Export / Import.")
        if others:
            warn = (f"The sensor has {len(others)} template(s) not used by this install — "
                    "possibly another install or Windows Hello.\n\n" + warn)
        else:
            warn += "\n\nThere are no other templates on the sensor right now."
        note = Gtk.Label(label=warn, wrap=True, xalign=0, max_width_chars=55)
        area.pack_start(note, False, False, 0)

        icon = Gtk.Label()
        head = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        sub = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        bar = Gtk.ProgressBar(show_text=True)
        for w in (icon, head, sub, bar):
            w.set_no_show_all(True)
            area.pack_start(w, False, False, 0)
        state = {"proc": None, "done": False, "count": 0, "finger": None}

        def show(symbol, colour, title, detail=""):
            span = f' foreground="{colour}"' if colour else ""
            icon.set_markup(f'<span size="40000"{span}>{symbol}</span>')
            head.set_markup(f'<span size="large" weight="bold"{span}>'
                            f'{GLib.markup_escape_text(title)}</span>')
            sub.set_text(detail)
            for w in (icon, head, sub):
                w.show()

        def progress():
            n = min(state["count"], total)
            bar.set_fraction(n / total if total > 1 else 0)
            bar.set_text(f"{n} of {total} touches" if total > 1 else "")
            bar.show()

        def start():
            finger = combo.get_active_id()
            if not finger:
                return
            state.update(finger=finger, count=0)
            pick.hide()
            if finger_given and others:
                # Started without the choice screen: keep a short warning.
                note.set_text(f"The sensor has {len(others)} template(s) not used by this "
                              "install. If this finger is one of them (another install or "
                              "Windows Hello), enrolling it here deletes it from there.")
                note.get_style_context().add_class("dim-label")
            else:
                note.hide()
            start_btn.hide()
            show("☝", None, f"Touch the sensor with your {finger.replace('-', ' ')}",
                 "Lift your finger and touch again each time, moving it slightly.")
            progress()
            proc = subprocess.Popen(["fprintd-enroll", "-f", finger], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            state["proc"] = proc

            def read():
                for line in proc.stdout:
                    GLib.idle_add(on_line, line.strip())
                proc.wait()
                GLib.idle_add(on_exit, proc.returncode)

            threading.Thread(target=read, daemon=True).start()

        def finish(symbol, colour, title, detail):
            state["done"] = True
            show(symbol, colour, title, detail)
            if symbol != "✓":
                bar.hide()
            close_btn.set_label("Close")

        def on_line(line):
            if state["done"]:
                return False
            res = line.split(":", 1)[1].strip() if line.startswith("Enroll result:") else ""
            finger = state["finger"]
            if res == "enroll-stage-passed":
                state["count"] += 1
                progress()
                show("☝", None, "Lift and touch again", f"Enrolling: {long_finger(finger)}")
            elif res in ("enroll-retry-scan", "enroll-swipe-too-short",
                         "enroll-finger-not-centered", "enroll-remove-and-retry"):
                show("☝", AMBER, "That touch didn't read — touch again",
                     "Place your finger flat in the middle of the sensor.")
            elif res == "enroll-completed":
                state["count"] = total
                progress()
                finish("✓", GREEN, f"Enrolled — {long_finger(finger)}",
                       "If you share fingerprints with other installs, export again "
                       "so they get this finger too.")
            elif res == "enroll-duplicate":
                finish("✗", RED, "Already enrolled here",
                       "That finger is already enrolled on this install (as another finger "
                       "or for another user). Nothing was changed.")
            elif res == "enroll-data-full":
                finish("✗", RED, "The sensor is full",
                       "Delete templates you no longer need on the Sensor tab (☰ → Show "
                       "the Sensor tab), then try again.")
            elif res:
                finish("✗", RED, "Enrolment failed", res)
            elif line.lower().startswith(("failed", "enrollstart failed", "impossible")):
                finish("✗", RED, "Enrolment could not start", line)
            return False

        def on_exit(rc):
            if not state["done"] and not state.get("closed"):
                finish("!", AMBER, "Enrolment stopped", f"fprintd-enroll exited ({rc}).")
            return False

        finger_given = finger in free
        d.show_all()
        if finger_given:
            d.set_title(f"Enrol — {long_finger(finger)}")
            start()
        while True:
            r = d.run()
            if r == 1 and state["proc"] is None:
                start()
                continue
            break
        state["closed"] = True
        p = state["proc"]
        if p and p.poll() is None:
            p.terminate()
        d.destroy()
        if p:
            self.refresh()

    def on_restore(self, _btn):
        """List records moved aside and put the chosen ones back."""
        def listed(res, err):
            if err:
                return self.error(err)
            self._restore_dialog(res["records"])
        self.run_job("list_moved", listed)

    def _restore_dialog(self, recs):
        if not recs:
            return self.show_output("Nothing to restore",
                                    "No records have been moved aside on this install.")
        d = Gtk.Dialog(title="Restore fingerprint records", transient_for=self, modal=True)
        d.set_default_size(680, 380)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button("Restore", Gtk.ResponseType.OK)
        ok.get_style_context().add_class("suggested-action")
        area = d.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.pack_start(Gtk.Label(wrap=True, xalign=0, label=(
            "Records moved aside by the boot check, this tool, or an import with --replace. "
            "Only a record whose template is still on the sensor can work, so only those "
            "can be restored.")), False, False, 0)
        # moved: date, user, finger, why, status, path, restorable
        store = Gtk.ListStore(str, str, str, str, str, str, bool)
        for r in recs:
            if not r["user_ok"]:
                status, ok_ = "✗ No such user here", False
            elif r["exists"]:
                status, ok_ = "Enrolled here again", False
            elif r["on_sensor"]:
                status, ok_ = "✓ Template on the sensor", True
            else:
                status, ok_ = "✗ Template gone", False
            why = "Replaced by import" if r["kind"] == "replaced" else "Removed"
            day, _, hms = r["date"].partition("_")       # 2026-10-25_123333
            when = f"{day} {hms[:2]}:{hms[2:4]}" if len(hms) >= 4 else day
            store.append([when, r["user"], r["name"], why, status, r["path"], ok_])
        view = self._table(store, ["Moved", "User", "Finger", "Why", "Status"])
        sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        sw.add(view)
        area.pack_start(sw, True, True, 0)

        def changed(*_):
            rows = self._selected(view, 0)
            ok.set_sensitive(bool(rows) and all(r[6] for r in rows))
        view.get_selection().connect("changed", changed)
        changed()
        d.show_all()
        rows = self._selected(view, 0) if d.run() == Gtk.ResponseType.OK else []
        paths = [r[5] for r in rows if r[6]]
        d.destroy()
        if not paths:
            return

        def done(res, err):
            if err:
                return self.refresh(lambda: self.error(err))
            text = []
            if res["restored"]:
                text.append("Restored: " + ", ".join(res["restored"]))
            if res["skipped"]:
                text.append("Not restored: " + "; ".join(res["skipped"]))
            n, k = len(res["restored"]), len(res["skipped"])
            short = f"Restored {n} record(s)." + (f" {k} not restored." if k else "")
            self.refresh(lambda: self.message(short, details="\n".join(text)))
        self.run_job("restore", done, paths=paths)

    def on_remove_dead(self, _btn, dead=None):
        if dead is None:
            dead = [r for r in self.status["records"] if r["on_sensor"] is False]
        names = "\n".join(f"  • {long_finger(r['name'])} ({r['user']})" for r in dead)
        if self.confirm("Remove dead record?" if len(dead) == 1 else "Remove dead records?",
                        f"Their templates are no longer on the sensor, so they can never match:\n"
                        f"{names}\n\nThe records are moved to "
                        "/var/lib/samsung-galaxybook/removed-fingerprints/. "
                        "Nothing on the sensor changes.", "Remove", destructive=False):
            self.run_job("remove_records", self.after_job("Removed dead records"),
                         records=[{"user": r["user"], "finger": r["finger"]} for r in dead])

    def on_remove_selected(self, _btn):
        rows = self._selected_recs()
        if rows and not any(r[5] for r in rows):      # only dead ones: say so
            sel = [r for r in self.records if (r["user"], r["finger"]) in self.sel_keys]
            return self.on_remove_dead(None, sel)
        names = "\n".join(f"  • {r[1]} ({r[0]})" for r in rows)
        if self.confirm(f"Remove from {OS_NAME} only?",
                        f"{names}\n\nThese fingerprints stop working on {OS_NAME}. Their templates "
                        "stay on the sensor, so other installs sharing them keep working. The records "
                        "are moved to /var/lib/samsung-galaxybook/removed-fingerprints/.",
                        "Remove"):
            self.run_job("remove_records", self.after_job(f"Removed from {OS_NAME}", undo=True),
                         records=[{"user": r[0], "finger": r[4]} for r in rows])

    def on_delete_templates(self, _btn):
        rows = self._selected_tpls()
        used = [r for r in rows if r[2]]
        unused = [r for r in rows if not r[2]]
        text = []
        if used:
            text.append("Used by this install: " + "; ".join(r[1] for r in used) + ".\n"
                        "They stop working here and on every other install sharing them. "
                        "Their records here are moved aside.")
        if unused:
            text.append(f"{len(unused)} template(s) not used by {OS_NAME}. They may belong to "
                        "another distro or to Windows Hello (or be left over from a reinstall) — "
                        "fingerprint login stops working there until you enrol again.")
        if self.confirm(f"Delete {len(rows)} template(s) from the sensor?",
                        "\n\n".join(text) + "\n\nThis can't be undone.", "Delete"):
            self.run_job("delete_templates", self.after_job("Deleted from the sensor"),
                         ids=[r[0] for r in rows])

    def on_wipe(self, _btn):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text="Wipe the whole sensor?")
        d.format_secondary_text(
            "This deletes EVERY template on the sensor — the fingerprints of every Linux install "
            "and of Windows Hello. Every record on this install is moved aside. Everyone has to "
            "enrol again, and exports made before this stop working.\n\nType WIPE to confirm.")
        entry = Gtk.Entry(activates_default=True)
        d.get_message_area().pack_start(entry, False, False, 0)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        ok = d.add_button("Wipe", Gtk.ResponseType.OK)
        ok.get_style_context().add_class("destructive-action")
        ok.set_sensitive(False)
        entry.connect("changed", lambda e: ok.set_sensitive(e.get_text().strip().upper() == "WIPE"))
        d.show_all()
        r = d.run()
        confirmed = r == Gtk.ResponseType.OK and entry.get_text().strip().upper() == "WIPE"
        d.destroy()
        if confirmed:
            self.run_job("wipe", self.after_job("Sensor wiped"))

    def _chooser(self, title, action, ok_label):
        d = Gtk.FileChooserDialog(title=title, transient_for=self, action=action)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d.add_button(ok_label, Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Fingerprint exports (*.tgz)")
        f.add_pattern("*.tgz")
        f.add_pattern("*.tar.gz")
        d.add_filter(f)
        d.set_current_folder(os.path.expanduser("~"))
        return d

    def on_export(self, _btn):
        d = self._chooser("Export fingerprints", Gtk.FileChooserAction.SAVE, "Export")
        d.set_current_name(EXPORT_NAME)
        d.set_do_overwrite_confirmation(True)
        path = d.get_filename() if d.run() == Gtk.ResponseType.OK else None
        d.destroy()
        if path:
            if not path.endswith((".tgz", ".tar.gz")):
                path += ".tgz"
            self.run_job("export", self.after_job("Exported"), file=path)

    def on_import(self, _btn):
        d = self._chooser("Import fingerprints", Gtk.FileChooserAction.OPEN, "Import")
        default = os.path.expanduser(f"~/{EXPORT_NAME}")
        if os.path.isfile(default):
            d.set_filename(default)
        path = d.get_filename() if d.run() == Gtk.ResponseType.OK else None
        d.destroy()
        if not path:
            return
        mine = [r for r in self.status["records"] if r["user"] == self.status["user"]]
        replace = False
        if mine:
            names = ", ".join(long_finger(r["name"]).lower() for r in mine)
            d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.NONE,
                                  text="You already have fingerprints on this install")
            d.format_secondary_text(
                f"You have {names} here.\n\n"
                "Add the missing ones: imports only the fingers you don't have here yet, "
                "and keeps yours as they are.\n\n"
                "Replace all: replaces yours with the ones in this file. Your records are "
                "moved to /var/lib/samsung-galaxybook/replaced-fingerprints/ — nothing is "
                "deleted from the sensor.")
            d.add_button("Cancel", Gtk.ResponseType.CANCEL)
            rb = d.add_button("Replace all", 2)
            rb.get_style_context().add_class("destructive-action")
            d.add_button("Add the missing ones", Gtk.ResponseType.OK)
            d.set_default_response(Gtk.ResponseType.OK)
            r = d.run()
            d.destroy()
            if r not in (Gtk.ResponseType.OK, 2):
                return
            replace = r == 2
        self.run_job("import", self.after_job("Imported"), file=path, replace=replace)

    # ── fingerprints in ~/fingerprint-export.tgz that this install lacks ──
    def _offer_export(self, offer):
        """Once per export file (a new export asks again): offer the fingers in
        it that this install doesn't have and the sensor still stores."""
        if self.busy or offer["id"] in (self._export_offered, load_settings().get("export_offer_seen")):
            return False
        self._export_offered = offer["id"]
        save_setting("export_offer_seen", offer["id"])
        names = ", ".join(long_finger(f["name"]).lower() for f in offer["fingers"])
        n = len(offer["fingers"])
        short = offer["file"].replace(os.path.expanduser("~") + "/", "~/")
        if self.confirm(f"Import {n} fingerprint{'s' if n > 1 else ''} from another install?",
                        f"{short} has {names}, which {'are' if n > 1 else 'is'} not on this "
                        "install yet and still stored on the sensor. Your fingerprints here "
                        "stay as they are.", "Import", destructive=False):
            self.run_job("import", self.after_job("Imported"), file=offer["file"],
                         fingers=[f["finger"] for f in offer["fingers"]])
        return False

    # ── new versions ──
    def check_for_update(self, max_age=24 * 3600):
        def work():
            new = update_check.newer_release(max_age)
            assets = update_check.release_assets(new) if new else []
            GLib.idle_add(self._show_update, new, assets)
        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, new, assets=()):
        self._new_version, self._new_assets = new, list(assets)
        if new:
            self.update_btn.set_tooltip_text(f"fingerprint-fix-sdcp {new} is available "
                                             f"(this is {app_version()})")
        self.update_btn.set_visible(bool(new))
        return False

    def _check_windows(self):
        """Look for Windows in the background (lsblk), then show the reminder."""
        def work():
            found = windows_installed()
            GLib.idle_add(self._windows_checked, found)
        threading.Thread(target=work, daemon=True).start()
        return False

    def _windows_checked(self, found):
        self._windows = found
        self.windows_item.set_visible(found)
        self.win_row.set_visible(found and self.windows_item.get_active())
        return False

    def _on_windows_toggled(self, item):
        save_setting("windows_hint", "1" if item.get_active() else "0")
        self.win_row.set_visible(self._windows and item.get_active())

    def _on_update_toggled(self, item):
        save_setting("update_check", "1" if item.get_active() else "0")
        if item.get_active():
            self.check_for_update(max_age=0)
        else:
            self.update_btn.hide()

    def _installed_as(self):
        """How this copy was installed: ('deb', 'ubuntu26.04'), ('rpm', 'fc45'),
        ('pacman', ''), or ('', '') for install.sh. The install marker says,
        e.g. "(deb package 1.0.0-1~ubuntu26.04)"."""
        marker = (self.status or {}).get("marker") or ""
        m = re.search(r"\((rpm|deb|pacman) package (\S+)\)", marker)
        if not m:
            return "", ""
        dist = (re.search(r"~([a-z]+[0-9.]+)$", m.group(2))
                or re.search(r"\.(fc[0-9]+)$", m.group(2)))
        return m.group(1), dist.group(1) if dist else ""

    def on_update(self, *_):
        new = self._new_version
        installed_fmt, installed_dist = self._installed_as()
        fmt, dist = update_check.this_system(installed_fmt, installed_dist)
        asset = update_check.pick_asset(self._new_assets, new, fmt, dist) if fmt else None
        page = f"{update_check.REPO_URL}/releases/tag/v{new}"

        tt = lambda t: f"<tt>{GLib.markup_escape_text(t)}</tt>"     # file names, commands
        if asset and "files" in asset:
            how = (f"Download the release's {tt('PKGBUILD')} to {tt('~/Downloads/' + asset['folder'])}, "
                   f"then build and install it with {tt('makepkg -si')} "
                   f"(needs {tt('base-devel')} and {tt('git')}; it only takes seconds).")
        elif asset:
            how = f"Download {tt(asset['name'])} to your {tt('~/Downloads')} folder."
        elif installed_fmt:
            how = ("No package for this system was found in this release.\n"
                   "- View on GitHub — download the right one from the release page.")
        else:
            how = ("No package fits this system. In your fingerprint-fix-sdcp folder, run:\n"
                   f"    {tt('git pull')}\n    {tt('sudo bash install.sh')}")
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.NONE,
                              text=f"fingerprint-fix-sdcp {new} is available")
        d.format_secondary_markup(how)
        d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.add_button("View on GitHub", 1)
        if asset:
            d.add_button("Download", 2)
            d.set_default_response(2)
        else:
            d.set_default_response(1)
        resp = d.run()
        d.destroy()
        if resp == 1:
            self._open_uri(page, "the release page")
        elif resp == 2:
            self._download_update(asset, fmt, replace_local=not installed_fmt)

    def _open_uri(self, uri, what):
        try:
            Gtk.show_uri_on_window(self, uri, Gdk.CURRENT_TIME)
        except GLib.Error as e:
            self.error(f"Could not open {what}: {e.message}")

    def _download_update(self, asset, fmt, replace_local=False):
        folder = (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                  or os.path.expanduser("~/Downloads"))
        self.update_btn.set_sensitive(False)
        # OTHER: stays up until the download ends (INFO fades after 10 s)
        self.message(f"Downloading {asset['name']}…", Gtk.MessageType.OTHER)
        shown = [0]

        def progress(done, total):
            pct = int(done * 100 / total) if total else 0
            if pct >= shown[0] + 10:                 # every 10 %
                shown[0] = pct
                GLib.idle_add(self.msg_label.set_text, f"Downloading {asset['name']}… {pct} %")

        def work():
            try:
                path = update_check.download_item(asset, folder, progress)
                GLib.idle_add(self._downloaded, path, fmt, None, replace_local)
            except Exception as e:                   # network, disk, checksum
                GLib.idle_add(self._downloaded, None, fmt, str(e), replace_local)
        threading.Thread(target=work, daemon=True).start()

    def _downloaded(self, path, fmt, err, replace_local=False):
        self.update_btn.set_sensitive(True)
        self._hide_message()
        if err:
            self.error(f"Download failed: {err}")
            return False
        cmd = update_check.install_command(fmt, path)
        # pacman refuses files it doesn't own, such as an install.sh copy's menu
        # entry, icon and polkit policy: remove that copy first with its own
        # cleanup, which asks nothing and keeps fingerprints and the sudo /
        # polkit-1 lines (the package takes those over). dnf and apt replace
        # it themselves, from the package's install script.
        if fmt == "pacman" and replace_local and os.path.exists(LOCAL_CLEANUP):
            cmd = f"sudo {LOCAL_CLEANUP} && {cmd}"
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.NONE, text="Downloaded")
        tt = lambda t: f"<tt>{GLib.markup_escape_text(t)}</tt>"
        if fmt == "pacman":
            text = ("- <b>Open folder</b> — opens the folder with the " + tt("PKGBUILD") + " and "
                    "copies the build command to the clipboard.\n\n"
                    "- <b>To build and install</b> — open a terminal and paste the command, or run:\n"
                    + tt(cmd) + "\n"
                    "It builds the driver (a few seconds), then asks for your password to install.")
            opened = path
        else:
            text = ("- <b>Open folder</b> — opens your " + tt("~/Downloads") + " folder and copies "
                    "the install command to the clipboard.\n\n"
                    "- <b>To install</b> — open a terminal and paste the install command, or run:\n"
                    + tt(cmd))
            opened = os.path.dirname(path)
        d.format_secondary_markup(text)
        d.add_button("Open folder", 1)
        d.add_button("Copy command", 2)
        d.add_button("Quit Manager", 3)
        d.set_default_response(1)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        while True:
            resp = d.run()
            if resp == 1:                            # open the folder, then quit like Quit Manager
                self._open_folder_detached(opened)
            if resp in (1, 2, 3):
                clipboard.set_text(cmd, -1)
                # Hand it to the clipboard manager, so it is still there to paste
                # after the Manager has quit.
                clipboard.store()
            if resp == 2:
                d.format_secondary_markup(text + "\n\n✓ Command copied — paste it into a terminal.")
                continue
            break
        d.destroy()
        if resp in (1, 3):
            # The package replaces the Manager's files and restarts fprintd. A
            # moment's wait lets the file manager come up first.
            GLib.timeout_add(700, lambda: self.close() and False)
        return False

    def _open_folder_detached(self, folder):
        """Open a folder in the file manager as its own process, so it still
        opens when the Manager quits straight afterwards (show_uri hands the
        request over asynchronously and is lost if the Manager exits first).

        On Wayland a program may only bring a window to the front with an
        activation token from the user's click; without one, a file manager
        that is already open (or minimised) gets the folder but stays behind.
        GTK makes the token; xdg-open and the file manager pass it on."""
        env = dict(os.environ)
        try:
            app = Gio.AppInfo.get_default_for_type("inode/directory", False)
            if app:
                ctx = self.get_display().get_app_launch_context()
                ctx.set_timestamp(Gtk.get_current_event_time())
                token = ctx.get_startup_notify_id(app, [Gio.File.new_for_path(folder)])
                if token:
                    env["XDG_ACTIVATION_TOKEN"] = token     # Wayland
                    env["DESKTOP_STARTUP_ID"] = token       # X11 startup notification
        except Exception:                                   # no token: the folder still opens
            pass
        try:
            subprocess.Popen(["xdg-open", folder], start_new_session=True, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:                              # no xdg-open: GTK's way
            self._open_uri(GLib.filename_to_uri(folder), "the folder")

    # ── a new version installed while the Manager is open ──
    def _watch_install(self):
        """Watch the installed copies' VERSION files (not when running from a
        checkout, where VERSION changes with git pull)."""
        self._install_monitors = []
        self._install_check_pending = False
        self._announced_version = None
        # Read now: an update replaces the VERSION file this copy reads.
        self._running_version = app_version()
        here = os.path.realpath(os.path.join(HERE, ".."))
        if here not in (os.path.realpath(folder) for folder, _ in INSTALLED_COPIES):
            return
        for folder, _ in INSTALLED_COPIES:
            try:
                mon = Gio.File.new_for_path(os.path.join(folder, "VERSION")).monitor_file(
                    Gio.FileMonitorFlags.NONE, None)
            except GLib.Error:
                continue
            mon.connect("changed", self._on_install_changed)
            self._install_monitors.append(mon)          # kept, or it stops watching

    def _on_install_changed(self, *_):
        # A package install changes several files: look once it has settled.
        if not self._install_check_pending:
            self._install_check_pending = True
            GLib.timeout_add_seconds(3, self._check_install)

    def _check_install(self):
        self._install_check_pending = False
        version, command = installed_copy()
        if not version or version in (self._running_version, self._announced_version):
            return False
        self._announced_version = version
        self.update_btn.hide()
        self.refresh()                              # the install restarted fprintd
        self.message(f"fingerprint-fix-sdcp {version} has been installed — restart the "
                     "Fingerprint Manager to use it.", Gtk.MessageType.INFO,
                     action=("Restart", lambda c=command: self._restart_into(c)))
        return False

    def _restart_into(self, command):
        """Start the newly installed Manager once this one has gone (it is a
        single instance: started sooner, it would only bring this window back)."""
        try:
            subprocess.Popen(["sh", "-c", 'sleep 1; exec "$0"', command], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError as e:
            self.error(f"Could not start the new Fingerprint Manager: {e}")
            return
        self.close()

    def on_about(self, *_):
        st = self.status or {}
        d = Gtk.AboutDialog(transient_for=self, modal=True)
        d.set_program_name(TITLE)
        d.set_logo_icon_name(ICON_NAME)
        d.set_comments("Part of Samsung Galaxy Book Fixes — fingerprint-fix-sdcp.\n"
                       "Test, enrol, share and tidy fingerprints on the Galaxy Book's "
                       "Egis fingerprint sensor.\n\nAn unofficial community tool, "
                       "not made or endorsed by Samsung.")
        version, driver, date = parse_marker(st.get("marker"))
        d.set_version(app_version())
        d.set_comments(d.get_comments() + "\n\nInstalled: "
                       + (f"fingerprint-fix-sdcp {version}" if version else "fingerprint-fix-sdcp")
                       + (f"\nDriver: libfprint-egismoc-sdcp {driver[:7]}" if driver else "")
                       + (f" ({nice_date(date, True)})" if date else ""))
        d.set_website("https://github.com/david-bartlett/fingerprint-fix-sdcp")
        d.set_website_label("github.com/david-bartlett/fingerprint-fix-sdcp")
        d.set_license_type(Gtk.License.GPL_2_0)
        d.set_authors(["David Bartlett", "Driver: Joshua Grisham, Abdallah Alkanani"])
        d.run()
        d.destroy()

    def on_quit(self, *_):
        self.helper.stop()
        if self.get_application() is None:       # started without the App (tests)
            Gtk.main_quit()


class App(Gtk.Application):
    """One window per user session. Starting it again — from the menu, the
    command or the launcher — asks the running window to come forward (the
    desktop raises it, or flashes it in the taskbar if it won't steal focus),
    and the second start exits."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

    def do_activate(self):
        if self.window is None and not reader_present():
            no_reader_dialog()          # nothing to manage; the app then quits
            return
        if self.window is None:
            self.window = Manager(application=self)
        else:
            self.window.present()


def main():
    if os.geteuid() == 0 and not os.environ.get("SUDO_UID"):
        sys.exit("Run Fingerprint Manager as yourself (it asks for your password when needed).")
    if not os.path.isfile(HELPER):
        sys.exit(f"Missing {HELPER} — keep both files in the same folder.")
    sys.exit(App().run(sys.argv[:1]))


if __name__ == "__main__":
    main()
