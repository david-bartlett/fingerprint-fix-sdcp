# Idea: using the fingerprints Windows Hello enrolled

PR #183 · Claude · 2026-11-20

## What changed
- PLAN.md §11 (Ideas not done yet): linking fprintd records to the templates Windows Hello enrolled, from abdallah-alkanani/libfprint-egismoc-sdcp issue #5. It covers how it works, its limits (Linux can't enrol its own, and deleting through fprintd deletes the Windows template), and what the Manager would need to keep Windows' templates safe.

## Why
- David wants to come back to it later. Nothing is built.

## Tested
- Nothing to test: PLAN.md only.

## For the next person
- Check the issue for replies, and whether the helper was added to the driver repo as an example, before starting. Ask David first.
