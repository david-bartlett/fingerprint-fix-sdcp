# Privacy, how it's built, SECURITY.md and CONTRIBUTING.md

PR #<number> · Claude · 2026-11-17

## What changed
- README: two new sections after "How it stays safe": **Your Fingerprints and Privacy** and **How It's Built and Tested**, with links to the two new files.
- New `SECURITY.md` (private reporting through GitHub's **Report a vulnerability**; newest release only; driver and fprintd issues go to their own projects) and `CONTRIBUTING.md` (issue forms, PR rules from AGENTS.md / PLAN.md, AI-assisted contributions with disclosure).
- PLAN.md's file map lists both files. CHANGELOG has an Unreleased entry.

## Why
- David asked how to raise confidence in the public repos. Being open about AI use and the testing, a clear privacy statement and a private way to report security problems were the missing pieces (a tested-on table, uninstall docs and SHA256SUMS were already there).

## Tested
- Markdown only: links checked against the repo's files and headings. The privacy facts come from docs/how-it-works.md, docs/manager.md, docs/multi-distro.md, docs/updating.md and lib/update_check.py.
- Not tested: GitHub's private vulnerability reporting must be turned on in the repository's settings (Settings → Security → Private vulnerability reporting) for the link in SECURITY.md to work.

## For the next person
- The README's AI wording ("much of the code is written with Claude") is David's to adjust.
- Release attestations are a separate PR.
