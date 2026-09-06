"""User config, persisted at ~/.flowclone.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".flowclone.json"


@dataclass
class Config:
    backend: str = "parakeet"        # parakeet (MLX/GPU) | whisper (faster-whisper/CPU)
    # v2 is English-only ON PURPOSE: v3 (multilingual) auto-detects language with
    # no way to force one, and transcribed short English phrases as Russian
    # ("hello hello" -> "Алло алло"). Set v3 here only for non-English dictation.
    parakeet_model: str = "mlx-community/parakeet-tdt-0.6b-v2"
    spell_numbers: bool = False      # parakeet says "twenty two"; False -> "22"
    stream: bool = True              # transcribe while speaking (parakeet only)
    stream_finalize_secs: float = 60.0  # <= this, re-transcribe fully for accuracy
    model_size: str = "small.en"     # whisper backend only: tiny.en|base.en|small.en|medium
    hotkey: str = "alt_r"            # pynput key name, hold-to-talk
    language: str = "en"
    formatter: str = "none"          # none | ollama | claude
    ollama_model: str = "llama3.2"
    restore_clipboard: bool = True
    # No sample_rate knob: both backends' feature extractors are fixed at
    # 16 kHz, so it could only ever be set wrong. See audio.SAMPLE_RATE.

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            known = {f.name for f in fields(cls)}
            data = {k: v for k, v in json.loads(CONFIG_PATH.read_text()).items() if k in known}
            return cls(**data)
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2))
