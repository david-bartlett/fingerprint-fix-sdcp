"""Galaxy Book Fingerprint Manager — open a command in the user's terminal.

find_terminal() picks the terminal to run the update in, best first:
  1. the one the desktop's own settings name (KDE, Xfce, Cinnamon, MATE)
  2. xdg-terminal-exec, the cross-desktop default (newer GNOME, Fedora, Arch)
  3. the desktop's own terminal (Ptyxis / GNOME Terminal / Console on GNOME,
     Konsole on KDE, …)
  4. x-terminal-emulator (Debian, Ubuntu, Mint)
  5. any other known terminal that is installed
Each terminal takes a command differently, hence the table. GNOME's own
"default terminal" setting is left out: it's no longer used and often names a
terminal that isn't the one in use.
"""
import configparser
import os
import shutil
import subprocess

# How each terminal runs a command: argv before the command's own arguments.
# ("str" ones take the command as one string.)
TERMINALS = {
    "ptyxis":          (["ptyxis", "--new-window", "--"], "args"),
    "gnome-terminal":  (["gnome-terminal", "--"], "args"),
    "kgx":             (["kgx", "--"], "args"),
    "konsole":         (["konsole", "-e"], "args"),
    "xfce4-terminal":  (["xfce4-terminal", "-x"], "args"),
    "mate-terminal":   (["mate-terminal", "-x"], "args"),
    "qterminal":       (["qterminal", "-e"], "args"),
    "lxterminal":      (["lxterminal", "-e"], "str"),
    "tilix":           (["tilix", "-e"], "str"),
    "terminator":      (["terminator", "-x"], "args"),
    "kitty":           (["kitty"], "args"),
    "alacritty":       (["alacritty", "-e"], "args"),
    "wezterm":         (["wezterm", "start", "--"], "args"),
    "foot":            (["foot"], "args"),
    "xterm":           (["xterm", "-e"], "args"),
}
# Each desktop's own terminals, best first (XDG_CURRENT_DESKTOP's names).
NATIVE = {
    "gnome":    ["ptyxis", "gnome-terminal", "kgx"],
    "ubuntu":   ["ptyxis", "gnome-terminal", "kgx"],
    "kde":      ["konsole"],
    "xfce":     ["xfce4-terminal"],
    "x-cinnamon": ["gnome-terminal", "xfce4-terminal"],
    "cinnamon": ["gnome-terminal", "xfce4-terminal"],
    "mate":     ["mate-terminal"],
    "lxqt":     ["qterminal"],
    "lxde":     ["lxterminal"],
    "budgie":   ["tilix", "gnome-terminal"],
}
# Last of all, in this order.
OTHERS = ["ptyxis", "konsole", "gnome-terminal", "kgx", "xfce4-terminal", "mate-terminal",
          "qterminal", "tilix", "terminator", "kitty", "alacritty", "wezterm", "foot",
          "lxterminal", "xterm"]


def _desktops():
    return [d.strip().lower() for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d.strip()]


