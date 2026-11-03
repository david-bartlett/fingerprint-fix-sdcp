# Show the command first on the release page

PR #165 · Claude · 2026-11-03

## What changed
- `.github/release-install.md`, *1. Install*: the columns are now Distro, Command, Files to download first. The sentence above the table says to download the files first.
- The Arch row said "In a new, empty folder: `makepkg -si`". It now says `makepkg -si`, in a new folder with only these files in it.

## Why
- This is the table David meant in PR #164, which changed the table in `docs/install-options.md` instead. That table is left as merged, so the two match.
- "New, empty folder" could be read as running `makepkg` in a folder with no `PKGBUILD`.

## Tested
- `bash .github/release-notes.sh 2.13.5` writes the page with the table in the new order and the version filled in.
- How it looks on a real release page can't be seen until the next release.

## For the next person
- The release page for 2.13.5 keeps the old table; the change shows from the next release.
