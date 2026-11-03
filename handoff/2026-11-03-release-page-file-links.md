# Link the release page's files to their downloads

PR #166 · Claude · 2026-11-03

## What changed
- `.github/release-install.md`, *1. Install*: each file in the table links to that file in the same release, through `@VERSION@`.
- The columns are now called *Install Command* and *Download these files*.

## Why
- David asked for links. He renamed the command column *Install Command* on the 2.13.5 release page by hand, so the template now uses it. *Download these files* drops "two" because the Arch row has three.

## Tested
- Rendered the page with `bash .github/release-notes.sh 2.13.5`: all 13 links are real files in the 2.13.5 release.

## For the next person
- The 2.13.5 page was edited by hand and differs from the template; `@VERSION@` links appear from the next release.
