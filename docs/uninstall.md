# Uninstalling

[← Back to the README](../README.md)

How to remove the fix, or only one of its two packages, and what's kept.

## Installed from a package

Remove both with your package manager:

```bash
sudo dnf remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Fedora
sudo apt remove fingerprint-fix-sdcp galaxybook-fingerprint-manager      # Ubuntu, Mint, Debian, MX
sudo pacman -R fingerprint-fix-sdcp galaxybook-fingerprint-manager       # Arch, CachyOS
```

## Installed with install.sh

From its folder:

```bash
sudo bash uninstall.sh
```

Enrolled fingerprints are always kept, so reinstalling uses them again, and fingerprint login stays as you set it.

## Removing only one part, and what's kept

**Only the driver** — e.g. once your distro's own libfprint handles the reader with SDCP (the monitor tells you, and the Galaxy Book Fingerprint Manager offers it): `sudo dnf remove fingerprint-fix-sdcp` (or `apt remove` / `pacman -R` the same name), or `sudo bash uninstall.sh --driver-only`. fprintd goes back to your distro's libfprint; the Manager, its checks and fingerprint login stay.

**Only the Manager:** `sudo dnf remove galaxybook-fingerprint-manager` (or `apt remove` / `pacman -R`), or `sudo bash uninstall.sh --manager-only`. The driver, fingerprint login and enrolled fingerprints stay.

Either way, enrolled fingerprints are always kept — fprintd's records and the templates on the sensor — so reinstalling uses them again. To delete fingers, use the Manager before uninstalling (while the driver is still loaded, so the templates leave the sensor too). Both remove the drop-in, the library, the Manager and the monitor; nothing needs reinstalling because the distro libfprint was never replaced. Fingerprint login is left as you set it, on every distro, so it keeps working once your distro's libfprint has SDCP.

To switch an `install.sh` copy off **temporarily** instead:

```bash
sudo mv /etc/systemd/system/fprintd.service.d/samsung-galaxybook-egismoc-sdcp.conf /root/
sudo systemctl daemon-reload && sudo systemctl restart fprintd
```
