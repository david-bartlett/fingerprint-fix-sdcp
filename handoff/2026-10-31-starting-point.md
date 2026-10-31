# Starting point: where things stand at 2.10.0

PR #120 · Claude · 2026-10-31

## What changed
- Nothing in the code: this is the first note, describing the state of the project when handoff notes started. Released: **2.10.0** (29 Oct 2026). Earlier releases from 2.4.2 to 2.8.1 may have been deleted from GitHub; 2.9.0 is kept for testing updates.

## State of things
- Two packages (driver, Galaxy Book Fingerprint Manager); rpm (Fedora 44/45), deb (Debian 13, Ubuntu 24.04/26.04), Arch PKGBUILD; `install.sh` for others. See PLAN.md.
- The Manager has a **single-distro mode** (default) and a **multi-distro mode** (when the shared slots file on the EFI partition lists another install that still exists). Each install notes its partition there; installs whose partition was deleted or reformatted are forgotten at the next start.
- Sharing fingerprints between distros goes through the records on the EFI partition (import offer at start, ☰ → Import from other distros…). The Manager no longer writes or reads `~/fingerprint-export.tgz`; the command-line tools and `install.sh` still do.
- Removed fingers are kept (moved aside) while they can be restored; there's no "last 5 folders" limit any more.
- Fingerprints tab: **Remove all from <distro>…** (restorable). ☰ → **Reset <distro>…** (multi mode only) erases the slots only this distro uses.
- Information panel: alerts blink and stay; plain details (a clicked finger/slot) don't blink and go after 5 s.

## Tested
- Everything up to 2.10.0 was tested by David on his Galaxy Book5 Pro (Fedora 45, Ubuntu 26.04, Linux Mint 22.3, MX Linux 25, CachyOS with Limine, plus Windows).
- Not yet seen on real hardware: a distro being **detected as gone** after its partition is deleted or reformatted (only tested with made-up `lsblk` layouts), and the Manager **returning to single-distro mode** afterwards. Distros that only ran 2.9.0 or older have no location in the file and stay listed until they run 2.10.0 or are forgotten by hand (Other distros… → Forget).

## For the next person
- Ideas not started (ask David first): remove the helper's unused `export` action; drop the finger cards' hover tooltip (the information panel shows the details now); sharing for driver-only installs; offering to forget the old install when a reinstalled distro imports its fingers.
