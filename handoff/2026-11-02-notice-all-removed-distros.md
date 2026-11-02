# Name every removed distro in the notice

PR #NUMBER · Claude · 2026-11-02

## What changed
- `lib/fingerprint-manager.py`: new `forgotten_text()` builds one message for all the installs found gone at a start, and `_apply_mode` shows it once.
- PLAN.md §6 and the CHANGELOG.

## Why
- David removed CachyOS and MX Linux, and the notice named only CachyOS. `_apply_mode` called `message()` once per install, and a message replaces the one before it, so only the last was seen.
- Only the notice was wrong. `_check_installs` took both out of the shared file, confirmed in David's export from 2 Nov: Fedora, Mint and Ubuntu are left, in `installs` and on all 6 templates, and the 6 templates and their records are still there.

## Tested
- `forgotten_text()` extracted from the source and run on: one, two, three, two installs of one distro, a mix of those, and two different reasons.
- `_apply_mode` run with a stand-in window: two gone gives one `message()` call naming both, none gives no call.
- `py_compile`.
- Not here: the real window, a real EFI partition, the sensor.

## For the next person
- If `multi` turns on at the same start as a forget, *Other distros on this laptop use the sensor too…* still replaces this notice. Not changed: it needs an install to be found and another to go at one start.
- Any loop calling `message()` has this problem, as there's no queue.
