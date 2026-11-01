# Update now: "already installed" when it is

PR #131 · Claude · 2026-11-01

## What changed
- `lib/update_check.py` `install(VERSION)`: if the installed version (`installed_version()`, read at that moment) is VERSION or newer, it prints *fingerprint-fix-sdcp X is already installed - nothing to update.* and stops (in a window of its own: closes after 10 s or Enter), before downloading anything. Also covers `galaxybook-fingerprint-manager update` racing with the Manager.
- CHANGELOG.

## Why
- David on Ubuntu: after updating with the Manager, the new-version notification was still up (it stays until closed); its Update now downloaded both packages and apt found nothing to install. galaxybook-fan's `update` already says "up to date".

## Tested
- `install("2.10.6")` with installed 2.10.6 and 2.10.7: says already installed, returns 0, never reaches the package / download steps. `py_compile`.
