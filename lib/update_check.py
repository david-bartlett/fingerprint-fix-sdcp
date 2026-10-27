#!/usr/bin/env python3
# =============================================================================
# fingerprint-fix-sdcp — is a newer release on GitHub? (runs as the user)
# =============================================================================
# Used by the Fingerprint Manager (its Update button) and by the login check:
#
#   update_check.py --notify    at login: one notification per new release
#
# The Manager asks GitHub each time it starts; the login check asks at most
# once a day (both share one cache). When GitHub can't be reached (no network
# yet), the next login or Manager start tries again. The Manager's menu item
# "Check for new versions" (update_check=0 in its settings) turns both off.
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


def enabled():
    """False when the Manager's 'Check for new versions' is switched off."""
    try:
        with open(SETTINGS) as f:
            return not any(l.strip() == "update_check=0" for l in f)
    except OSError:
        return True


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
# the same version, and the driver requires that exact Manager. Both are then
# downloaded into one folder and installed in one command — or only the
# Manager, once the driver has been removed (the distro's libfprint has SDCP).
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


def notify_once():
    """At login: tell the user once about each new release."""
    if not enabled():
        return
    new = newer_release()
    if not new:
        return
    try:
        with open(NOTIFIED) as f:
            if f.read().strip() == new:
                return
    except OSError:
        pass
    title = f"Samsung Galaxy Book — fingerprint-fix-sdcp {new} is available"
    msg = "Open Galaxy Book Fingerprint Manager and click Update to see how to install it."
    # Stays until closed, with an "Open Fingerprint Manager" button
    # (notify-open-manager.sh, started on its own so this doesn't wait for it);
    # a plain notification if that can't be started.
    helper = os.path.join(HERE, "notify-open-manager.sh")
    try:
        subprocess.run(["systemd-run", "--user", "--quiet", "--collect", helper, title, msg],
                       check=True, timeout=15, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        try:
            subprocess.run(["notify-send", "-t", "0", "-a", "Samsung Galaxy Book Fixes", "-i", APP,
                            title, msg], check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return                  # try again next login
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(NOTIFIED, "w") as f:
            f.write(new + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    if sys.argv[1:] == ["--notify"]:
        notify_once()
    else:
        sys.exit("Usage: update_check.py --notify")
