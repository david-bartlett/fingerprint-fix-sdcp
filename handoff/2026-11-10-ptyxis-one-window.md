# Ptyxis: one window for Update

PR #179 · Claude · 2026-11-10

## What changed
- `lib/terminal.py`: Ptyxis runs with `--standalone` instead of `--new-window`. When `xdg-terminal-exec` would open Ptyxis (its `--print-id`, or on GNOME/Ubuntu when `--print-id` gives nothing), Ptyxis is started directly so the flag isn't lost.
- PLAN.md (`terminal.py` row), CHANGELOG.

## Why
- David saw the update open two Ptyxis windows from the dev tools' buttons, fixed there in samsung-galaxybook-dev-tools with `ptyxis --standalone --`, ahead of `xdg-terminal-exec` on GNOME. Without it, Ptyxis passes the command to its shared instance, which can restore saved windows as well. `terminal.py` is used by both the notification's **Update now** and the Manager's **Update**, so both had it.
- Unlike the dev tools, this still follows `xdg-terminal-exec` when it names another terminal, even on GNOME.

## Tested
- `python3 lib/terminal.py` with fake `ptyxis`, `konsole` and `xdg-terminal-exec` on `PATH`: GNOME with Ptyxis as the default, GNOME with an `xdg-terminal-exec` that has no `--print-id`, GNOME without `xdg-terminal-exec` and Cinnamon with Ptyxis as the default all give `ptyxis --standalone --`. GNOME with Konsole as the default, and Ptyxis not on `PATH` (Flatpak), still use `xdg-terminal-exec`.
- Not here: a real Ptyxis window.

## For the next person
- `--standalone` keeps the `ptyxis` process running until its window closes. That suits `update_now()`, which execs the terminal as the notification service's main process.
