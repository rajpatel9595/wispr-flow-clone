"""Local speech-to-text.

Two backends behind one protocol (`load` / `transcribe` / `open_stream`):
- `_ParakeetBackend` (default): parakeet-mlx on the Apple GPU via MLX. Streams
  natively, and leaves the CPU free for the rest of the pipeline.
- `_WhisperBackend`: faster-whisper on CPU (CTranslate2 has no Metal support).

Each backend owns its own quirks — parakeet spells numbers out, whisper
hallucinates ". . ." on trailing silence — so `Transcriber` has no
`if backend == ...` branches left.

Parakeet has no initial_prompt equivalent, so vocabulary biasing is a no-op
there; the personal dictionary's forced replacements in `dictionary.apply()`
carry that load instead.

THREADING: MLX streams are thread-local and main.py runs a fresh thread per
dictation, so calling into MLX from those threads raises "There is no
Stream(cpu, N) in current thread". Every model touch — load, warm-up, batch
inference, and each streaming call — is funnelled through one dedicated
single-thread executor: the ASR analogue of this app's "all AppKit on the main
thread" rule. Callers still see plain blocking methods.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Callable, Iterator, Protocol

import numpy as np

from flow.audio import SAMPLE_RATE, gain_for

DEFAULT_PARAKEET = "mlx-community/parakeet-tdt-0.6b-v2"  # English-only; see Config

# parakeet v3's supported languages that are not written in Latin script. For
# any other configured language, a transcript dominated by non-Latin letters
# means the model auto-detected the wrong language, not that the user spoke it.
_NON_LATIN_LANGS = frozenset({"ru", "uk", "bg", "el"})
_LATIN_MAX = 0x024F  # end of Latin Extended-B: keeps café, naïve, Straße

_MIN_TRANSCRIBE_SAMPLES = SAMPLE_RATE // 10  # <0.1 s — an accidental tap

# Streaming feeds audio in blocks of this many seconds. Measured on real speech:
# 0.3s blocks starve the encoder and produce garbage ("Norway" for "no wait",
# trailing gibberish); 2-3s blocks match batch quality. Callers may drain far
# more often than this — the session buffers up to a full block itself.
_STREAM_BLOCK_SECS = 2.0
_BLOCK_SAMPLES = int(_STREAM_BLOCK_SECS * SAMPLE_RATE)
_MIN_FEED_SAMPLES = 512  # parakeet's n_fft; anything shorter crashes add_audio

# Parakeet spells numbers out ("twenty two"); dictation usually wants digits.
_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_TENS_RE = re.compile(
    r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[ -]"
    r"(one|two|three|four|five|six|seven|eight|nine)\b",
    re.IGNORECASE,
)
# A bare number word is only digitised in an unambiguously numeric context.
# Converting every one of them wrecks ordinary prose: "no one knows" would
# become "no 1 knows", "one of the people" -> "1 of the people".
_UNITS = (
    r"a\.?m\.?|p\.?m\.?|o'clock|percent|dollars?|degrees?|"
    r"seconds?|minutes?|hours?|days?|weeks?|months?|years?"
)
_CUES = r"number|step|chapter|version|page|part|level|item|option|question"
_WORDS_RE = "|".join(_NUM_WORDS)
_UNIT_NUM_RE = re.compile(rf"\b({_WORDS_RE})\b(?=\s+(?:{_UNITS})\b)", re.IGNORECASE)
_CUE_NUM_RE = re.compile(rf"\b({_CUES})(\s+)({_WORDS_RE})\b", re.IGNORECASE)


def digits(text: str) -> str:
    """'twenty two years old' -> '22 years old'. Parakeet output only.

    Deliberately conservative: compound tens always convert, but a lone number
    word only converts next to a unit ("four p.m.") or after a counting cue
    ("step three"). Everything else is left alone so prose survives intact.
    """
    def _sub(m):
        return str(_NUM_WORDS[m.group(1).lower()])

    text = _TENS_RE.sub(
        lambda m: str(_NUM_WORDS[m.group(1).lower()] + _NUM_WORDS[m.group(2).lower()]),
        text,
    )
    text = _UNIT_NUM_RE.sub(_sub, text)
    return _CUE_NUM_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{_NUM_WORDS[m.group(3).lower()]}", text
    )


def foreign_script(text: str) -> bool:
    """True if most letters in `text` are outside Latin script.

    The multilingual parakeet v3 has no language pin, so a short, quiet or
    noisy English take sometimes comes back as Russian/Bulgarian/Greek. Pasting
    that into the user's document is worse than pasting nothing.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(ord(c) > _LATIN_MAX for c in letters) * 2 > len(letters)


