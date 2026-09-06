"""The dictation state machine — no microphone, no model, no AppKit.

This is the most concurrency-dense code in the app (three threads, a shared
recorder, a streaming session that must always be torn down), so it is faked
rather than left to manual testing. Every case here is a bug that shipped once.
"""
import sys
import threading
import time
import types
from contextlib import contextmanager

import numpy as np
import pytest

from flow.audio import SAMPLE_RATE, Recorder
from flow.config import Config
from flow.main import Dictation, FlowApp


class FakeTake:
    def drain(self):
        return np.zeros(0, dtype=np.float32)


class FakeRecorder:
    def __init__(self, secs: float = 1.0):
        self.level = 0.0
        self.starts = 0
        self.stops = 0
        self.fail_next_stop = False
        self._audio = np.ones(int(secs * SAMPLE_RATE), dtype=np.float32)

    def start(self):
        self.starts += 1
        return FakeTake()

    def stop(self, take=None):
        self.stops += 1
        if self.fail_next_stop:
            self.fail_next_stop = False
            raise RuntimeError("mic went away")
        return self._audio


class FakeSession:
    def __init__(self, active=True, text="streamed text"):
        self.active = active
        self._text = text
        self.feeds = self.finishes = self.closes = 0

    def feed(self, audio):
        self.feeds += 1
        return "live partial"

    def finish(self):
        self.finishes += 1
        return self._text

    def close(self):
        self.closes += 1


class FakeTranscriber:
    label = "fake-model"

    def __init__(self, session=None, batch="batch text"):
        self.session = session if session is not None else FakeSession()
        self.batch = batch
        self.transcribe_calls = []
        self.stream_enabled = None

    @contextmanager
    def stream(self, enabled=True):
        self.stream_enabled = enabled
        try:
            yield self.session
        finally:
            self.session.close()

    def transcribe(self, audio, initial_prompt=None):
        self.transcribe_calls.append(len(audio))
        return self.batch


@pytest.fixture
def app(monkeypatch):
    """A FlowApp with every side effect (mic, model, clipboard, disk) faked."""
    from flow import main as main_mod

    monkeypatch.setattr(main_mod.dictionary, "load", lambda: {"words": [], "replacements": {}, "snippets": {}})
    monkeypatch.setattr(main_mod.context, "frontmost_app", lambda: "Notes")
    monkeypatch.setattr(main_mod.stats, "record", lambda *a, **k: None)
    pasted = []
    monkeypatch.setattr(main_mod, "inject", lambda text, restore=True: pasted.append(text))

    cfg = Config(formatter="none", stream=True, stream_finalize_secs=60.0)
    a = FlowApp(cfg, recorder=FakeRecorder(), transcriber=FakeTranscriber())
    a.pasted = pasted
    return a


def _dictate(app, timeout=5.0):
    """Press, release, and wait for the dictation thread to finish."""
    app._on_press()
    app._on_release()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app._current is None and app._state == "idle":
            return
        time.sleep(0.01)
    raise AssertionError(f"dictation never finished (state={app._state})")


class TestHappyPath:
    def test_pastes_the_batch_transcription(self, app):
        _dictate(app)
        assert app.pasted and "batch text" in app.pasted[0].lower()

    def test_returns_to_idle_and_releases_the_dictation(self, app):
        _dictate(app)
        assert app._state == "idle" and app._current is None

    def test_recorder_started_and_stopped(self, app):
        _dictate(app)
        assert app.recorder.starts == 1 and app.recorder.stops >= 1

    def test_streaming_enabled_from_config(self, app):
        app.cfg.stream = False
        _dictate(app)
        assert app.transcriber.stream_enabled is False


class TestStreamTeardown:
    def test_session_is_always_closed(self, app):
        _dictate(app)
        assert app.transcriber.session.closes == 1

    def test_closed_even_when_the_pipeline_raises(self, app):
        app.recorder.fail_next_stop = True
        _dictate(app)
        assert app.transcriber.session.closes == 1

    def test_short_dictation_does_not_pay_for_the_final_flush(self, app):
        """1 s of audio is re-transcribed in batch, so finish() is wasted work."""
        _dictate(app)
        assert app.transcriber.session.finishes == 0
        assert app.transcriber.session.closes == 1

    def test_long_dictation_finalises_and_uses_the_stream(self, app):
        app.recorder = FakeRecorder(secs=90.0)
        _dictate(app)
        assert app.transcriber.session.finishes == 1
        assert not app.transcriber.transcribe_calls  # no redundant batch pass
        assert "streamed text" in app.pasted[0].lower()


class TestFailureRecovery:
    def test_mic_failure_still_returns_to_idle(self, app):
        """A throw before stop() used to leave the pill up and _busy set."""
        app.recorder.fail_next_stop = True
        _dictate(app)
        assert app._state == "idle" and app._current is None

    def test_transcriber_failure_still_returns_to_idle(self, app):
        def boom(*a, **k):
            raise RuntimeError("model exploded")

        app.transcriber.transcribe = boom
        _dictate(app)
        assert app._state == "idle" and app._current is None


