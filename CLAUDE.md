# Flow Clone — Claude Code guide

Local Wispr Flow clone: hold right-Option → record → faster-whisper → dictionary → tone-aware format → CGEvent paste. macOS only, runs as LaunchAgent.

## Layout
- `src/flow/` — one module per stage: `hotkey.py` → `audio.py` (mic + live RMS level + auto-gain) → `transcriber.py` (small.en, warm_up) → `dictionary.py` (vocab bias/replacements/snippets, `~/.flowclone_dict.json`) → `formatter.py` (spoken commands, scratch-that, tone-aware cleanup, optional Ollama/Claude) → `injector.py` (CGEvent ⌘V). `context.py` = frontmost-app → tone. `hud.py` = voice-reactive pill. `main.py` orchestrates.
- `tests/` — pytest, pure-logic only (formatter/dictionary/context/config). Hardware paths are manual-tested via the `run-app` skill.

## Conventions
- Python 3.12 native arm64 (uv-managed). NEVER let the venv go x86 — Rosetta cost us 5x speed once.
- Heavy deps (faster_whisper, rumps, sounddevice, AppKit, Quartz) imported lazily inside functions; unit tests must run without them.
- All AppKit/UI on the rumps main thread only (the 20fps `_tick` timer). Listener/worker threads communicate via plain attributes (`_state`, `recorder.level`).
- Config via `Config` (`~/.flowclone.json`); dictionary via `dictionary.load()`. No env vars except `ANTHROPIC_API_KEY`.

## Gotchas (hard-won)
- macOS permissions are PER-BINARY: swapping the python interpreter silently revokes Accessibility/Input Monitoring. `_check_permissions()` in main.py preflights and self-registers; log says exactly what's missing.
- pynput cannot see the Fn key. Paste = CGEventPost ⌘V (keycode 9), NOT osascript.
- On paste-permission failure, text stays on the clipboard (never restore over it).
- Whisper hallucinates ". . ." on trailing silence — stripped in transcriber.
- The running instance is the LaunchAgent, NOT a dev process: after ANY code change run `launchctl kickstart -k gui/501/com.rajpatel.flowclone` and check `~/Library/Logs/flowclone.log`. Never start a second instance alongside it (double-paste).

## Commands
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q          # tests
launchctl kickstart -k gui/501/com.rajpatel.flowclone        # restart app
tail -20 ~/Library/Logs/flowclone.log                        # check state
```
