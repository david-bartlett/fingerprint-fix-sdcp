# Split the README into a summary and guides

PR #137 · Claude · 2026-11-02

## What changed
- `README.md` is now the summary: install, updating, uninstall, a Documentation table, supported hardware, a short safety list, reporting problems, licence and credits.
- Seven new guides in `docs/`: `manager.md`, `fingerprint-login.md`, `multi-distro.md`, `install-options.md`, `monitoring.md`, `how-it-works.md` and `troubleshooting.md`.
- Most collapsible sections became headings. The Manager's table of every button stays collapsed.
- Outside the README: `.github/release-install.md` had a dead `#only-one-part` link, now pointing to `install-options.md`. `install.sh` now sends people to `docs/fingerprint-login.md` for the manual PAM steps. `tools/test-latest-libfprint.sh` pointed to maintainer notes the README no longer has, so it now names `packaging/README.md`.
- `PLAN.md` (rule 5, the file map, the fish rule) and `AGENTS.md` now mention `docs/`.

## Why
- David wanted the same layout as `snapper_tray`. The README was about 8,500 words over 584 lines.

## Tested
- A script moved the text, then every line of the old README was compared with the new files. The only differences are the ones listed in the PR.
- A script checked every relative link, every full link to `docs/`, their anchors and every picture path.
- Checked GitHub's rendered HTML for the README and guides on the branch: headings, tables and picture tags come through, and each picture file exists. Not seen in a browser.
- `bash -n` on `install.sh` and `tools/test-latest-libfprint.sh`, and `py_compile` on `lib/*.py`.
- Not tested: the full links to `docs/` on GitHub, which only work once this is merged. `install.sh`'s changed message only shows when turning on PAM fails.

## For the next person
- The packages install only `README.md`, so its links to the guides are full GitHub addresses. Links between guides are relative.
- The README is still about 1,250 words of moved text, plus the table and safety list. Install, Updating and Supported Hardware could shrink, but that's rewording, so it's left for David to decide.
- `manager.md` is right at the 2,000-word limit.
- Other repos weren't checked for links to this README's old anchors.
