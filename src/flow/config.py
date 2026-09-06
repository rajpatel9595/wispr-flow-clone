"""User config, persisted at ~/.flowclone.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".flowclone.json"

# Config.load() writes every default into the file on first run, so the old
# multilingual default is pinned in existing configs even though the user never
# chose it. Loading swaps it for the current default (a deliberately chosen
# non-Latin language keeps it — that is the one case v3 is the right model).
_RETIRED_PARAKEET = "mlx-community/parakeet-tdt-0.6b-v3"
_NON_LATIN_LANGS = frozenset({"ru", "uk", "bg", "el"})


@dataclass
class Config:
    backend: str = "parakeet"        # parakeet (MLX/GPU) | whisper (faster-whisper/CPU)
    # v2 is English-only. v3 is multilingual and auto-detects the language of
    # every utterance with no way to pin it, so a short/quiet English take
    # sometimes came back in Cyrillic or Greek. Same architecture and speed.
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
            cfg = cls(**data)
            if (
                cfg.parakeet_model == _RETIRED_PARAKEET
                and cfg.language not in _NON_LATIN_LANGS
            ):
                cfg.parakeet_model = cls.parakeet_model
                cfg.save()
                print(f"[flow] config: parakeet_model upgraded to {cfg.parakeet_model}")
            return cfg
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2))