class TestPerDictationState:
    def test_target_app_comes_from_the_dictation_not_the_app(self, app):
        """A second press must not retarget the take still being formatted."""
        first = Dictation(target_app="Slack")
        app._current = Dictation(target_app="Terminal")  # user pressed again
        app._process(first, np.ones(SAMPLE_RATE, dtype=np.float32), "")
        assert app.pasted, "expected a paste"
        # 'code' tone (Terminal) leaves text verbatim; 'casual' (Slack) does not
        # add a trailing period. Either way it must not be Terminal's tone.
        assert app.pasted[0] == app.pasted[0].rstrip(".")

    def test_stale_dictation_does_not_stop_the_current_recording(self, app):
        """Cleanup from an old take must not cut off the one now recording."""
        stale = Dictation(target_app="Notes", take=FakeTake())
        stale.stop.set()
        live = Dictation(target_app="Notes", take=FakeTake())
        app._current = live
        app._state = "recording"

        app._dictate(stale)  # runs to completion on this thread

        assert app._current is live, "stale take cleared the live one"
        assert app._state == "recording", "stale take forced the UI back to idle"

    def test_each_dictation_gets_its_own_stop_event(self, app):
        app._on_press()
        first = app._current
        app._on_press()
        second = app._current
        assert first is not second and first.stop is not second.stop
        first.stop.set()
        second.stop.set()

    def test_release_before_any_press_is_harmless(self, app):
        app._current = None
        app._on_release()  # must not raise


class TestRecorderMicHandoff:
    """The real Recorder's start/stop handoff, with PortAudio faked.

    start() runs on the hotkey listener thread while a previous take's stop()
    runs on that dictation's own thread; the pair must be atomic or a press
    landing mid-close inherits a microphone that is about to disappear.
    """

    def test_press_during_previous_takes_mic_close_still_records(self, monkeypatch):
        closing = threading.Event()  # stop() has reached the PortAudio close
        release = threading.Event()  # test lets the close finish
        streams = []

        class SlowCloseStream:
            def __init__(self, *args, **kwargs):
                self.callback = kwargs.get("callback")
                self.dead = False
                streams.append(self)

            def start(self):
                pass

            def stop(self):
                closing.set()
                assert release.wait(timeout=5), "test never released the close"

            def close(self):
                self.dead = True

        sd = types.ModuleType("sounddevice")
        sd.InputStream = SlowCloseStream
        monkeypatch.setitem(sys.modules, "sounddevice", sd)

        rec = Recorder()
        first = rec.start()
        stopper = threading.Thread(target=rec.stop, args=(first,))
        stopper.start()
        assert closing.wait(timeout=5)

        # The next press arrives while the mic teardown is still in flight.
        second_take = []
        starter = threading.Thread(target=lambda: second_take.append(rec.start()))
        starter.start()
        time.sleep(0.05)  # unguarded, start() would slip through here
        release.set()
        stopper.join(timeout=5)
        starter.join(timeout=5)
        assert not stopper.is_alive() and not starter.is_alive()

        live = rec._stream
        assert live is not None and not live.dead, "new take was left with no microphone"
        # ...and the frames it captures reach the new take, not the void.
        live.callback(np.ones((10, 1), dtype=np.float32), 10, None, None)
        assert second_take[0].drain().size == 10
        rec.stop(second_take[0])


class TestConcurrency:
    def test_two_dictations_are_serialised_on_the_pipeline_lock(self, app):
        """Streaming and batch generate() must never interleave on the model."""
        overlaps = []
        inside = threading.Lock()
        busy = []

        real = app.transcriber.transcribe

        def watched(audio, initial_prompt=None):
            with inside:
                busy.append(1)
                overlaps.append(len(busy))
            time.sleep(0.05)
            with inside:
                busy.pop()
            return real(audio, initial_prompt)

        app.transcriber.transcribe = watched
        threads = []
        for _ in range(3):
            d = Dictation(target_app="Notes", take=FakeTake())
            d.stop.set()
            threads.append(threading.Thread(target=app._dictate, args=(d,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert max(overlaps) == 1, f"model used concurrently: {overlaps}"

    def test_rapid_presses_never_wedge_the_pipeline(self, app):
        """A press landing inside another dictation's cleanup check-then-act
        used to null out the NEW dictation's _current; its stop Event was then
        never set and its thread held _pipeline forever. Hammer press/release
        with maximal thread interleaving and require full drainage."""
        old = sys.getswitchinterval()
        sys.setswitchinterval(1e-5)
        try:
            for _ in range(300):
                app._on_press()
                app._on_release()
        finally:
            sys.setswitchinterval(old)
        deadline = time.time() + 5
        while time.time() < deadline:
            if app._current is None and app._state == "idle":
                break
            time.sleep(0.01)
        assert app._pipeline.acquire(timeout=5), (
            "a dictation never finished — its stop Event was orphaned"
        )
        app._pipeline.release()
        assert app._state == "idle" and app._current is None
