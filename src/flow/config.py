"""User config, persisted at ~/.flowclone.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".flowclone.json"


@dataclass
class Config:
    model_size: str = "small.en"     # tiny.en | base.en | small.en | medium | large-v3
    hotkey: str = "alt_r"            # pynput key name, hold-to-talk
    language: str = "en"
    formatter: str = "none"          # none | ollama | claude
    ollama_model: str = "llama3.2"
    sample_rate: int = 16000
    restore_clipboard: bool = True

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
