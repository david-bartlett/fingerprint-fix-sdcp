# Say when the update notification closes by itself

PR #141 · Claude · 2026-11-02

## What changed
- The README's collapsed section on the update check says the notification also closes once the new version is installed some other way.

## Why
- David pointed out that the README only mentioned closing it by hand.

## Tested
- Wording checked against `lib/notify-update.sh`. The notification itself wasn't tested closing here.
