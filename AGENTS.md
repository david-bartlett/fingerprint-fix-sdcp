# Instructions for coding agents

Read **[PLAN.md](PLAN.md)** before starting: it explains how the project works, every file, and how changes are made. The essentials:

- **Every change is a pull request** against `main`, from its own branch. Never push to `main`, never merge, never force-push.
- **Never release:** don't change `VERSION`, don't create `v*` tags or GitHub releases. David releases himself, after testing the PR on his laptop.
- **One topic per PR.** Check a PR isn't merged before pushing more to its branch.
- **User-visible change → a line under `## Unreleased` in `CHANGELOG.md`** (a short bold headline line, then plain detail lines; see PLAN.md §8.2), and update `README.md` where it describes what you changed.
- **Don't touch `DRIVER`** unless asked.
- In the PR description: what changed, how you tested it, what you couldn't test, and numbered steps for David to test it on the laptop (PLAN.md §9).
- **Add a handoff note** to `handoff/` in every PR (see [handoff/README.md](handoff/README.md)), and **read the notes newer than your last session** before starting. When a PR changes how something works, update `PLAN.md` in the same PR.
- Before committing: `python3 -m py_compile lib/*.py`, `bash -n` on changed scripts, and check `git status` for stray files. Keep test scripts outside the repository.
- The helper runs as root and the sensor holds real fingerprints: read PLAN.md §10 (safety) before changing anything that writes files, touches the sensor or PAM.
- British English; call the app "Galaxy Book Fingerprint Manager" the first time, then "the Manager".