def _known(name):
    """The table's key for a terminal named by a setting or a symlink."""
    base = os.path.basename((name or "").split()[0]) if name else ""
    base = base.split(":")[0]           # xdg-terminal-exec: "org.gnome.Ptyxis.desktop:new-window"
    for suffix in (".wrapper", ".real", ".desktop"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    base = {"org.gnome.ptyxis": "ptyxis", "org.gnome.console": "kgx",
            "org.kde.konsole": "konsole", "org.gnome.terminal": "gnome-terminal",
            "org.codeberg.dnkl.foot": "foot", "alacritty": "alacritty",
            "org.wezfurlong.wezterm": "wezterm", "com.gexperts.tilix": "tilix"}.get(base.lower(), base)
    return base if base in TERMINALS else None


def _read(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip().strip("'\"")
    except (OSError, subprocess.SubprocessError):
        return ""


def _desktop_setting():
    """The terminal the desktop's settings name, as a table key, or None."""
    desks = _desktops()
    home = os.path.expanduser("~")
    if "kde" in desks:
        for tool in ("kreadconfig6", "kreadconfig5"):
            if shutil.which(tool):
                t = _known(_read([tool, "--file", "kdeglobals", "--group", "General",
                                  "--key", "TerminalApplication"]))
                if t:
                    return t
        return None
    if "xfce" in desks:
        cp = configparser.ConfigParser(interpolation=None)
        for path in (os.path.join(home, ".config/xfce4/helpers.rc"), "/etc/xdg/xfce4/helpers.rc"):
            try:
                cp.read_string("[x]\n" + open(path).read())
                t = _known(cp.get("x", "TerminalEmulator", fallback=""))
                if t:
                    return t
            except (OSError, configparser.Error):
                pass
        return None
    for desk, schema in (("x-cinnamon", "org.cinnamon.desktop.default-applications.terminal"),
                         ("cinnamon", "org.cinnamon.desktop.default-applications.terminal"),
                         ("mate", "org.mate.applications-terminal")):
        if desk in desks and shutil.which("gsettings"):
            return _known(_read(["gsettings", "get", schema, "exec"]))
    return None


def find_terminal():
    """(name, argv-prefix, style) of the best terminal here, or None."""
    tried = []

    def ok(name):
        if not name or name in tried:
            return None
        tried.append(name)
        prefix, style = TERMINALS[name]
        return (name, prefix, style) if shutil.which(prefix[0]) else None

    found = ok(_desktop_setting())
    if found:
        return found
    if shutil.which("xdg-terminal-exec"):
        return ("xdg-terminal-exec", ["xdg-terminal-exec"], "args")
    for desk in _desktops():
        for name in NATIVE.get(desk, []):
            found = ok(name)
            if found:
                return found
    xte = shutil.which("x-terminal-emulator")
    if xte:
        found = ok(_known(os.path.realpath(xte)))
        if found:
            return found
        return ("x-terminal-emulator", [xte, "-e"], "args")   # Debian's rule: -e command args
    for name in OTHERS:
        found = ok(name)
        if found:
            return found
    return None


def command_line(term, argv):
    """The full argv that opens argv in term (from find_terminal)."""
    name, prefix, style = term
    if style == "str":
        import shlex
        return prefix + [shlex.join(argv)]
    return prefix + list(argv)


def _default_name(term):
    """For the system's default (xdg-terminal-exec, x-terminal-emulator): the
    table key of the terminal it opens, when that can be found out."""
    if term[0] == "xdg-terminal-exec":
        return _known(_read(["xdg-terminal-exec", "--print-id"]))      # e.g. org.gnome.Ptyxis.desktop
    if term[0] == "x-terminal-emulator":
        return _known(os.path.realpath(term[1][0]))
    return term[0]


def pretty_name(term):
    """'Konsole', 'Ptyxis'…; '' when it isn't known which terminal opens."""
    return {"ptyxis": "Ptyxis", "gnome-terminal": "GNOME Terminal", "kgx": "Console",
            "konsole": "Konsole", "xfce4-terminal": "Xfce Terminal", "mate-terminal": "MATE Terminal",
            "qterminal": "QTerminal", "lxterminal": "LXTerminal", "tilix": "Tilix",
            "terminator": "Terminator", "kitty": "kitty", "alacritty": "Alacritty",
            "wezterm": "WezTerm", "foot": "foot", "xterm": "XTerm"}.get(_default_name(term), "")


def in_window(term):
    """'in a Konsole window', or 'in your terminal' when the name isn't known."""
    name = pretty_name(term)
    if not name:
        return "in your terminal"
    article = "an" if name[0] in "AEIOUX" else "a"     # an Xfce Terminal, an XTerm
    return f"in {article} {name} window"


if __name__ == "__main__":          # python3 terminal.py: which one would be used
    t = find_terminal()
    print(t and f"{in_window(t)}: {' '.join(command_line(t, ['echo', 'hello']))}" or "no terminal found")
