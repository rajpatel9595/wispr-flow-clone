"""Streaming helpers — pure logic only, must run without mlx/AppKit."""
import numpy as np
import pytest

from flow.audio import Take, gain_for
from flow.hud import tail


class TestGain:
    def test_silence_is_not_amplified(self):
        assert gain_for(0.0) == 1.0
        assert gain_for(1e-9) == 1.0

    def test_quiet_speech_boosted_toward_full_scale(self):
        assert gain_for(0.09) == 10.0

    def test_capped_so_noise_is_not_blown_up(self):
        assert gain_for(0.001) == 12.0

    def test_loud_audio_attenuated_below_clipping(self):
        assert gain_for(1.0) == 0.9

    def test_monotonic_non_increasing_in_peak(self):
        """Streaming relies on this: a growing peak must never raise the gain."""
        peaks = [0.01, 0.05, 0.1, 0.3, 0.6, 1.0]
        gains = [gain_for(p) for p in peaks]
        assert gains == sorted(gains, reverse=True)


class TestDrain:
    def test_returns_only_new_audio(self):
        t = Take()
        t._append(np.ones(4, dtype=np.float32))
        assert len(t.drain()) == 4
        assert len(t.drain()) == 0          # nothing new
        t._append(np.ones(6, dtype=np.float32))
        assert len(t.drain()) == 6

    def test_empty_when_nothing_recorded(self):
        assert Take().drain().size == 0

    def test_drain_does_not_consume_the_final_recording(self):
        """audio() must still see the whole take after streaming drained it."""
        t = Take()
        t._append(np.ones(3, dtype=np.float32))
        t._append(np.ones(5, dtype=np.float32))
        t.drain()
        assert t.audio().size == 8

    def test_audio_is_peak_normalised(self):
        t = Take()
        t._append(np.full(10, 0.09, dtype=np.float32))
        assert t.audio().max() == pytest.approx(0.9, abs=1e-6)

    def test_audio_empty_when_nothing_recorded(self):
        assert Take().audio().size == 0


class TestTail:
    def test_short_text_kept_whole(self):
        assert tail("hello world", 80) == "hello world"

    def test_long_text_truncated_at_the_head(self):
        out = tail("abcdefghij", 4)
        assert out == "…ghij"          # keeps the live tail, not the start

    def test_whitespace_collapsed(self):
        assert tail("a\n\n  b   c") == "a b c"

    def test_empty(self):
        assert tail("") == ""
