# Records aren't dead when the sensor can't be listed

PR #157 · Claude · 2026-11-03

## What changed
- `do_status()`: with no `STORAGE_LIST`, a record's `on_sensor` is `None`, not `False`.
- Manager: `rec_kind()` shows *Can't check sensor*, with no *Remove dead record* in its menu, and the Details and Test messages say why.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding (second pass), reproduced by Codex with the real `do_status()` and a mocked sensor, and confirmed here by reading `1fa414d`. The empty `chip` made every readable record look gone, so the Manager offered to remove working fingerprints. PR #153 fixed the shared file for this case, but not the records.

## Tested
- `rec_kind()` for on, gone, unlisted, unreadable and other-driver records, and the helper's expression for listed, not on the sensor, not listed and no print.
- `py_compile`.
- Not here: `do_status()` from end to end, the real window. A driver without `STORAGE_LIST` isn't available: egismoc has it.

## For the next person
- `on_sensor` has three values. Treat only `False` as gone: test `is False`, not `not`.
- Test stays disabled for these records, as a check that they match needs the sensor's list.
