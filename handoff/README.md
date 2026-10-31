# Handoff notes

One short note per pull request, so whoever works on the project next (Claude, Codex or David) can catch up from the repository alone.

## Rules

- **Every PR adds one note here**, in the same PR: `handoff/YYYY-MM-DD-short-topic.md` (the date you open the PR, a few words of the branch's topic).
- **Before starting work, read the notes newer than your last session** (`git log --oneline -- handoff/` shows what's been added), then [PLAN.md](../PLAN.md) for anything they mention.
- Notes are history: don't edit or delete other notes. If something in an older note is no longer true, say so in yours.
- `PLAN.md` describes how things work **now**: when your PR changes how something works, update `PLAN.md` in the same PR too. The note says what changed and why; PLAN.md is the reference.
- Keep it short: a few lines per heading. Leave out a heading that has nothing to say.

## Template

```markdown
# <What the PR does, in a few words>

PR #<number> · <who: Codex / Claude / David> · <YYYY-MM-DD>

## What changed
- …

## Why
- …

## Tested
- What was tested, and how (unit test with stand-ins, Xvfb mock-up, …).
- What couldn't be tested here (needs the sensor, a package build, a real desktop…).

## For the next person
- Anything left half-done, known problems, decisions made on the way ("didn't touch X because…"), ideas.
```
