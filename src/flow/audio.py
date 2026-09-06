"""Microphone capture: start on key press, stop on release.

Exposes `level` (smoothed 0..1 loudness, updated per callback) for the HUD
waveform, and peak-normalizes on stop so whisper-quiet speech transcribes as
well as normal volume (Wispr's "whisper mode").

A `Take` is one recording. `start()` hands out a fresh one and the callback
feeds whichever is newest; an older take keeps the frames it already captured.
That is what lets a dictation still finishing its transcription hold on to its
own audio after the user has pressed again to start the next one — with a
single shared frame buffer, the late `stop()` used to hand take A the (empty)
audio of take B and close B's microphone out from under it.
"""
from __future__ import annotations

import threading

import numpy as np

_MAX_GAIN = 12.0  # cap auto-gain so silence doesn't amplify into noise

# Both ASR backends' feature extractors are fixed at 16 kHz, so the capture rate
# is a property of the models rather than a user setting. Defined here because
# audio is the lower-level module: transcriber.py imports this, not vice versa.
SAMPLE_RATE = 16000


def gain_for(peak: float) -> float:
    """Auto-gain factor for a given peak level (shared by Take and streaming).

    Streaming feeds raw chunks while a finished take normalizes the whole
    recording, so both go through this to keep the live preview and the final
    text consistent.
    """
    if peak <= 1e-4:
        return 1.0
    return min(_MAX_GAIN, 0.9 / peak)


class Take:
    """One recording's frames, appended by the audio callback thread."""

    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._drained = 0  # how many frames the streaming feeder has taken

    def _append(self, mono: np.ndarray) -> None:
        self._frames.append(mono)

    def drain(self) -> np.ndarray:
        """Audio captured since the last drain, for incremental transcription.

        Safe to call from a feeder thread: `_frames` is append-only from the
        audio callback, so snapshotting its length and slicing never tears.
        `audio()` still returns the complete take.
        """
        frames = self._frames[self._drained:]
        self._drained += len(frames)
        return np.concatenate(frames) if frames else np.zeros(0, dtype=np.float32)

    def audio(self) -> np.ndarray:
        """The whole take as mono float32, peak-normalized (auto-gain)."""
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._frames)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        return audio * gain_for(peak)  # boost quiet/whispered speech to full scale


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.level: float = 0.0  # smoothed mic loudness 0..1, read by the HUD
        self._take: Take | None = None
        self._stream = None
        # start() runs on the hotkey listener thread, stop() on each dictation's
        # own thread. Without mutual exclusion, a press landing while the
        # previous take's stop() is inside the (multi-ms) PortAudio close sees
        # _stream still non-None, skips reopening the mic, and then records
        # nothing — the mic closes out from under the brand-new take.
        self._lock = threading.Lock()

    def start(self) -> Take:
        """Begin a new take; audio flows to it from here on. Returns the take."""
        import sounddevice as sd  # lazy: needs mic permission / PortAudio

        with self._lock:
            take = Take()
            self._take = take
            self.level = 0.0
            if self._stream is not None:
                return take  # already capturing — just retarget the frames

            def callback(indata, _frames, _time, _status):
                mono = indata[:, 0]
                current = self._take
                if current is not None:
                    current._append(mono.copy())
                rms = float(np.sqrt(np.mean(mono**2)))
                # scale: normal speech rms ~0.02-0.15; smooth for a fluid waveform
                self.level = 0.65 * self.level + 0.35 * min(1.0, rms * 9.0)

            self._stream = sd.InputStream(
                samplerate=self.sample_rate, channels=1, dtype="float32", callback=callback
            )
            self._stream.start()
            return take

    def stop(self, take: Take | None = None) -> np.ndarray:
        """End `take` and return its audio. Idempotent.

        The microphone is only closed if `take` is still the live one, so a late
        stop() from a previous dictation cannot cut off the current recording.
        """
        with self._lock:
            if take is None:
                take = self._take
            if take is not None and self._take is take:
                self._take = None
            if self._take is None and self._stream is not None:
                self.level = 0.0
                self._stream.stop()
                self._stream.close()
                self._stream = None
        return take.audio() if take is not None else np.zeros(0, dtype=np.float32)
