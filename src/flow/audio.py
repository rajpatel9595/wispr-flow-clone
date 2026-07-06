"""Microphone capture: start on key press, stop on release."""
from __future__ import annotations

import numpy as np


class Recorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd  # lazy: needs mic permission / PortAudio

        if self._stream is not None:
            return
        self._frames = []

        def callback(indata, _frames, _time, _status):
            self._frames.append(indata[:, 0].copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32", callback=callback
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop capture and return mono float32 audio at self.sample_rate."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._frames)
