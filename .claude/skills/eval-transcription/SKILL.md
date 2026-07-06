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
2. For each candidate config (tiny.en / base.en / small.en × beam 1/5), write a throwaway script in the scratchpad that loads the model once, transcribes every fixture, and records wall time + output.
3. Score with word error rate (simple word-diff is fine; don't add a WER dependency).
4. Report a table: model × beam → WER, avg latency, and a recommendation. Update `Config.model_size` default only if the user approves.
