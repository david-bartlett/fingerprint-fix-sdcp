#!/usr/bin/env python3
# =============================================================================
# Samsung Galaxy Book — fingerprint-fix-sdcp: can the distro's own libfprint
# drive the Galaxy Book's Egis reader over SDCP?
# =============================================================================
#   python3 distro-driver-check.py   → a word on the first line, then a detail
#                                      line (where the library came from):
#     sdcp     0  the distro's egismoc driver is an SDCP driver, from the
#                 distro's own unmodified libfprint package (the fix may no
#                 longer be needed: confirm with the Manager's test)
#     modified 2  an SDCP driver, but the library file doesn't match its
#                 package: another fix copied its build over the distro's
#     foreign  2  an SDCP driver from outside the distro: an unowned file
#                 (e.g. /usr/local), or a package from a COPR, a PPA, the AUR
#                 or a local file — the next distro update may replace it
#     plain    1  it handles the reader, but without SDCP (the distro's
#                 egismoc before SDCP: 1c7a:05a1 only, and it can't keep prints)
#     none     1  no driver for the reader in the distro's libfprint, or the
#                 reader isn't on USB
#     error    3  libfprint's Python bindings couldn't be loaded
#     unknown  4  the reader is on USB, but libfprint didn't list it — some
#                 builds open the device while listing, which needs root
#
# Always runs on the distro's libfprint: started with the fix's LD_LIBRARY_PATH,
# it starts itself again without it. Lists the USB devices; fprintd can keep
# running. Run it as root for a definite answer: some libfprint builds open the
# reader while listing it (the monitor, install.sh and the Manager's helper do).
#
# Used by install.sh (Step 3), the monitor (after a distro libfprint update)
# and the Fingerprint Manager. For testing, CHECK_DRIVER=<driver id> looks for
# another driver (e.g. virtual_sdcp, with FP_VIRTUAL_SDCP=1).
# =============================================================================
import os
import shutil
import subprocess
import sys

if os.environ.get("LD_LIBRARY_PATH"):
    env = {k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}
    os.execve(sys.executable, [sys.executable, os.path.realpath(__file__)] + sys.argv[1:], env)

DRIVER = os.environ.get("CHECK_DRIVER", "egismoc")
SDCP_CLASS = "FpSdcpDevice"     # the shared SDCP device class SDCP drivers derive from


def answer(word, code, detail=""):
    print(word)
    if detail:
        print(detail)
    sys.exit(code)


try:
    import gi
    gi.require_version("FPrint", "2.0")
    from gi.repository import FPrint
except (ImportError, ValueError) as e:
    answer("error", 3, f"libfprint's Python bindings: {e}")


def class_names(obj):
    """The object's GType and every parent type's name."""
    names, t = [], obj.__gtype__
    while t and t.name not in ("GObject", "invalid") and len(names) < 32:
        names.append(t.name)
        t = t.parent
    return names


