# Updates: keep a terminal the Manager doesn't know

PR #187 · Claude · 2026-11-22

## What changed
- `lib/terminal.py` `find_terminal()`: Ptyxis is now chosen in place of `xdg-terminal-exec` only when `--print-id` names Ptyxis, or gives **no answer** on GNOME (an older `xdg-terminal-exec`). An answer naming a terminal that isn't in our table (Ghostty, say) is left to `xdg-terminal-exec`.

## Why
- Codex's review: `_known()` returns `None` both for no answer and for an unknown terminal, so the 2.14.2 Ptyxis fix (PR #179) opened Ptyxis on GNOME even when the user had chosen Ghostty.

## Tested
- Fake `xdg-terminal-exec` and `ptyxis` on PATH, with GNOME and KDE:
  - Ghostty → `xdg-terminal-exec`
  - Ptyxis → `ptyxis`
  - no answer on GNOME → `ptyxis`
  - Konsole → `xdg-terminal-exec`
  - no answer on KDE → `xdg-terminal-exec`
- `py_compile`.
- **Not tested:** a real GNOME session with Ghostty.
