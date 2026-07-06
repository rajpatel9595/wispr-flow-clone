# Flow Clone — Claude Code guide

Local Wispr Flow clone: hold right-Option → record → faster-whisper → optional LLM cleanup → paste into active app. macOS only.

## Layout
- `src/flow/` — one module per pipeline stage: `hotkey.py` → `audio.py` → `transcriber.py` → `formatter.py` → `injector.py`; `main.py` orchestrates (rumps menu bar app); `config.py` loads `~/.flowclone.json`.
- `tests/` — pytest; pure-logic tests only (formatter, config). Audio/hotkey/injection need real hardware + permissions — test those manually via the `run-app` skill.
- `PLAN.md` — roadmap; update checkboxes when a milestone item lands.

## Conventions
- Python 3.11+, type hints everywhere, no heavy frameworks. Keep each pipeline stage importable and testable in isolation (no module-level side effects).
- Heavy deps (faster_whisper, rumps, sounddevice) are imported lazily inside functions/classes so unit tests run without them installed.
- All user-facing config goes through `Config` — never read env vars or hardcode paths elsewhere (exception: `ANTHROPIC_API_KEY`).
- The transcription worker runs on a background thread; never block the pynput listener or rumps main thread.

## Gotchas
- pynput cannot see the Fn key on macOS — hotkey must be a normal modifier (default `alt_r`).
- Injection = clipboard swap + `osascript` ⌘V. Always restore the user's clipboard (config flag).
- Requires Microphone + Accessibility + Input Monitoring permissions for the *terminal* running it; missing permissions fail silently — check there first when keys/audio "don't work".

## Commands
```bash
source .venv/bin/activate
python -m flow        # run the app
pytest tests/         # unit tests
```