# ── where the library came from ──────────────────────────────────────────────
def run(*cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return None, ""


def loaded_library():
    """The libfprint file this process loaded (the one fprintd would use
    without the fix)."""
    try:
        with open("/proc/self/maps") as f:
            for line in f:
                path = line.split()[-1] if len(line.split()) >= 6 else ""
                if "/libfprint-2.so" in path:
                    return os.path.realpath(path)
    except OSError:
        pass
    return None


def owner_of(path):
    """(package manager, package) that owns the file, asking each installed
    package manager in turn: having a tool installed (e.g. dpkg on Fedora, to
    build .debs) doesn't make it the one that installed libfprint."""
    if shutil.which("rpm"):
        rc, out = run("rpm", "-qf", "--qf", "%{NAME}\n", path)
        name = out.split("\n")[0].strip()
        if rc == 0 and name and " " not in name:
            return "rpm", name
    if shutil.which("dpkg"):
        for p in (path, path.replace("/usr/lib/", "/lib/", 1)):      # usrmerge
            rc, out = run("dpkg", "-S", p)
            if rc == 0 and ":" in out:
                return "dpkg", out.split(":")[0].strip()
    if shutil.which("pacman"):
        rc, out = run("pacman", "-Qqo", path)
        if rc == 0 and out.strip():
            return "pacman", out.strip()
    return None, None


def provenance(path):
    """('distro' | 'modified' | 'foreign', detail) for a library file, from the
    package manager that owns it (rpm, dpkg or pacman)."""
    if not path:
        return "foreign", "couldn't tell which libfprint was loaded"
    tool, owner = owner_of(path)
    if tool is None:
        if not any(shutil.which(t) for t in ("rpm", "dpkg", "pacman")):
            return "foreign", "couldn't check where libfprint came from (no rpm, dpkg or pacman)"
        return "foreign", f"{path} isn't part of any package"
    if tool == "rpm":
        _, changed = run("rpm", "-V", owner)
        if any(l.split()[-1] == path and l[2:3] == "5" for l in changed.splitlines() if l.strip()):
            return "modified", f"{path} was changed after the {owner} package installed it"
        _, vendor = run("rpm", "-q", "--qf", "%{VENDOR}", owner)
        if vendor.strip() != "Fedora Project":
            return "foreign", f"{owner} is from {vendor.strip() or 'an unknown source'}, not Fedora"
        return "distro", f"{owner} from Fedora"
    if tool == "dpkg":
        _, changed = run("dpkg", "--verify", owner)
        name = os.path.basename(path)
        if any(l[2:3] == "5" and os.path.basename(l.split()[-1]) == name
               for l in changed.splitlines() if l.strip()):
            return "modified", f"{path} was changed after the {owner} package installed it"
        _, policy = run("apt-cache", "policy", owner)
        sources, mine = [], False
        for line in policy.splitlines():
            if line.lstrip().startswith("***"):
                mine = True
                continue
            if mine:
                if not line.startswith("        "):      # the next version's line
                    break
                sources.append(line.split()[1] if len(line.split()) > 1 else "")
        repos = [x for x in sources if x != "/var/lib/dpkg/status"]
        if not repos:
            return "foreign", f"{owner} was installed from a local file, not a repository"
        third = [x for x in repos if "ppa.launchpad" in x]
        if third and len(third) == len(repos):
            return "foreign", f"{owner} is from a PPA ({third[0]})"
        return "distro", f"{owner} from {repos[0]}"
    if tool == "pacman":
        _, changed = run("pacman", "-Qkk", owner)
        if any(path in l and "checksum mismatch" in l.lower() for l in changed.splitlines()):
            return "modified", f"{path} was changed after the {owner} package installed it"
        _, foreign = run("pacman", "-Qqm")
        if owner in foreign.split():
            return "foreign", f"{owner} is from the AUR or a local package, not a repository"
        return "distro", f"{owner} from the distro's repositories"
    return "foreign", f"couldn't check where {path} came from"


def reader_on_usb():
    for d in os.listdir("/sys/bus/usb/devices"):
        try:
            with open(f"/sys/bus/usb/devices/{d}/idVendor") as f:
                if f.read().strip() != "1c7a":
                    continue
            with open(f"/sys/bus/usb/devices/{d}/idProduct") as f:
                if f.read().strip() in ("05a5", "05a1"):
                    return True
        except OSError:
            continue
    return False


ctx = FPrint.Context()
ctx.enumerate()
for dev in ctx.get_devices():
    if dev.get_driver() != DRIVER:
        continue
    names = class_names(dev)
    if SDCP_CLASS in names:
        where, detail = provenance(loaded_library())
        if where == "distro":
            answer("sdcp", 0, detail)
        answer(where, 2, detail)
    answer("plain", 1, " → ".join(names))
# The reader is there but libfprint didn't list it: either no driver claims
# it, or a driver failed to open it (no permission) and libfprint skipped it.
# Only root can tell those apart.
if DRIVER == "egismoc" and reader_on_usb() and os.geteuid() != 0:
    answer("unknown", 4, "the reader is on USB but libfprint didn't list it — run as root to be sure")
answer("none", 1)
