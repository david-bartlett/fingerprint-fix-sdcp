# Build attestations on release files

PR #182 · Claude · 2026-11-17

## What changed
- The release workflow's publish job ends with `actions/attest-build-provenance@v3` over `dist/*`, after the release is published, with `continue-on-error: true`. The job has its own permissions (`contents: write`, `id-token: write`, `attestations: write`); job permissions replace the workflow's, hence `contents: write` repeated.
- `.github/release-install.md` (on every release page) says how to check a file: `gh attestation verify <file> -R david-bartlett/fingerprint-fix-sdcp`.
- PLAN.md's release workflow description and CHANGELOG updated.

## Why
- Part of making the public repo easier to trust: SHA256SUMS shows a download wasn't damaged; an attestation shows which workflow run, commit and tag built it.

## Tested
- YAML parsed with PyYAML; the publish job's permissions and last step checked.
- Not tested: a real run. It only runs on David's next release tag. If the step fails (for example if the action's major version is wrong), the release is still published and the run shows the step in orange; nothing else changes.

## For the next person
- After the first release with this, check a file: `gh attestation verify <file> -R david-bartlett/fingerprint-fix-sdcp` should say it's verified.
