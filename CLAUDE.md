# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Local Wispr Flow clone: hold right-Option → record → parakeet-mlx (streaming, Apple GPU) → dictionary → tone-aware format → CGEvent paste. macOS only, runs as LaunchAgent.

## Layout
- `src/flow/` — one module per pipeline stage: `hotkey.py` → `audio.py` (mic + live RMS level + auto-gain) → `transcriber.py` (parakeet-mlx on the Apple GPU by default; `backend="whisper"` falls back to faster-whisper/CPU) → `dictionary.py` (vocab bias/replacements/snippets, `~/.flowclone_dict.json`) → `formatter.py` (spoken commands, scratch-that, tone-aware cleanup, optional Ollama/Claude) → `injector.py` (CGEvent ⌘V). `context.py` = frontmost-app → tone. `hud.py` = voice-reactive pill. `stats.py` = append-only JSONL (`~/.flowclone_stats.jsonl`) + aggregates. `dashboard.py` renders those stats as HTML and shows them in a native WKWebView window (main thread only). `main.py` (`FlowApp`) orchestrates all of it as a rumps menu bar app.
- `tests/` — pytest, no hardware/model/AppKit. `test_config.py`, `test_dictionary.py`, `test_formatter.py`, `test_stats.py`, `test_streaming.py` are pure logic; `test_dictation.py` drives the real `FlowApp` state machine with a fake recorder/transcriber injected via `FlowApp(cfg, recorder=…, transcriber=…)` — add a case there for any threading/ordering bug rather than manual-testing it. Only hotkey, injector, dashboard, context and the model backends themselves stay manual (`run-app` skill).
- `.claude/agents/` and `.claude/skills/` — subagents and skills already scoped to this codebase; both are auto-listed with descriptions each session, so they aren't enumerated here. When work falls squarely in one's area, prefer it over ad hoc edits: each agent file carries hard-won detail not repeated below.

## Conventions
- Python 3.12 native arm64 (uv-managed). NEVER let the venv go x86 — Rosetta cost us 5x speed once.
- Heavy deps (faster_whisper, rumps, sounddevice, AppKit, Quartz, WebKit) imported lazily inside functions; unit tests must run without them.
- Threading model (see `main.py` module docstring): the pynput listener starts one dictation thread on **press**; `_on_release` only sets that dictation's Event. The dictation thread feeds the stream, finalises, then runs transcribe/format/inject under `self._pipeline`. The rumps main thread's 20fps `_tick` polls `_state` and is the ONLY place AppKit/UI (menu bar title, HUD pill, live transcript, sounds, dashboard) may be touched.
- **Per-dictation state lives on `Dictation`, never on `FlowApp`.** Its target app, live partial, stop Event and audio `Take` all hang off that object. Two dictations really can be in flight (press again while the last paste computes); every bug where take B pasted with take A's tone, cleared A's HUD, or stopped A's microphone came from sharing one of those slots. `FlowApp._current` is only "what the UI should render" — a thread touches shared state in `finally` **only** while `self._current is d`.
- Config via `Config` (`~/.flowclone.json`); dictionary via `dictionary.load()`. No env vars except `ANTHROPIC_API_KEY`. There is deliberately no `sample_rate` knob: both backends' feature extractors are fixed at 16 kHz (`audio.SAMPLE_RATE`).
- README.md's feature list names concrete models/defaults — update it in the same commit as any default change (it silently advertised v3 after the v2 switch).

## Gotchas (hard-won)
- macOS permissions are PER-BINARY: swapping the python interpreter silently revokes Accessibility/Input Monitoring. `_check_permissions()` in main.py preflights and self-registers; log says exactly what's missing.
- pynput cannot see the Fn key. Paste = CGEventPost ⌘V (keycode 9), NOT osascript.
- On paste-permission failure, text stays on the clipboard (never restore over it).
- Whisper hallucinates ". . ." on trailing silence — stripped in transcriber.
- Default parakeet model is **v2 (English-only) on purpose**: v3 is multilingual with unforceable auto language detection and transcribed short English phrases as Russian ("hello hello" → "Алло алло"). `cfg.language` does nothing on the parakeet backend.
- An exception escaping a pynput callback **stops the listener** — hotkey dead, app looks alive. `HoldToTalk._press/_release` therefore swallow and log; keep it that way.
- Parakeet backend: (a) **must** be fed a mel via `get_logmel`, never a file path — its path loader shells out to ffmpeg, which isn't installed; (b) has no `initial_prompt`, so dictionary vocab-biasing is a no-op and `dictionary.apply()` replacements carry that load alone; (c) emits spelled-out numbers, converted by `transcriber.digits()` unless `spell_numbers` is set.
- Streaming is a **context manager**: `with transcriber.stream(enabled=…) as session:` always tears the session down, and yields an `InactiveSession` (never raises, never None) when streaming is off/unsupported/failed — so the caller's loop is identical either way and the batch path just takes over. `session.finish()` (flush the tail, get the text) is separate from `close()` on purpose: a short dictation gets re-transcribed in batch anyway, so it skips `finish()` and pays only for teardown. Opening a session leaves the encoder in local-attention mode, so a batch `generate()` must never run while one is open — that is what `FlowApp._pipeline` guarantees.
- Feed the stream in **~2s blocks** (`_STREAM_BLOCK_SECS`). Measured: 0.3s blocks starve the encoder and yield garbage ("Norway" for "no wait", trailing gibberish); 2–3s matches batch quality. `StreamSession` buffers internally, so callers may drain as often as they like.
- Never call `add_audio` with fewer than 512 samples (parakeet's `n_fft`) — it raises "Negative dimensions not allowed". The buffer guards this.
- `Recorder.start()` returns a `Take`; `stop(take)` returns *that* take's audio and only closes the mic if it is still the live one. Never go back to one shared frame buffer — a late `stop()` from the previous dictation then handed it the new take's (empty) audio and killed the new recording.
- Backends are two classes behind one protocol (`load`/`transcribe`/`open_stream`/`clean`), each owning its own quirks, so `Transcriber` has no `if backend == …` left. `Transcriber.__init__` is keyword-only: `Transcriber("small.en")` used to be accepted and silently gave you parakeet with the model name ignored. Build it with `Transcriber.from_config(cfg)`.
- Benchmark parakeet only after a real `warm_up()` — the first `generate()` includes graph compilation and will overstate latency ~3x.
- Single-instance guard (`_single_instance()` in main.py): double-clicking `/Applications/Flow.app` while the LaunchAgent is already running just touches `~/.flowclone_show_dashboard` (polled by `_tick`) to pop the dashboard window, then exits — it does not spawn a second pipeline. A stale PID in `~/.flowclone.lock` is detected and overwritten.
- The running instance is the LaunchAgent, NOT a dev process: after ANY code change run `launchctl kickstart -k gui/501/com.rajpatel.flowclone` and check `~/Library/Logs/flowclone.log`. Never start a second instance alongside it (double-paste).

## Commands
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q          # tests
PYTHONPATH=src .venv/bin/python -m pytest tests/test_formatter.py -q  # single test file
launchctl kickstart -k gui/501/com.rajpatel.flowclone        # restart app
tail -20 ~/Library/Logs/flowclone.log                        # check state
```
