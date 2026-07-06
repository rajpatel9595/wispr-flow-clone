# Build plan

## M0 — Scaffold ✅
Project layout, docs, Claude Code agents/skills, config system.

## M1 — Core pipeline (current)
- [x] Audio capture (sounddevice, 16 kHz mono float32)
- [x] Local transcription (faster-whisper, lazy-loaded)
- [x] Hold-to-talk global hotkey (pynput, right Option)
- [x] Text injection (clipboard + ⌘V via osascript, clipboard restore)
- [x] Menu bar app (rumps) with recording state
- [ ] Verify end-to-end on real mic; tune VAD/silence trimming
- [ ] Handle rapid press/release (<300 ms) — ignore, don't transcribe

## M2 — Smart formatting
- [ ] Filler-word removal + punctuation/caps in `none` mode (regex baseline)
- [ ] Ollama formatter with strict "output only the cleaned text" prompt
- [ ] Claude formatter (claude-haiku-4-5, low latency)
- [ ] Per-app tone: detect frontmost app (osascript), casual for Slack/iMessage, neutral elsewhere
- [ ] Spoken commands: "new line", "period", "scratch that"

## M3 — Personal dictionary & context
- [ ] User dictionary (`~/.flowclone_dict.json`) — proper nouns, jargon → Whisper `initial_prompt` + post-replace
- [ ] Auto-learn corrections (diff injected text vs. what user edits — stretch)

## M4 — Polish
- [x] Floating on-screen HUD pill (non-activating NSPanel) showing Listening/Transcribing state
- [ ] Streaming/partial transcription for long dictations
- [ ] Latency target: <1.5 s release-to-paste for 10 s clips (`small.en` on Apple Silicon)
- [ ] Sound cues on start/stop
- [ ] History window (last 20 dictations, click to re-copy)
- [x] Launch at login (LaunchAgent: `~/Library/LaunchAgents/com.rajpatel.flowclone.plist`, logs at `~/Library/Logs/flowclone.log`)
- [x] Native arm64 venv (uv-managed CPython 3.12 — was x86_64 under Rosetta, ~6x realtime now)
- [ ] Package with py2app

## Key risks
- **Fn key can't be captured** by pynput on macOS → we use right Option instead.
- **Secure input fields** (password boxes) block synthetic ⌘V — detect and no-op.
- **Model cold start** (~2–5 s) → pre-load model at app launch, not first use.
