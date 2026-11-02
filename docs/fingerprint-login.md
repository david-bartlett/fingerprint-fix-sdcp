# Fingerprint login

[← Back to the README](../README.md)

How to enrol a fingerprint, and how to turn fingerprint login on or off, with the extra detail for Arch-based distros.

## Enrolling a Fingerprint

Open **Galaxy Book Fingerprint Manager** from the app menu and click a grey finger, or use your desktop's settings: KDE: System Settings → Users → Fingerprint Authentication · GNOME: Settings → System → Users → Fingerprint Login · Mint: Menu → Fingerprints · Xfce (e.g. MX Linux) has none: use the Manager or `fprintd-enroll`. No reboot is needed. Check with `fprintd-verify`.

If `fprintd-verify` never matches, those fingers were enrolled with another driver (e.g. your distro's own, before this fix): the Manager marks them **Other driver** and offers to delete and enrol them again.

## Turning Fingerprint Login On or Off

`fingerprint-pam.sh` turns fingerprint for login, sudo and admin prompts on or off the way each distro expects — the installer and the Galaxy Book Fingerprint Manager both use it, so it also puts things right if the PAM setting was lost:

```bash
bash tools/fingerprint-pam.sh status
sudo bash tools/fingerprint-pam.sh enable
sudo bash tools/fingerprint-pam.sh disable    # enrolled fingerprints are kept
```

| Distro | How |
| --- | --- |
| Fedora | `authselect enable-feature with-fingerprint` / `disable-feature` |
| Ubuntu, Debian, MX Linux | `pam-auth-update` profile `fprintd` (from `libpam-fprintd`) |
| Linux Mint | `pam-auth-update` profile `fingwit` (Mint's own; it conflicts with `fprintd`'s, which is turned off) |
| Arch-based | `arch-pam.sh` — sudo and polkit-1 (below) |

## Fingerprint for sudo and Admin Prompts on Arch-Based Distros

Arch, CachyOS, Manjaro, EndeavourOS and other Arch-based distros have no authselect or pam-auth-update, so the installer asks:

```
Enable fingerprint for sudo and admin prompts? [Y/n]
```

It waits for an answer (no time limit, because it changes how you log in to sudo) and is skipped when there is no terminal. `FPRINT_PAM=1` or `FPRINT_PAM=0` answers it in advance. The same is available any time with `fingerprint-pam.sh`, or directly with `arch-pam.sh`:

```bash
sudo bash tools/arch-pam.sh enable     # sudo + polkit-1 (pkexec, graphical admin prompts)
sudo bash tools/arch-pam.sh status
sudo bash tools/arch-pam.sh disable    # removes exactly what 'enable' added
sudo bash tools/arch-pam.sh update     # brings lines added by an older version up to date
```

What it does:

- Adds one `auth sufficient pam_fprintd.so` line, marked with a comment, above the first `auth` line of `/etc/pam.d/sudo` and `/etc/pam.d/polkit-1`. `polkit-1` normally lives only in `/usr/lib/pam.d`, so it is copied to `/etc/pam.d` first (that copy takes precedence).
- In `polkit-1` the line has `timeout=10`. Admin dialogs show a password box straight away, but polkit only checks a typed password once the fingerprint step gives up — after 3 tries or 30 seconds by default (a known polkit limitation, the same on Fedora: [KDE Discuss](https://discuss.kde.org/t/polkit-authentication-not-usable-with-password-only-fingerprint/46150)). With `timeout=10` a typed password goes through after at most 10 seconds; touching the sensor still works at once. `sudo` keeps the default, since Ctrl+C there skips straight to the password.
- Keeps a backup of each file (`*.bak-samsung-galaxybook`), and checks the edited file still contains every original line.
- Leaves any file that already mentions `pam_fprintd` alone, so hand edits are never overwritten and running it twice changes nothing.
- Is safe before enrolling: with no finger enrolled, `pam_fprintd` reports "not available" and you are asked for your password as usual.
- Uninstalling the fix leaves them, so fingerprint login keeps working once your distro's libfprint has SDCP. To take them out, run `sudo bash tools/arch-pam.sh disable` (or turn fingerprint login off in the Galaxy Book Fingerprint Manager) first: only the marked lines are removed, and the `polkit-1` copy is deleted if it was created by the fix and not changed since.

**Not changed:** the **KDE lock screen** already uses the fingerprint through its own `kde-fingerprint` service, and the **login screen** is left password-only (with fingerprint, Plasma's login screen waits for the sensor after you type a password).

Test in a new terminal with `sudo -k; sudo true` and `pkexec true`. Keep a root terminal open (`sudo -i`) while testing PAM changes.

**Tested** on CachyOS (KDE): `enable`, `disable`, `enable` again, with sudo and pkexec both accepting the fingerprint (2026-10-25).

**If the lock screen locks you out after a few successful fingerprint unlocks** — a known KDE Plasma 6 bug where `pam_faillock` counts successful fingerprint scans as failures — copy `/usr/lib/pam.d/kde-fingerprint` to `/etc/pam.d/kde-fingerprint` and use:
```
#%PAM-1.0
auth [success=1 ignore=ignore module_unknown=die default=bad] \
     pam_fprintd.so max-tries=3 timeout=65535
auth [default=die] pam_faillock.so authfail
auth optional pam_permit.so
auth required pam_faillock.so authsucc
auth required pam_env.so
account include system-local-login
password required pam_deny.so
session include system-local-login
```

> ⚠️ Always keep a root terminal open while editing PAM files.
