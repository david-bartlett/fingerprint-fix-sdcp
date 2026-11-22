# Attestation check: name the workflow and the tag

PR #186 · Claude · 2026-11-22

## What changed
- `.github/release-install.md` (on every release page): the `gh attestation verify` command now adds `--signer-workflow david-bartlett/fingerprint-fix-sdcp/.github/workflows/release-packages.yml --source-ref refs/tags/v@VERSION@`. The release notes fill in the version.
- The comment in `release-packages.yml` and the Unreleased CHANGELOG line now say the same.

## Why
- Codex's review: `-R` alone only checks the repository, so an attestation from another workflow or ref in it would pass, while the text promised the release workflow and the exact tag.

## Tested
- `sed "s/@VERSION@/2.15.0/g"` on the file shows the right command. Workflow YAML parses, and `bash -n .github/release-notes.sh` passes.
- **Not tested:** a real `gh attestation verify` against a release. That needs a release made after PR #182.

## For the next person
- After the next release, run the command from its release page on one file: it should say it's verified.
