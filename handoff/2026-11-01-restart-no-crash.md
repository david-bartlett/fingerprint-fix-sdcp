# No crash report when the Manager restarts after an update

PR #130 · Claude · 2026-11-01

## What changed
- `lib/fingerprint-manager.py`: `_closing` is set in `on_quit` (the window's destroy) and in `_restart_into`; `run_job`'s `finish` and `no_access` return straight away once it's set, so a helper reply that arrives while the window is being taken down doesn't touch its widgets. `show_status` also skips a stack page that's gone instead of passing `None` to `child_set_property`.
- CHANGELOG.

## Why
- David on Ubuntu 26.04 (2.10.5): after the Manager's Update and **Restart**, apport showed *fingerprint-manager.py crashed with TypeError in show_status(): Argument 1 does not allow None as a value*. The Manager's install watcher refreshes the status after an update; its reply landed after the old window had been destroyed, `get_child_by_name` returned None. PyGObject passes callback exceptions to `sys.excepthook`, which on Ubuntu is apport's, hence the crash window; elsewhere it's only printed. (Seen before, noted in an earlier session as a crash after update / restart.)

## Tested
- `py_compile`. Not reproduced here (needs the window and the root helper).

## For the next person
- If apport still reports something after Restart, its Traceback names the call: other late callbacks (GLib timeouts, the install watcher) may need the same `_closing` check.
