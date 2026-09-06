# Build plan — target: Wispr Flow parity, 100% free & local

Feature map from research (wisprflow.ai/features, superwhisper.com):
Wispr = auto-edits (fillers/punctuation), per-app tone, personal dictionary +
auto-learn, snippets, self-correction ("no wait, make it 4pm"), whisper-quiet
mode, command mode, 100+ languages. Superwhisper = modes, selected-text context.

## Done
- [x] M0/M1 core: hotkey → mic → faster-whisper → format → paste; menu bar; HUD pill
- [x] LaunchAgent always-on (`com.rajpatel.flowclone`), logs `~/Library/Logs/flowclone.log`
- [x] Native arm64 (uv CPython 3.12) — 6x realtime; CGEvent paste; permission self-check

## P1 — Feel & accuracy (this session)
- [x] Voice-reactive HUD waveform (RMS from audio callback → bars)
- [x] Whisper-quiet mode: peak-normalize audio before transcription (auto-gain)
- [x] `small.en` model (native arm64 makes it fast enough)
- [x] Personal dictionary `~/.flowclone_dict.json`: words → Whisper initial_prompt
      bias + forced replacements
- [x] Snippets: "insert my email" → expansion (dictionary file)
- [x] Spoken commands: new line/paragraph, punctuation words, "scratch that"
- [x] Per-app tone (NSWorkspace frontmost app): casual (Slack/Messages/Discord),
      verbatim-code (terminals/IDEs), default prose
- [x] Sound cues on record start/stop (NSSound)
- [x] History: last 20 dictations in menu bar, click to re-copy
- [x] Startup pre-warm (dummy transcribe so first dictation isn't slow)

## P2 — LLM auto-edits (free via Ollama; wiring done, install manual)
- [x] Formatter prompt v2: self-correction collapse, per-app tone, vocab hints
- [ ] USER: install Ollama.app (ollama.com/download) → then pull llama3.2, set
      `"formatter": "ollama"`, kickstart (sandbox blocks agent-side binary installs)
- [ ] Command mode: hold hotkey with selection → "make this formal" transforms it

## P3 — Product polish
- [x] Stats (`~/.flowclone_stats.jsonl`): words, WPM, time saved, streak, per-app
- [x] Dashboard (menu → Dashboard…): offline dark HTML, Wispr-style cards/chart/history
- [x] /Applications/Flow.app bundle (script launcher, LSUIElement; LaunchAgent runs it)
- [ ] Auto-learn dictionary (watch post-paste edits) — needs accessibility diffing
- [ ] Streaming transcription for long dictations (chunked while speaking)
- [ ] Custom .icns icon for Flow.app
- [x] ~~Multilingual~~ — dropped on purpose: English only (v3 auto-detect pasted Cyrillic/Greek)

## Key risks / facts
- pynput can't see Fn key → alt_r. CGEvent paste needs Accessibility; permissions
  are PER-BINARY (changing python binaries resets them — bit us once).
- rumps/AppKit calls only on main thread; pipeline on worker thread.
- Whisper hallucinates "..." on trailing silence (stripped in transcriber).
