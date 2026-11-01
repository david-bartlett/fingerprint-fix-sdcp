#!/usr/bin/env python3
# =============================================================================
# fingerprint-fix-sdcp — is a newer release on GitHub? (runs as the user)
# =============================================================================
# Used by the Fingerprint Manager (its Update button) and by the hourly check:
#
#   update_check.py --notify    one notification per new release, with buttons
#                               to its GitHub page and the Fingerprint Manager
#
# The hourly check is a user timer in each package (the driver's copy of this
# file in /usr/lib/fingerprint-fix-sdcp/update/ runs only while the Manager
# isn't installed). It asks GitHub at most once an hour; the Manager asks each
# time it starts (they share one cache). When GitHub can't be reached (no
# network yet), the next check tries again.
#
# On / off is the timer itself, per user. The Manager's menu item "Check for
# new versions" switches both timers; with only the driver:
#   systemctl --user mask   fingerprint-fix-sdcp-update-check.timer   (off)
#   systemctl --user unmask fingerprint-fix-sdcp-update-check.timer   (on)
# Packages enable the timers for all users, which a user can't disable, only
# mask; install.sh enables them in the user's own folder, where they can be
# disabled but not masked. So "off" is masked or disabled.
#
# The Manager's Download button: this_system() and pick_asset() choose this
# system's package from the release's files, download() saves and checks it.
#
# No GitHub API: it allows only 60 requests an hour per internet connection
# without a login, shared by everything on that connection, and a used-up
# limit would hide new releases. The newest release comes from where
# github.com/…/releases/latest redirects to (…/releases/tag/v1.2.0), and its
# files from the SHA256SUMS file attached to each release.
# =============================================================================
import hashlib
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

APP = "galaxybook-fingerprint-manager"      # the icon, and the settings / cache folder name
REPO_URL = "https://github.com/david-bartlett/fingerprint-fix-sdcp"
LATEST_URL = REPO_URL + "/releases/latest"             # redirects to …/releases/tag/<tag>
DOWNLOAD_URL = REPO_URL + "/releases/download/{tag}/{name}"
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), APP)
RELEASE_CACHE = os.path.join(CACHE_DIR, "latest-release")       # "<checked epoch> <tag or ->"
NOTIFIED = os.path.join(CACHE_DIR, "notified-release")          # tag last announced at login
SETTINGS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        APP, "settings")
HERE = os.path.dirname(os.path.realpath(__file__))


def version_key(v):
    """(major, minor, patch) from '1.2.3' or 'v1.2.3'; None if it isn't one."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def installed_version():
    """This copy's version: the VERSION file next to lib/."""
    try:
        with open(os.path.join(HERE, "..", "VERSION")) as f:
            return f.read().strip() or None
    except OSError:
        return None


FIX_TIMER = "fingerprint-fix-sdcp-update-check.timer"
MGR_TIMER = "galaxybook-fingerprint-manager-update-check.timer"


