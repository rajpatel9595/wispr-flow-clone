# Flow Clone — local voice dictation for macOS

A free, local, privacy-first clone of [Wispr Flow](https://wisprflow.ai): hold a key, speak, release — clean formatted text appears in whatever app has focus. Runs permanently in your menu bar. Audio never leaves your machine unless you opt into a cloud formatter.

![Flow dashboard](docs/dashboard.png)

## Features (Wispr parity, all free)

- **Hold-to-talk anywhere** — hold **right Option (⌥)**, speak, release. Works in every app.
- **Local transcription** — [parakeet-mlx](https://github.com/senstella/parakeet-mlx) `tdt-0.6b-v2` (English-only; set `parakeet_model` to `…-v3` for multilingual) running on the Apple GPU via MLX: ~33× realtime (14 s of speech transcribes in 0.42 s). [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `small.en` on CPU remains available via `"backend": "whisper"`.
- **Streaming transcription** — text is recognised *while you speak* and shown live above the pill, so release-to-paste stays fast no matter how long you talk.
- **Voice-reactive HUD** — Wispr-style black pill above the Dock; waveform bars follow your actual voice.
- **Per-app tone** — casual in Slack/Messages/Discord, verbatim (no invented punctuation) in terminals/IDEs, clean prose everywhere else.
- **Personal dictionary** — `~/.flowclone_dict.json`: your names/jargon bias recognition; forced replacements fix stubborn mishears.
- **Snippets** — say "insert my email" → your saved text expands.
- **Spoken commands** — "new line", "new paragraph", "period", "comma", "question mark"…, and **"scratch that"** discards what you said before it.
- **Whisper-quiet mode** — auto-gain normalizes quiet speech; dictate without disturbing the room.
- **Auto-edits** — filler-word removal + punctuation locally; optional LLM cleanup (self-correction collapse, tone rewriting) via free local [Ollama](https://ollama.com) or Claude API.
- **History** — menu bar → History: last 20 dictations, click to re-copy.
- **Sound cues** + always-on via LaunchAgent (starts at login, auto-restarts).

## Architecture

```
hold ⌥ ─▶ hotkey.py ─▶ audio.py ─▶ transcriber.py ─▶ dictionary.py ─▶ formatter.py ─▶ injector.py ─▶ paste
          pynput       mic+RMS      parakeet-mlx       vocab/snippets    commands/tone     CGEvent ⌘V
          listener     auto-gain    Apple GPU (MLX)    replacements      regex or LLM      clipboard swap
                                         ▲                                    ▲
                          streams while you speak                context.py (frontmost app → tone)
```

Threads: pynput listener (key events), one dictation thread per take (started on **press** — streams audio to the model while you speak, then finalises and pastes), and the rumps main thread (menu bar + HUD + sounds — all AppKit stays here, fed by a 20 fps timer). All model calls are funnelled onto a single ASR thread, because MLX streams are thread-local.

## Setup

```bash
cd wispr-flow-clone
uv venv .venv --python 3.12        # MUST be native arm64 python (not Rosetta!)
uv pip install -r requirements.txt --python .venv/bin/python
PYTHONPATH=src .venv/bin/python -m flow
```

### Permissions (System Settings → Privacy & Security)
Grant the **actual python binary** (it self-registers in the panes on first run; permissions are per-binary — swapping interpreters resets them):
- **Accessibility** — paste keystrokes • **Input Monitoring** — hotkey • **Microphone** — recording

The app prints `permissions OK` or exactly what's missing to its log.

### Always-on (LaunchAgent)
Installed at `~/Library/LaunchAgents/com.rajpatel.flowclone.plist`. Logs: `~/Library/Logs/flowclone.log`.
```bash
launchctl kickstart -k gui/501/com.rajpatel.flowclone   # restart (after code/config changes)
launchctl bootout gui/501/com.rajpatel.flowclone        # stop permanently
```

### Optional LLM formatter (better auto-edits, still free)
Install [Ollama](https://ollama.com/download) → `ollama pull llama3.2` → set `"formatter": "ollama"` in `~/.flowclone.json` → kickstart. Falls back to regex cleanup automatically if Ollama is down.

## Config

`~/.flowclone.json`: `backend` (`parakeet|whisper`), `parakeet_model`, `stream` (live transcription), `stream_finalize_secs` (under this, re-transcribe in one pass for accuracy), `spell_numbers`, `model_size` (whisper only), `hotkey` (pynput name; Fn is impossible on macOS), `formatter` (`none|ollama|claude`), `restore_clipboard`.
`~/.flowclone_dict.json`: `words` (recognition bias), `replacements`, `snippets`.

## Development

[CLAUDE.md](CLAUDE.md) conventions • [PLAN.md](PLAN.md) roadmap • `.claude/agents/` subagents • `.claude/skills/` skills • `PYTHONPATH=src .venv/bin/python -m pytest tests/ -q`
