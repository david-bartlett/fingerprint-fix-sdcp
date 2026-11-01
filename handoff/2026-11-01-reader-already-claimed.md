# README: what to do when the reader is already in use

PR #134 · Claude · 2026-11-01

## What changed
- `README.md`: new section *If the Reader Says It's Already in Use*, before *Reporting Problems*. CHANGELOG.

## Why
- This answers the CachyOS freeze left open in `2026-11-01-close-while-suspended.md`, where the command `sudo[70644]` was running and why it held on were unknown. The likely cause is Ctrl+Z at a fingerprint prompt.
- David reproduced the mechanism on Fedora: Ctrl+Z on `sudo true` at the prompt, `jobs` shows it suspended, `fprintd-verify` fails with *Device was already claimed*, and `fg` resumes it.
- It fits the 1 Nov log: a stopped `pam_fprintd` can't act on its 30 s timeout, so the driver's own timeout fired; other `sudo` commands ran on the same terminal; and that `sudo` logged no command. It ended with *conversation failed* at 19:53:31, probably when the terminal closed.
- That he pressed Ctrl+Z at 19:49 wasn't proved, but the failure isn't specific to CachyOS, and nothing needs changing in the code.

## Tested
- Ctrl+Z, `jobs`, `fprintd-verify` and `fg` by David on Fedora. The lockout text comes from the CachyOS log.
- Not tested: `faillock --reset` during a lock, or the same steps in fish. Documentation only.

## For the next person
- The third failed login on 1 Nov was never found. README's existing note on `pam_faillock` counting fingerprint scans on KDE's lock screen may or may not be related.