def _timer_state(timer):
    """systemctl --user is-enabled: enabled, masked, disabled…; '' if unknown."""
    try:
        r = subprocess.run(["systemctl", "--user", "is-enabled", timer],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def enabled():
    """False when checking is switched off: the Manager's timer masked (its
    'Check for new versions' masks both). Before 2.3 the switch was a line in
    the Manager's settings: such a choice is moved to the timers once."""
    _migrate_setting()
    return _timer_state(MGR_TIMER) not in ("masked", "disabled")


def set_enabled(on):
    """The Manager's switch: unmask / mask both timers (the driver's too, so
    removing the Manager later doesn't start checking again)."""
    timers = [MGR_TIMER, FIX_TIMER]
    steps = (["unmask", "enable"] if on else ["disable", "mask"])
    for step in steps:              # each may not apply (see above): errors are fine
        for t in timers:
            subprocess.run(["systemctl", "--user", step, t], capture_output=True, timeout=15)


def _migrate_setting():
    try:
        with open(SETTINGS) as f:
            lines = f.readlines()
    except OSError:
        return
    old = [l for l in lines if l.strip().startswith("update_check=")]
    if not old:
        return
    try:
        if any(l.strip() == "update_check=0" for l in old):
            set_enabled(False)
        with open(SETTINGS, "w") as f:
            f.writelines(l for l in lines if l not in old)
    except (OSError, subprocess.SubprocessError):
        pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None                 # report the redirect instead of following it


def _latest_tag():
    """The newest release's tag from where releases/latest redirects to; None
    when there is no release (no redirect to a tag, or 404). Raises on network
    trouble."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(LATEST_URL, method="HEAD", headers={"User-Agent": APP})
    try:
        with opener.open(req, timeout=10):
            return None             # 200: a releases page without a tag — no release yet
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            m = re.search(r"/releases/tag/([^/?#]+)$", e.headers.get("Location") or "")
            return urllib.parse.unquote(m.group(1)) if m else None
        if e.code == 404:
            return None             # no such repository (or not public)
        raise


def latest_release(max_age=24 * 3600):
    """The newest release's tag (e.g. 'v1.0.2'), or None when unknown.
    Asks GitHub at most once per max_age seconds. 'No release' (none yet, or
    the repository not public) is remembered too; a failed connection is not,
    so the next try asks again."""
    now = time.time()
    try:
        with open(RELEASE_CACHE) as f:
            checked, tag = f.read().split()
        if 0 <= now - float(checked) < max_age:
            return None if tag == "-" else tag
    except (OSError, ValueError):
        pass
    try:
        tag = _latest_tag()
    except Exception:               # no network yet, DNS, timeout, server trouble
        return None
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(RELEASE_CACHE, "w") as f:
            f.write(f"{now:.0f} {tag or '-'}\n")
    except OSError:
        pass
    return tag


def _cache_time():
    """When GitHub's answer was saved (epoch seconds), or None."""
    try:
        with open(RELEASE_CACHE) as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _session_start():
    """When this desktop session started (graphical-session.target became
    active), as epoch seconds; 0 when systemd can't say."""
    try:
        out = subprocess.run(["systemctl", "--user", "show", "-P", "ActiveEnterTimestamp",
                              "--timestamp=unix", "graphical-session.target"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return float(out.lstrip("@")) if out.lstrip("@") else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def newer_release(max_age=24 * 3600):
    """The newer release's version ('1.0.2') if there is one, else None."""
    tag, mine = latest_release(max_age), installed_version()
    if version_key(tag) and version_key(mine) and version_key(tag) > version_key(mine):
        return tag.lstrip("v")
    return None


# ── this system's package ────────────────────────────────────────────────────
# Ubuntu-based releases by codename (Linux Mint, Zorin, Pop!_OS… name their
# Ubuntu base in UBUNTU_CODENAME): the release's .deb for each.
UBUNTU_BASES = {"noble": "ubuntu24.04", "resolute": "ubuntu26.04"}


def os_release(path="/etc/os-release"):
    fields = {}
    try:
        with open(path) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k:
                    fields[k] = v.strip("\"'")
    except OSError:
        pass
    return fields


def this_system(fmt="", dist="", fields=None):
    """The package format and distro release of the package for this system:
    ('deb', 'ubuntu24.04'), ('rpm', 'fc45'), ('pacman', ''), or ('', '') when
    no package fits. fmt / dist come from the installed package when it was
    installed as one; otherwise /etc/os-release decides."""
    if fmt in ("deb", "rpm") and dist:
        return fmt, dist
    if fmt == "pacman":
        return fmt, ""
    f = os_release() if fields is None else fields
    ident = f.get("ID", "")
    family = [ident] + f.get("ID_LIKE", "").split()
    version = f.get("VERSION_ID", "")
    if ident == "fedora" and version:
        return "rpm", "fc" + version
    if f.get("UBUNTU_CODENAME") in UBUNTU_BASES:
        return "deb", UBUNTU_BASES[f["UBUNTU_CODENAME"]]
    if ident == "ubuntu" and version:
        return "deb", "ubuntu" + version
    if ident == "debian" and version:                  # Debian, and MX (Debian's os-release)
        return "deb", "debian" + version.split(".")[0]
    if "arch" in family:                                # Arch, CachyOS, EndeavourOS…
        return "pacman", ""
    return "", ""


def release_assets(version):
    """The files of release v<version> from its SHA256SUMS file:
    [{name, url, sha256}]; [] when it can't be fetched (or the release has
    none — releases before 1.2.1)."""
    tag = "v" + version
    try:
        req = urllib.request.Request(DOWNLOAD_URL.format(tag=tag, name="SHA256SUMS"),
                                     headers={"User-Agent": APP})
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read(256 * 1024).decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        m = re.fullmatch(r"([0-9a-f]{64}) [ *]?(\S+)", line.strip())
        if m and "/" not in m.group(2):
            out.append({"name": m.group(2), "sha256": m.group(1),
                        "url": DOWNLOAD_URL.format(tag=tag, name=urllib.parse.quote(m.group(2)))})
    return out


# Arch-based systems build the release from its PKGBUILD (makepkg), so it is
# built against the system's current libraries; the PKGBUILD and its .install
# files are downloaded together into a folder of their own.
#
# From 2.0.0 a release has two packages built from one source: the driver
# (fingerprint-fix-sdcp) and the Manager (galaxybook-fingerprint-manager), with
# the same version; either can be installed alone. With both installed, both
# are downloaded into one folder and installed in one command; with only the
# Manager, only the Manager (e.g. the distro's libfprint has SDCP).
# Releases with one package (before 2.0.0) work as before.
FIX = "fingerprint-fix-sdcp"
MANAGER = "galaxybook-fingerprint-manager"


def pick_asset(assets, version, fmt, dist, fix_installed=True):
    """This system's download among a release's files, or None. GitHub shows
    the '~' of a .deb's version as '.' in file names, so both are accepted.

    One package file: that asset. Several files (the PKGBUILD and its .install
    files, or the driver and Manager packages of a split release): one item
    {name, folder, files: [asset, …], manager_only}, downloaded into one folder."""
    if platform.machine() not in ("x86_64", "amd64"):
        return None
    folder = f"{FIX}-{version}"
    if fmt == "pacman":
        pkgbuild = next((a for a in assets if a["name"] == "PKGBUILD"), None)
        installs = [a for a in assets if a["name"].endswith(".install")]
        if not pkgbuild or not installs:
            return None
        split = any(a["name"] == f"{MANAGER}.install" for a in installs)
        if not fix_installed and not split:
            return None                 # a single-package release can't update the Manager alone
        return {"name": folder, "folder": folder, "files": [pkgbuild] + installs,
                "manager_only": split and not fix_installed}
    if not dist:
        return None
    v, d = re.escape(version), re.escape(dist)
    patterns = {"deb": (rf"{FIX}_{v}-\d+[.~]{d}_amd64\.deb",
                        rf"{MANAGER}_{v}-\d+[.~]{d}_(amd64|all)\.deb"),
                "rpm": (rf"{FIX}-{v}-\d+\.{d}\.x86_64\.rpm",
                        rf"{MANAGER}-{v}-\d+\.{d}\.(x86_64|noarch)\.rpm")}.get(fmt)
    if not patterns:
        return None
    fix = next((a for a in assets if re.fullmatch(patterns[0], a["name"])), None)
    manager = next((a for a in assets if re.fullmatch(patterns[1], a["name"])), None)
    if manager:                                       # a split release
        if fix_installed and not fix:
            return None                               # both are needed together
        files = [manager] + ([fix] if fix_installed else [])
        return {"name": folder, "folder": folder, "files": files,
                "manager_only": not fix_installed}
    return fix if fix_installed else None


def install_command(fmt, path, manager_only=False):
    """The command that installs a download over the installed fix: the package
    file; a folder of packages (installed in one go, so the driver's
    dependency on the same Manager version is met); or for pacman the folder
    holding the PKGBUILD (makepkg builds as the user and asks for the password
    to install — every package it builds, or only the Manager)."""
    quoted = "'" + path.replace("'", "'\\''") + "'"
    if fmt == "pacman":
        if manager_only:
            return f"cd {quoted} && makepkg -s && sudo pacman -U ./{MANAGER}-*.pkg.tar.zst"
        return f"cd {quoted} && makepkg -si"
    if os.path.isdir(path):
        ext, tool = {"deb": ("deb", "apt install"), "rpm": ("rpm", "dnf install")}[fmt]
        return f"cd {quoted} && sudo {tool} ./*.{ext}"
    return {"deb": f"sudo apt install {quoted}",
            "rpm": f"sudo dnf install {quoted}"}[fmt]


def download_item(item, folder, progress=None):
    """Download what pick_asset chose into folder: one package file, or an
    item's files into folder/<item folder>. Returns the file's or that folder's
    path."""
    if "files" not in item:
        return download(item, folder, progress)
    sub = os.path.join(folder, item["folder"])
    for i, f in enumerate(item["files"]):
        download(f, sub, (lambda d, t, i=i: progress(i * 100 + (d * 100 // t if t else 0),
                                                     100 * len(item["files"])))
                 if progress else None)
    return sub


def download(asset, folder, progress=None):
    """Save a release file in folder and check it against GitHub's SHA-256.
    Returns the file's path; raises OSError / ValueError when it fails, and
    leaves no partial file behind. progress(done_bytes, total_bytes)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, os.path.basename(asset["name"]))
    part = path + ".part"
    digest = hashlib.sha256()
    try:
        req = urllib.request.Request(asset["url"], headers={"User-Agent": APP})
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if not asset.get("sha256") or digest.hexdigest() != asset["sha256"]:
            raise ValueError("the downloaded file doesn't match the release's SHA256SUMS — try again")
        os.replace(part, path)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return path


MANAGER_BINS = ("/usr/bin/galaxybook-fingerprint-manager",
                "/usr/local/bin/galaxybook-fingerprint-manager")


def _regular_user():
    """A person's account (UID_MIN..UID_MAX of /etc/login.defs), not a system
    one: the timers are enabled for every user, including the login screen's
    own session (GDM's gdm-greeter users)."""
    lo, hi = 1000, 60000
    try:
        with open("/etc/login.defs") as f:
            for line in f:
                f2 = line.split()
                if len(f2) >= 2 and f2[0] in ("UID_MIN", "UID_MAX") and f2[1].isdigit():
                    lo, hi = (int(f2[1]), hi) if f2[0] == "UID_MIN" else (lo, int(f2[1]))
    except OSError:
        pass
    return lo <= os.getuid() <= hi


REUSE = 55 * 60                    # seconds GitHub's answer is reused by the hourly check


def notify_once():
    """The hourly check (only runs while its timer isn't masked): tell the
    user once about each new release."""
    if not _regular_user():
        return
    _migrate_setting()
    # GitHub's answer is reused for 55 minutes, but not from before this
    # login: the first check of a session always asks (a release made while
    # you were away is seen at once). 55, not 60: the timer runs on the hour
    # and the answer is saved a moment later, so with a full hour the next
    # run found it just under an hour old and asked only every other hour.
    login = _session_start()

    def fresh():
        t = _cache_time()
        return t is not None and t >= login and 0 <= time.time() - t < REUSE

    # Right after login the network may not be up yet: when GitHub has to be
    # asked and can't be reached, try again every 30 s for up to 3 minutes.
    for attempt in range(7):
        had_answer = fresh()
        new = newer_release(max_age=REUSE if had_answer else 0)
        if new or had_answer or fresh() or attempt == 6:
            break
        time.sleep(30)
    if not new:
        return
    try:
        with open(NOTIFIED) as f:
            if f.read().strip() == new:
                return
    except OSError:
        pass
    # Only a release whose files are attached (its SHA256SUMS is there), so the
    # Manager's Update has something to install. The release workflow
    # publishes a release only after attaching them, but re-attaching files
    # replaces them one at a time. Not noted as told: the next hourly check
    # looks again.
    if not release_assets(new):
        return
    show_notification(new)


def show_notification(new):
    """The new-version notification for release NEW (the hourly check and
    'galaxybook-fingerprint-manager updates check'), then noted as told.
    False if it couldn't be shown."""
    title = f"fingerprint-fix-sdcp {new} is available"
    url = f"{REPO_URL}/releases/tag/v{new}"
    # The first line is all that's shown with buttons (notify-update.sh); the
    # rest is for a notification without them
    mine = installed_version()
    first = f"You have {mine}." if mine else ""
    if any(os.access(m, os.X_OK) for m in MANAGER_BINS):
        how = "Open the Fingerprint Manager and click Update to install it, or see the release on GitHub."
    else:
        how = "See the release on GitHub for the files and how to install them."
    msg = f"{first}\n{how}" if first else how
    # Stays until closed, with buttons to the release page and (when it is
    # installed) the Manager: notify-update.sh, started on its own so this
    # doesn't wait for it; a plain notification if that can't be started.
    helper = os.path.join(HERE, "notify-update.sh")
    try:
        subprocess.run(["systemd-run", "--user", "--quiet", "--collect", helper, title, msg, url, new],
                       check=True, timeout=15, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        try:
            subprocess.run(["notify-send", "-u", "critical", "-t", "0", "-a", "Samsung Galaxy Book Fixes", "-i", APP,
                            title, f"{msg}\n{url}"], check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return False            # try again next time
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(NOTIFIED, "w") as f:
            f.write(new + "\n")
    except OSError:
        pass
    return True


# ── "Update now" from the notification ────────────────────────────────────────
# The same steps as the Manager's Update, without opening the Manager:
# notify-update.sh asks --can-update-now (only a Manager installed from a
# package, with a terminal to run it in), and on the button runs --update-now,
# which opens the terminal running --install: download this system's packages
# into /tmp, check them against SHA256SUMS, then update-in-terminal.sh runs the
# install command (both packages together, as the Manager does).
DRIVER_MARKERS = ("/usr/lib/fingerprint-fix-sdcp/installed",
                  "/etc/samsung-galaxybook-egismoc-sdcp.installed")


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def installed_package():
    """How the Manager was installed: ('rpm', 'fc45'), ('deb', 'ubuntu26.04'),
    ('pacman', ''), or ('', '') when not from a package (install.sh). From the
    package's own release, e.g. 2.10.2-1~ubuntu26.04 or 1.fc45."""
    v = _run(["dpkg-query", "-W", "-f=${Status} ${Version}", MANAGER])
    if v.startswith("install ok installed "):
        m = re.search(r"~([a-z]+[0-9.]+)$", v)
        return this_system("deb", m.group(1) if m else "")
    r = _run(["rpm", "-q", "--qf", "%{RELEASE}", MANAGER])
    m = re.fullmatch(r"\d+\.(fc\d+)", r)
    if m:
        return this_system("rpm", m.group(1))
    if _run(["pacman", "-Q", MANAGER]).startswith(MANAGER + " "):
        return "pacman", ""
    return "", ""


def _update_files():
    return [os.path.join(HERE, "update-in-terminal.sh"), os.path.join(HERE, "terminal.py")]


def can_update_now():
    """Can the notification's Update now install it? A Manager from a package,
    this folder's terminal helpers, and a terminal to open."""
    if not all(os.path.isfile(f) for f in _update_files()):
        return False
    if not installed_package()[0]:
        return False
    sys.path.insert(0, HERE)
    import terminal
    return terminal.find_terminal() is not None


def update_now(version):
    """Open the user's terminal running --install VERSION (from the
    notification). False when no terminal could be started."""
    sys.path.insert(0, HERE)
    import terminal
    term = terminal.find_terminal()
    if not term:
        return False
    argv = terminal.command_line(term, [sys.executable, "-I", os.path.realpath(__file__),
                                        "--install", version])
    try:
        subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def install(version):
    """In the terminal: download and check this system's packages of
    release VERSION, then hand over to update-in-terminal.sh to install them."""
    import shutil
    import tempfile
    bold, red, off = "\033[1m", "\033[31m", "\033[0m"
    title = f"Updating fingerprint-fix-sdcp to {version}"
    print(("" if os.environ.get("GBF_OWN_TERMINAL") == "1" else f"\033]0;{title}\a")
          + f"{bold}{title}{off}\n", flush=True)
    folder = None

    own_terminal = os.environ.get("GBF_OWN_TERMINAL") == "1"   # typed, not a window of its own

    def give_up(why):
        print(f"\n{red}{bold}The update didn't start:{off} {why}")
        print(f"See {REPO_URL}/releases/tag/v{version} for the files and how to install them.")
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        if not own_terminal:
            try:
                input("\nPress Enter to close this window.")
            except EOFError:
                pass
        return 1

    fmt, dist = installed_package()
    if not fmt:
        return give_up("the Fingerprint Manager wasn't installed from a package.")
    assets = release_assets(version)
    if not assets:
        return give_up("the release's files couldn't be read from GitHub (no network?).")
    driver = any(os.path.isfile(m) for m in DRIVER_MARKERS)
    item = pick_asset(assets, version, fmt, dist, driver)
    if not item:
        return give_up(f"the release has no packages for this system ({fmt} {dist}).")
    try:
        # A folder of its own in /tmp (update-in-terminal.sh removes it once
        # installed), readable by all: apt reads the files as its _apt user
        folder = tempfile.mkdtemp(prefix=f"galaxybook-update-{version}-", dir="/tmp")
        os.chmod(folder, 0o755)
        files = item["files"] if "files" in item else [item]
        sub = os.path.join(folder, item["folder"]) if "files" in item else folder
        for f in files:
            print(f"Downloading {f['name']} … ", end="", flush=True)
            download(f, sub)
            print("checked")
        path = sub if "files" in item else os.path.join(folder, item["name"])
    except (OSError, ValueError) as e:
        return give_up(f"download failed: {e}")
    print(flush=True)
    cmd = install_command(fmt, path, bool(item.get("manager_only")))
    os.environ["TITLE_SHOWN"] = "1"
    os.execvp("bash", ["bash", os.path.join(HERE, "update-in-terminal.sh"), title, folder, cmd])


# ── The command: galaxybook-fingerprint-manager update / updates … ───────────
# (fingerprint-manager.sh passes these on; the same words as galaxybook-fan's)
def _newest():
    """(newest release's version, or None if GitHub couldn't be reached)."""
    try:
        tag = _latest_tag()
    except Exception:
        return None
    return tag.lstrip("v") if tag else None


def cmd_update():
    """Install the newest release in this terminal."""
    mine, new = installed_version(), _newest()
    if not new:
        print("Couldn't find the newest release on GitHub (no network?)")
        return 1
    if not (version_key(new) and version_key(mine) and version_key(new) > version_key(mine)):
        print(f"fingerprint-fix-sdcp {mine} is up to date (newest release: {new})")
        return 0
    if not release_assets(new):
        print(f"fingerprint-fix-sdcp {new} is being released - its files aren't attached yet, try again in a few minutes")
        return 1
    print(f"fingerprint-fix-sdcp {new} is available (you have {mine}): {REPO_URL}/releases/tag/v{new}")
    os.environ["GBF_OWN_TERMINAL"] = "1"
    return install(new)


def cmd_updates(what):
    if what == "on":
        set_enabled(True)
        print("\"New version\" notifications are on: GitHub checked at login and hourly, told once per version")
    elif what == "off":
        set_enabled(False)
        print("No more \"new version\" notifications. Turn them back on: galaxybook-fingerprint-manager updates on")
    elif what == "status":
        if enabled():
            print("\"New version\" notifications: on (GitHub checked at login and hourly)")
            print("To turn them off: galaxybook-fingerprint-manager updates off")
        else:
            print("\"New version\" notifications: off")
            print("To turn them on: galaxybook-fingerprint-manager updates on")
    elif what == "check":
        mine, new = installed_version(), _newest()
        if not new:
            print("Couldn't find the newest release on GitHub (no network?)")
            return 1
        if not (version_key(new) and version_key(mine) and version_key(new) > version_key(mine)):
            print(f"fingerprint-fix-sdcp {mine} is up to date (newest release: {new})")
            return 0
        if not release_assets(new):
            print(f"fingerprint-fix-sdcp {new} is being released - its files aren't attached yet, try again in a few minutes")
            return 0
        print(f"fingerprint-fix-sdcp {new} is available (you have {mine}): {REPO_URL}/releases/tag/v{new}")
        print("To update, run: galaxybook-fingerprint-manager update")
        if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and show_notification(new):
            print("Notification shown (with Update now / What's new where your desktop has buttons)")
    else:
        print("Usage: galaxybook-fingerprint-manager updates on|off|status|check", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--notify"]:
        notify_once()
    elif args == ["--can-update-now"]:
        sys.exit(0 if can_update_now() else 1)
    elif len(args) == 2 and args[0] == "--update-now":
        sys.exit(0 if update_now(args[1]) else 1)
    elif len(args) == 2 and args[0] == "--install":
        sys.exit(install(args[1]))
    elif args == ["--update"]:
        sys.exit(cmd_update())
    elif len(args) == 2 and args[0] == "--updates":
        sys.exit(cmd_updates(args[1]))
    else:
        sys.exit("Usage: update_check.py --notify | --can-update-now | --update-now VERSION | --install VERSION"
                 " | --update | --updates on|off|status|check")
