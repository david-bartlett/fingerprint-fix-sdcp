# Pictures of the three update notifications

PR #151 · Claude · 2026-11-03

## What changed
- New `images/update-notification-driver.png`, `-manager.png` and `-both.png`, replacing `images/update-notification.png`.
- README: both packages under *Updating*, the driver under *With only the driver*. `docs/driver-only.md`: the driver. `docs/install-options.md`: the Manager, under *Installing only one package*.

## Why
- The old picture showed `fingerprint-fix-sdcp 2.11.4 is available`, the wording before PRs #149 and #150.

## Tested
- Each picture viewed, and each path in the docs checked against `images/`.
- Not a code change, so nothing else to run.

## For the next person
- **These are drawn, not screenshots.** They were made from an HTML page in the layout, colours and icon of David's KDE screenshot, as this session couldn't reach the laptop. David compared them with his notification and is happy with them.
- They show 2.13.2 and 2.13.1 as examples. They're only a picture of the wording, so they don't need changing every release.
