# Arch package (CachyOS, Arch, EndeavourOS, …)

`PKGBUILD` packages this repository's working tree (local changes included) and builds the driver commit named in `DRIVER` from the public fork. `VERSION` and `DRIVER` are read from the repository, so nothing here needs editing for a new release.

```bash
cd packaging/arch
makepkg -si                      # build, then install with pacman
```

Rebuilding the same version: raise `pkgrel` or use `makepkg -sif`.

## Where it installs

| Path | What |
| --- | --- |
| `/usr/lib/fingerprint-fix-sdcp/` | driver library, `sensor-check`, monitor / boot / login check scripts, `installed` marker, `manager/` |
| `/usr/lib/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf` | points fprintd at the driver while the reader is present (`fprintd-env.sh` decides each time fprintd starts) |
| `/usr/lib/systemd/system/`, `/usr/lib/systemd/user/` | monitor and boot-check services, login-check timer, session target |
| `/usr/share/polkit-1/` | monitor rule, Manager policy |
| `/usr/bin/galaxybook-fingerprint-manager`, `/usr/share/applications/`, `/usr/share/icons/` | the Manager |
| `/etc/xdg/autostart/fingerprint-fix-sdcp-session.desktop` | starts `graphical-session.target` on desktops that don't |

Install enables the boot check and the per-user login check (they start at the next boot / login) and restarts fprintd. Fingerprint login (PAM) is not touched: turn it on in the Manager. Removal keeps enrolled fingerprints and undoes the sudo / polkit-1 lines the Manager added.

## Testing on CachyOS

1. **Remove an `install.sh` install first**, keeping fingerprints (pacman refuses to install over its menu entry and polkit policy):
   `sudo bash uninstall.sh`
   This also removes the fingerprint lines it added to sudo and polkit-1 — turn them back on in the Manager afterwards.
2. `cd packaging/arch && makepkg -si`
3. fprintd uses the driver: `fprintd-list "$USER"`, then `sudo grep fingerprint-fix-sdcp /proc/$(pidof fprintd)/maps`
4. `fprintd-verify` matches the existing fingerprints.
5. The Manager opens from the app menu; *About* shows the version and driver `3b0ee1f`; the fingerprint-login switch works.
6. `systemctl is-enabled samsung-galaxybook-fprint-sdcp-boot-check.service` and `systemctl --user is-enabled samsung-galaxybook-fprint-sdcp-user-check.timer` both say `enabled`.
7. Reboot: `journalctl -b -u samsung-galaxybook-fprint-sdcp-boot-check` shows the check ran; with no fingers enrolled, a notification points to the Manager about 10 s after login.
8. Upgrade: raise `pkgrel`, `makepkg -si` — fingerprints still verify.
9. Remove: `sudo pacman -R fingerprint-fix-sdcp` — `/var/lib/fprint` is still there, fprintd no longer maps the driver. Reinstall and verify again.

## The release PKGBUILD

Each GitHub release gets a `PKGBUILD` (from `PKGBUILD.release.in`) that builds that release from its tarball, plus the built `.pkg.tar.zst`. The same file can go to the AUR later, with a `.SRCINFO` (`makepkg --printsrcinfo > .SRCINFO`). Both PKGBUILDs use the shared `packaging/build-driver.sh` and `packaging/install-files.sh`; see `packaging/README.md`.
