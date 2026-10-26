#!/usr/bin/env python3
# =============================================================================
# fingerprint-fix-sdcp — is a newer release on GitHub? (runs as the user)
# =============================================================================
# Used by the Fingerprint Manager (its Update button) and by the login check:
#
#   update_check.py --notify    at login: one notification per new release
#
# Asks GitHub at most once a day; both share one cache, so together they still
# make one request a day. When GitHub can't be reached (no network yet), the
# next login or Manager start tries again. The Manager's menu item "Check for
# new versions" (update_check=0 in its settings) turns both off.
# =============================================================================
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

APP = "galaxybook-fingerprint-manager"      # the icon, and the settings / cache folder name
REPO_URL = "https://github.com/david-bartlett/fingerprint-fix-sdcp"
RELEASES_API = "https://api.github.com/repos/david-bartlett/fingerprint-fix-sdcp/releases/latest"
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


def latest_release(max_age=24 * 3600):
    """The newest release's tag (e.g. 'v1.0.2'), or None when unknown.
    Asks GitHub at most once per max_age seconds. 'No release' (404 — none yet,
    or the repository not public) is remembered for a day too; a failed
    connection is not, so the next try asks again."""
    now = time.time()
    try:
        with open(RELEASE_CACHE) as f:
            checked, tag = f.read().split()
        if 0 <= now - float(checked) < max_age:
            return None if tag == "-" else tag
    except (OSError, ValueError):
        pass
    try:
        req = urllib.request.Request(RELEASES_API, headers={
            "Accept": "application/vnd.github+json", "User-Agent": APP})
        with urllib.request.urlopen(req, timeout=10) as r:
            tag = json.load(r).get("tag_name") or None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None             # rate limit, server trouble: ask again next time
        tag = None
    except Exception:               # no network yet, DNS, timeout
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
