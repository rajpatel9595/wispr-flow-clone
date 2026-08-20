---
name: eval-transcription
description: Benchmark transcription accuracy/latency across Whisper model sizes using audio fixtures. Use when tuning model_size, beam_size, or VAD settings.
---

# Transcription eval

1. Fixtures live in `tests/fixtures/*.wav` (16 kHz mono) with expected text in a matching `.txt`. If none exist, generate speech with macOS TTS:
   ```bash
   say -o tests/fixtures/sample1.aiff "the quick brown fox jumps over the lazy dog" \
     && ffmpeg -y -i tests/fixtures/sample1.aiff -ar 16000 -ac 1 tests/fixtures/sample1.wav
   ```
   (fallback if no ffmpeg: `afconvert -f WAVE -d LEI16@16000 -c 1 in.aiff out.wav`)
2. The shipped default is `backend="parakeet"` (parakeet-mlx on the Apple GPU); `model_size`/`beam_size` apply only to `backend="whisper"`. Benchmark whichever backend you are actually tuning — for parakeet the knobs are `parakeet_model`, `_STREAM_BLOCK_SECS`, and streaming `context_size`/`depth`. Write a throwaway script in the scratchpad that loads the model once, transcribes every fixture, and records wall time + output.
   **Always `warm_up()` before timing** — parakeet's first `generate()` includes graph compilation and overstates latency ~3x.
3. Score with word error rate (simple word-diff is fine; don't add a WER dependency).
4. Report a table: config → WER, avg latency, and a recommendation. Update the relevant `Config` default (`parakeet_model`, or `model_size` for whisper) only if the user approves.
5. TTS fixtures from `say` are near-useless for ranking models — they are clean, disfluency-free and unaccented, so everything scores near-perfectly and vocabulary biasing never gets exercised. Rank on real recorded speech; use TTS only for smoke tests and latency.
