# Link the release page's files to their downloads

PR #166 · Claude · 2026-11-03

## What changed
- `.github/release-install.md`, *1. Install*: each file in the table links to that file in the same release, through `@VERSION@`.
- The template now matches the 2.13.5 page as David edited it: columns *Install command* and *Download these files*, the sentence above the table and the Arch row's wording as they were before #165.

## Why
- David asked for links, and for his release pages to look like the 2.13.5 page.

## Tested
- Rendered the page with `bash .github/release-notes.sh 2.13.5`: all 13 links are real files in the 2.13.5 release.

## For the next person
- The live 2.13.5 page doesn't have the links until David updates it by hand: Claude sessions can't edit releases. This template gives them to every later release.
