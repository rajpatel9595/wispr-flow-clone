"""Local speech-to-text via faster-whisper."""
from __future__ import annotations

import re

import numpy as np


class Transcriber:
    def __init__(self, model_size: str = "base.en", language: str = "en"):
        self.model_size = model_size
        self.language = language
        self._model = None

    def load(self) -> None:
        """Load the model eagerly (call at app start to avoid first-use lag)."""
        if self._model is None:
            import os

            from faster_whisper import WhisperModel  # lazy: heavy import

            self._model = WhisperModel(
                self.model_size,
                device="auto",
                compute_type="int8",
                cpu_threads=os.cpu_count() or 4,
            )

    def warm_up(self) -> None:
        """First inference after load is slow (graph init) — burn it at startup."""
        self.transcribe(np.zeros(16000, dtype=np.float32))

    def transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        if audio.size < 1600:  # <0.1 s — accidental tap
            return ""
        self.load()
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,  # dictations are short; big speedup
            initial_prompt=initial_prompt,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        # Whisper hallucinates ". . . ." runs on trailing silence — collapse them.
        return re.sub(r"(?:\s*\.){2,}\s*$", ".", text)
