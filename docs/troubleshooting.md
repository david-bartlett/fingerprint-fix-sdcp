# Troubleshooting

[← Back to the README](../README.md)

What to do when the reader is busy, and what to know when Windows shares the laptop.

## If the Reader Says It's Already in Use

Only one program can use the reader at a time. If `fprintd-verify`, the Manager or a prompt fails with *Device was already claimed*, something still has it, usually a `sudo` waiting for a finger.

**Don't press Ctrl+Z at a fingerprint prompt.** It pauses `sudo` in the background, and a paused `sudo` keeps the reader. Press **Ctrl+C** to cancel instead. If you've already pressed Ctrl+Z, go back to that terminal and run:

```bash
jobs   # shows the paused sudo
fg     # brings it back
```

Then press Ctrl+C or enter your password. `kill` won't work, because `sudo` runs as root. Closing the terminal also frees the reader.

While the reader is held, prompts ask for your password instead. **Go carefully:** after 3 failed passwords, Arch-based distros lock your account for 10 minutes (*The account is locked due to 3 failed logins*), and even the right password fails until then. To clear it early, run `sudo faillock --user $USER --reset` from a root session that's already open, or restart.

## If the Shared Fingerprint File Can't Be Read

The Galaxy Book Fingerprint Manager keeps `EFI/samsung-galaxybook/fingerprint-slots.json` on the EFI partition, so distros can share fingerprints. If that file is damaged, or was written by a newer version, the Manager tells you and leaves it as it is. Sharing and Reset stay off, as it can't tell which fingerprints other distros use. Enrolled fingerprints keep working.

- If another distro on the laptop has a newer version, update this one to match.
- Otherwise, move the file aside, then open the Manager on each distro to write it again. On Fedora, Ubuntu and Mint it's usually:

  ```bash
  sudo mv /boot/efi/EFI/samsung-galaxybook/fingerprint-slots.json /boot/efi/EFI/samsung-galaxybook/fingerprint-slots.json.bad
  ```

  The Manager's **Details…** button shows the path on your system.

## Dual-Boot With Windows

The sensor has a single template store shared by every OS:

- **Windows** removes templates it did not create when its biometric service starts, so booting Windows with the sensor enabled deletes your Linux enrolments. Disable the fingerprint device in Windows Device Manager if you dual-boot. When Windows is installed on the laptop, the Galaxy Book Fingerprint Manager shows this reminder at the bottom of its window (hide it with **Got it**; ☰ → **Remind me about Windows** brings it back). It looks for a Windows Boot Manager boot entry whose partition still exists, and Windows' own partitions (NTFS or BitLocker, plus the Microsoft Reserved or Windows Recovery partition) — no password needed, and nothing is mounted.
- **fprintd** deletes an unknown template when you enrol a finger that matches it, and deletes unknown templates when the sensor is full. Enrolling the same finger in two Linux installs breaks the first one — use a different finger per install, or share one enrolment between installs (see [Multi-Distro Mode](multi-distro.md)).
