# Only announce releases whose files are attached

PR #<n> · Claude · 2026-10-31

## What changed
- `.github/workflows/release-packages.yml`: `gh release create --draft`; after the upload, a **Publish the release** step runs `gh release edit --draft=false --latest`, only if the release is still a draft (a re-run for an older tag mustn't make it the latest).
- `lib/update_check.py` `notify_once()`: no notification while `release_assets(new)` is empty (no `SHA256SUMS` yet); not noted as told, so the next hourly check looks again.
- `lib/fingerprint-manager.py` `check_for_update()`: no Update button while the new release has no `SHA256SUMS`.
- CHANGELOG, README (update check details), PLAN.md §4.

## Why
- The release was published by `gh release create` before `gh release upload` attached the files, so `releases/latest` pointed to a release with no packages for a moment; a check then could announce it and Update had nothing to install. Same change as galaxybook-fan's PR #28.

## Tested
- `py_compile`, the workflow's YAML; `notify_once` with stand-ins for GitHub (see the PR).
- Not tested: a real release with the draft step (the next release is the first: the release should only appear at the end of its run, marked Latest).

## For the next person
- `release_assets` returns `[]` on a network error too: then the check also just waits for the next hour.
