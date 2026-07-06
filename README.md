# Flow Clone — local voice dictation for macOS

A local, privacy-first clone of [Wispr Flow](https://wisprflow.ai): hold a key, speak, release — your words appear as clean, formatted text in whatever app has focus (Slack, VS Code, browser, anywhere).

Everything runs on your machine. Audio never leaves it unless you opt into a cloud formatter.

## How it works

```
hold hotkey ──▶ record mic ──▶ transcribe (faster-whisper) ──▶ format (regex / Ollama / Claude) ──▶ paste into active app
   hotkey.py       audio.py         transcriber.py                  formatter.py                       injector.py
```

- **Hotkey**: hold **right Option (⌥)** to talk, release to insert (configurable).
- **Transcription**: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) locally (`base.en` by default; bump to `small.en`/`medium` for accuracy).
- **Formatting**: three modes — `none` (fast regex cleanup), `ollama` (local LLM, e.g. `llama3.2`), `claude` (Claude Haiku via API).
- **Injection**: clipboard + simulated ⌘V, then restores your old clipboard.
- **UI**: menu bar icon (🎤 idle / 🔴 recording / ⚙️ transcribing) via `rumps`.

## Setup

```bash
cd wispr-flow-clone
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m flow            # or: python src/flow/main.py
```

First model load downloads weights (~150 MB for base.en) to `~/.cache/huggingface`.

### macOS permissions (required)

Grant your terminal app in **System Settings → Privacy & Security**:
- **Microphone** — to record
- **Accessibility** — for the global hotkey listener
- **Input Monitoring** — for pynput key events

### Optional formatters

- **Ollama**: `brew install ollama && ollama pull llama3.2`, set `"formatter": "ollama"` in config.
- **Claude**: `export ANTHROPIC_API_KEY=...`, set `"formatter": "claude"`.

## Config

`~/.flowclone.json` (created with defaults on first run):

```json
{
  "model_size": "base.en",
  "hotkey": "alt_r",
  "language": "en",
  "formatter": "none",
  "ollama_model": "llama3.2",
  "restore_clipboard": true
}
```

## Development

See [CLAUDE.md](CLAUDE.md) for conventions and [PLAN.md](PLAN.md) for the roadmap. Claude Code subagents live in `.claude/agents/`, skills in `.claude/skills/`.

```bash
pytest tests/             # run tests
```

## Status

M1 (core pipeline) scaffolded — see [PLAN.md](PLAN.md).
