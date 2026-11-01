# Reader keeps working after suspending during a scan

PR #133 · Claude · 2026-11-01

## What changed
- New `lib/patches/0001-close-while-suspended.patch` (libfprint core: `fp-device.c`, `fpi-device.c`, `fp-device-private.h`): `fp_device_close()` no longer refuses while suspended. It keeps the task and runs the driver's close when `fp_device_resume()` finishes, including when the device was removed during the sleep.
- `lib/patches/README.md`, `README.md`, CHANGELOG; PLAN.md §4, §5 and §11.

## Why
- Fedora log of 31 Oct: lock screen verifying, suspend, *Cannot run while suspended*, then `ReleaseDevice failed … still busy`.
- **Corrects the handover:** fprintd doesn't keep the claim. `dev_close_cb` clears it even when the close fails, while libfprint keeps the device open, so every later Claim fails with *The device has already been opened!* until fprintd exits. Confirmed by test. The `left some devices open` warning fits fprintd's idle exit with the device still open (from reading the code).
- Chose deferring over closing at once: an immediate Release would let the client Claim while still suspended, and `fp_device_open()` refuses that too. With the deferred close, Release's reply and so the retry come after the resume.

## Tested
- libfprint at `3b0ee1f`, unpatched and patched: 4 new unit tests in `tests/test-fpi-device.c` (in the PR, not in the patch): 3 fail unpatched (the cancelled-close one is a guard and passes on both), all pass patched. fpi-device, fp-device, fp-sdcp-device, fp-context and fpi-ssm pass on both.
- Driver replays, including `egismoc-suspend`, `egismoc-cancel` and `egismoc`: 25 of 28 pass on both. `egismoc-05a1`, `-0586` and `-0587` fail on both: the fork's `tests/meson.build` disables them (*needs an SDCP capture*).
- Real fprintd 1.94.5 with a mock logind and virtual devices, new `test_release_while_suspended`: unpatched gives the log's *Release failed … still busy*; patched, Release waits, finishes on resume, and the next client gets `verify-match`. Full suite, 524 tests: patched passes all (4 skipped); unpatched fails only the two runs of the new test.
- `packaging/build-driver.sh` applied the patch and built the egismoc-only library from a clean `3b0ee1f`; `git apply --check` is clean too.
- David's laptop, real sensor, 1 Nov (each test showed *Cannot run while suspended*, then *closing it on resume*, with no `ReleaseDevice failed` or `already been opened`):
  - CachyOS KDE: suspend during a `sudo` prompt, and at the lock screen.
  - Ubuntu GNOME: suspend during a `sudo` prompt, and at the lock screen (the lock screen restarted fingerprint after the wake).
  - Fedora 45 KDE: suspend during a `sudo` prompt, and at the lock screen, where one fprintd process went through two suspends 7 seconds apart: the same double suspend as the 31 Oct log.
- Not tested: hibernate, Mint, MX. fprintd for the workspace tests came from Ubuntu's source package, as freedesktop's GitLab isn't reachable from Claude's workspace, so newer upstream code than 1.95.2 / 1.94.5 wasn't checked.

## For the next person
- **Doesn't cover the CachyOS freeze (1 Nov, 19:49 to 19:53).** That was during `webcam-fix-book5`'s uninstall and install, with no suspend. `sudo[70644]` stayed in `pam_fprintd` for 3 min 40 s and held the reader, so other clients got *Device was already claimed*. Failed passwords then tripped `pam_faillock` for 10 minutes, so `sudo` and polkit couldn't authenticate and the restart never ran. fprintd itself stopped in under a second, and the log has no kernel or USB hang. That corrects the handover's "fprintd couldn't stop". Still unknown: which command that `sudo` was (it logged none) and why it held on. The driver's 30 s finger timeout fired at 40 s, before which `pam_fprintd` should have given up, so it may have been stopped or blocked.
- **CachyOS's sudo does use the fingerprint** (`pam_fprintd(sudo:auth)` in the log). The handover said it doesn't.
- **Separate lead, 1 Nov 07:13:** the camera relay printed *Verification timed out*, so a hidden `sudo` in it (Andy's `camera-relay` calls `sudo modprobe v4l2loopback`) probably held the reader for 30 s.
- If fprintd is stopped while a Release is waiting, it logs *Device was not cleaned up properly before being finalized* and exits normally (rc 0). Only fatal under fprintd's test flag `G_DEBUG=fatal-criticals`.
- A close that's cancelled while waiting is only noticed at resume.
- `run_deferred_close` is a pointer in `FpDevicePrivate` because `fpi-device.c` is in the private static library and can't call `fp-device.c`.
- `Needed-if-source-has:` uses the `fp_device_suspend` doc line, as `is_suspended` checks appear in about eight functions. `build-driver.sh` doesn't read that line (PLAN.md §11).
- Ubuntu's slow screen after lifting the lid isn't caused by this patch: it also happened with fprintd masked. In that run suspend started 30 s after the lid closed, with the lid already open. Not looked into.
- Offer upstream after David's testing: the fork first, then libfprint, with the unit tests from the PR.
