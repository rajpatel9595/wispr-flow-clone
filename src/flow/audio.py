"""Microphone capture: start on key press, stop on release.

Exposes `level` (smoothed 0..1 loudness, updated per callback) for the HUD
waveform, and peak-normalizes on stop so whisper-quiet speech transcribes as
well as normal volume (Wispr's "whisper mode").
"""
from __future__ import annotations

import numpy as np

_MAX_GAIN = 12.0  # cap auto-gain so silence doesn't amplify into noise


class Recorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.level: float = 0.0  # smoothed mic loudness 0..1, read by the HUD
        self._frames: list[np.ndarray] = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd  # lazy: needs mic permission / PortAudio

        if self._stream is not None:
            return
        self._frames = []
        self.level = 0.0

        def callback(indata, _frames, _time, _status):
            mono = indata[:, 0]
            self._frames.append(mono.copy())
            rms = float(np.sqrt(np.mean(mono**2)))
            # scale: normal speech rms ~0.02-0.15; smooth for a fluid waveform
            self.level = 0.65 * self.level + 0.35 * min(1.0, rms * 9.0)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32", callback=callback
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop capture; return mono float32 audio, peak-normalized (auto-gain)."""
        self.level = 0.0
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._frames)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1e-4:  # boost quiet/whispered speech toward full scale
            audio = audio * min(_MAX_GAIN, 0.9 / peak)
        return audio
