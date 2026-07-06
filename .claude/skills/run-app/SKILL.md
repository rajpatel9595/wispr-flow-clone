---
name: run-app
description: Run the Flow Clone menu bar app locally and walk through the manual smoke test. Use when asked to run, launch, or manually verify the dictation app.
---

# Run & smoke-test Flow Clone

1. Ensure venv + deps:
   ```bash
   cd wispr-flow-clone
   [ -d .venv ] || python3 -m venv .venv
   source .venv/bin/activate && pip install -q -r requirements.txt
   ```
2. Launch in foreground so logs are visible: `python -m flow`
   - First run downloads the Whisper model (~150 MB) — expect a delay, tell the user.
3. If the hotkey or mic does nothing, do NOT debug code first — instruct the user to grant the terminal Microphone, Accessibility, and Input Monitoring in System Settings → Privacy & Security, then relaunch.
4. Manual smoke test (user performs, you narrate):
   - Menu bar shows 🎤. Focus a text field (Notes.app).
   - Hold right Option, say "hello world testing one two three", release.
   - Expect: icon 🔴 while held, ⚙️ briefly, text appears in Notes, clipboard restored.
5. Report: model load time, release-to-paste latency (from logs), and any stderr.