# --- backends -----------------------------------------------------------------


class Backend(Protocol):
    """A speech-to-text engine. Every method runs on the ASR thread."""

    streams: bool

    def load(self) -> None: ...
    def transcribe(self, audio: np.ndarray, initial_prompt: str | None) -> str: ...
    def open_stream(self): ...
    def clean(self, text: str) -> str: ...


class _ParakeetBackend:
    """parakeet-mlx on the Apple GPU. Streams natively."""

    streams = True

    def __init__(
        self, model_id: str = DEFAULT_PARAKEET, spell_numbers: bool = False, language: str = "en"
    ):
        self.model_id = model_id
        self.spell_numbers = spell_numbers
        self.language = language
        self._model = None

    def load(self) -> None:
        if self._model is None:
            from parakeet_mlx import from_pretrained  # lazy: heavy import

            self._model = from_pretrained(self.model_id)

    def transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        # Feed a mel spectrogram directly: parakeet's own path loader shells out
        # to ffmpeg, which we neither have nor need for in-memory float32.
        # initial_prompt has no equivalent here and is deliberately ignored.
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel

        mel = get_logmel(mx.array(audio), self._model.preprocessor_config)
        results = self._model.generate(mel)
        return (getattr(results[0], "text", "") if results else "").strip()

    def open_stream(self):
        session = self._model.transcribe_stream(context_size=(256, 256), depth=1)
        session.__enter__()  # switches the encoder to local-attention mode
        return session

    def clean(self, text: str) -> str:
        if self.language not in _NON_LATIN_LANGS and foreign_script(text):
            print(
                f"[flow] dropped {text!r}: the model auto-detected another language. "
                f"Set parakeet_model to the English-only {DEFAULT_PARAKEET}."
            )
            return ""
        return text if self.spell_numbers else digits(text)


class _WhisperBackend:
    """faster-whisper on CPU. No streaming support."""

    streams = False

    def __init__(self, model_size: str = "small.en", language: str = "en"):
        self.model_size = model_size
        self.language = language
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        import os

        from faster_whisper import WhisperModel  # lazy: heavy import

        self._model = WhisperModel(
            self.model_size,
            device="auto",
            compute_type="int8",
            cpu_threads=os.cpu_count() or 4,
        )

    def transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,  # dictations are short; big speedup
            initial_prompt=initial_prompt,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def open_stream(self):
        return None

    def clean(self, text: str) -> str:
        # Whisper hallucinates ". . . ." runs on trailing silence — collapse them.
        return re.sub(r"(?:\s*\.){2,}\s*$", ".", text)


# --- streaming sessions -------------------------------------------------------


class InactiveSession:
    """No-op stand-in: streaming disabled, unsupported, or failed to open.

    Lets callers write the same code either way — `active` is the only check.
    """

    active = False

    def feed(self, audio: np.ndarray) -> str:
        return ""

    def finish(self) -> str:
        return ""

    def close(self) -> None:
        pass


class StreamSession:
    """One live streaming transcription, confined to the ASR thread.

    Obtained from `Transcriber.stream()`, which guarantees `close()`. `feed()`
    buffers until a full block has accumulated; `finish()` flushes the tail and
    returns the final transcript. Teardown is separate from `finish()` so a
    caller that ends up discarding the streamed text can skip the flush and
    still release the encoder — see main.py's `_dictate`.
    """

    active = True

    def __init__(self, pool: ThreadPoolExecutor, raw, clean: Callable[[str], str]):
        self._pool = pool
        self._raw = raw
        self._clean = clean
        self._buf = np.zeros(0, dtype=np.float32)
        self._peak = 0.0  # running peak, for monotonic streaming auto-gain
        self._text = ""

    # --- caller-facing (any thread) ---

    def feed(self, audio: np.ndarray) -> str:
        """Buffer audio; transcribe once a full block has accumulated.

        Returns the transcript so far — unchanged until a block goes through,
        so callers may drain as often as they like.
        """
        if self._raw is None:
            return self._text
        if audio.size:
            self._buf = np.concatenate([self._buf, audio])
        if self._buf.size < _BLOCK_SAMPLES:
            return self._text
        return self._pool.submit(self._flush).result()

    def finish(self) -> str:
        """Flush the tail of the dictation and return the final transcript."""
        if self._raw is None:
            return self._clean(self._text)
        return self._pool.submit(self._finish).result()

    def close(self) -> None:
        """Release the encoder. Idempotent; called by the context manager."""
        if self._raw is not None:
            self._pool.submit(self._close).result()

    # --- ASR thread only ---

    def _flush(self) -> str:
        if self._raw is None or self._buf.size < _MIN_FEED_SAMPLES:
            return self._text  # shorter than n_fft: add_audio would crash
        block, self._buf = self._buf, np.zeros(0, dtype=np.float32)
        try:
            import mlx.core as mx

            # Peak only ever grows, so the gain only ever shrinks: monotonic and
            # never oscillating, unlike per-block normalisation.
            self._peak = max(self._peak, float(np.max(np.abs(block))))
            self._raw.add_audio(mx.array(block * gain_for(self._peak)))
            self._text = (getattr(self._raw.result, "text", "") or "").strip()
        except Exception as e:
            print(f"[flow] stream feed failed ({e}); falling back to batch")
            self._close()
        return self._text

    def _finish(self) -> str:
        self._flush()
        return self._clean(self._text)

    def _close(self) -> None:
        raw, self._raw = self._raw, None
        self._buf = np.zeros(0, dtype=np.float32)
        if raw is None:
            return
        # MUST run: __enter__ mutated the encoder's attention mode, and leaving
        # it mutated silently degrades every later batch transcription.
        try:
            raw.__exit__(None, None, None)
        except Exception as e:
            print(f"[flow] stream teardown failed: {e}")


