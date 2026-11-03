# Put a bullet before each file on the release page

PR #167 · Claude · 2026-11-03

## What changed
- `.github/release-install.md`, *1. Install*: each file in the *Download these files* column has a `•` in front.

## Why
- David found a row's file names ran together. Markdown tables can't hold a real list, so it's a typed bullet, one per line with `<br>`.

## Tested
- Rendered the page with `bash .github/release-notes.sh 2.13.5`: 13 files, each with a bullet, and the links unchanged.

## For the next person
- The live 2.13.5 page needs the same change by hand: Claude sessions can't edit releases.
- galaxybook-fan has one file per row, so it doesn't need this.
