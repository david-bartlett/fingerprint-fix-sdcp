# Plain finger names in messages from the scripts

PR #189 · Claude · 2026-11-22

## What changed
- `lib/fingerprint-manager.py` `summarise()` (the one line shown from a script's output) turns fprintd's finger names (`right-index-finger`, `left-thumb`) into plain words. The import message now reads *Imported left index finger, right thumb… for davie*. The full output behind **Details…** is unchanged.

## Why
- Seen in David's EndeavourOS Reset and import test on 22 Nov. PLAN.md §7 says to name fingers, not files.

## Tested
- `summarise()` under Xvfb on the import line, an import from another user, the "Replacing records" line, an error naming something else with a hyphen (left alone), and a plain line.