# --- facade -------------------------------------------------------------------


class Transcriber:
    """Thread-confining facade over a `Backend`.

    Keyword-only on purpose: `Transcriber("small.en")` used to be accepted and
    silently gave you the parakeet backend with the model name ignored.
    """

    def __init__(
        self,
        *,
        backend: str = "parakeet",
        model_size: str = "small.en",
        language: str = "en",
        parakeet_model: str = DEFAULT_PARAKEET,
        spell_numbers: bool = False,
    ):
        self.backend = backend
        if backend == "parakeet":
            self._backend: Backend = _ParakeetBackend(parakeet_model, spell_numbers, language)
            self.label = parakeet_model.rsplit("/", 1)[-1]
        else:
            self._backend = _WhisperBackend(model_size, language)
            self.label = model_size
        # One thread owns the model for its whole lifetime (see THREADING above).
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr")
        self._session: StreamSession | None = None

    @classmethod
    def from_config(cls, cfg) -> "Transcriber":
        return cls(
            backend=cfg.backend,
            model_size=cfg.model_size,
            language=cfg.language,
            parakeet_model=cfg.parakeet_model,
            spell_numbers=cfg.spell_numbers,
        )

    # --- loading ---

    def load(self) -> None:
        """Load the model eagerly (call at app start to avoid first-use lag)."""
        self._pool.submit(self._backend.load).result()

    def warm_up(self) -> None:
        """First inference after load is slow (graph init) — burn it at startup."""
        self.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))

    # --- batch inference ---

    def transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        """Blocking; the work itself runs on the dedicated ASR thread."""
        if audio.size < _MIN_TRANSCRIBE_SAMPLES:
            return ""
        return self._pool.submit(self._transcribe, audio, initial_prompt).result()

    def _transcribe(self, audio: np.ndarray, initial_prompt: str | None) -> str:
        self._backend.load()
        # Invariant: a batch generate() must never run while a streaming session
        # is open — the session leaves the encoder in local-attention mode, which
        # silently degrades the result. Runs on the ASR thread, so this is safe.
        if self._session is not None:
            self._session._close()
            self._session = None
        return self._backend.clean(self._backend.transcribe(audio, initial_prompt))

    # --- streaming ---

    @property
    def streaming(self) -> bool:
        return self._session is not None

    @contextmanager
    def stream(self, enabled: bool = True) -> Iterator[StreamSession | InactiveSession]:
        """Yield a streaming session, guaranteeing teardown.

        Yields an `InactiveSession` (rather than raising) when streaming is off,
        unsupported by the backend, or fails to open, so the caller's loop is
        the same either way and the batch path just takes over.
        """
        session = self._open(enabled)
        try:
            yield session
        finally:
            session.close()
            self._session = None

    def _open(self, enabled: bool) -> StreamSession | InactiveSession:
        if not (enabled and self._backend.streams) or self._session is not None:
            return InactiveSession()
        try:
            raw = self._pool.submit(self._open_raw).result()
            self._session = StreamSession(self._pool, raw, self._backend.clean)
            return self._session
        except Exception as e:
            print(f"[flow] streaming unavailable ({e}); using batch transcription")
            return InactiveSession()

    def _open_raw(self):
        self._backend.load()
        return self._backend.open_stream()
