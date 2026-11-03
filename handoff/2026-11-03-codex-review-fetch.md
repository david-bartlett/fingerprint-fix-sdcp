# AGENTS.md: Codex reviews fetch the latest main first

PR #156 · Claude · 2026-11-03

## What changed
- `AGENTS.md`: a new rule after *Every change is a pull request*. Before a review, `git fetch origin main` and review `FETCH_HEAD`, say which commit was reviewed, and stop if GitHub can't be reached.

## Why
- Codex cloud caches its container for up to 12 hours. A galaxybook-fan review ran on `c03a2fd` when `main` was several releases ahead. The review prompt already asks for the fetch; this is the backup if a prompt leaves it out.
- David's Codex environments now allow `github.com`, so the fetch can work.

## For the next person
- It's for reviews only. PR work still starts from `main` as the other rules say.
