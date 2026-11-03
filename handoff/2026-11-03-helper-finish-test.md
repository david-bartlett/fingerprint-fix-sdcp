# Closing the Manager during a test

PR #161 · Claude · 2026-11-03

## What changed
- `lib/fingerprint-manager-helper.py`: when stdin closes with a test running, `finish_test()` cancels it and waits up to `EXIT_WAIT_S`. If it's stuck, it restores the drop-in and starts fprintd itself. `cancel_test()` is the old cancel code, now shared.
- PLAN.md §10, CHANGELOG.

## Why
- Codex finding (third pass), confirmed on `6646873`. The test is a daemon thread and `main()` only waited 5 seconds, without cancelling it. A test lasts up to 60, so the process ended first, skipping `Sensor.__exit__`, and fprintd stayed stopped. A distro test could leave the drop-in off until the helper next started.

## Tested
- The real `main()`, `cancel_test()` and `finish_test()` with stand-in tests and `systemctl`: a test that sees the cancel late, and one that's stuck. The old code logged stop with no start in both.
- `py_compile`.
- Not here: the real Manager, sensor, or a distro test.

## For the next person
- `cancel_test()` is called repeatedly because the test may not have reached its cancellable yet.
- `do_test()`'s reply goes to a closed pipe by then. That only raises in the finished thread.
