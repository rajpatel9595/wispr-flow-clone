"""Menu bar app orchestrating the dictation pipeline.

Threading model:
- pynput listener thread: _on_press creates a Dictation and starts its thread;
  _on_release only sets that dictation's stop Event. It never touches the model.
- dictation thread (one per dictation, started on PRESS): feeds the streaming
  session while the key is held, finalises it, then runs transcribe/format/
  inject. Issuing the session's open, every feed and the teardown from a single
  thread is what keeps them ordered — see transcriber.py, where feeding after
  teardown is invalid.
- main thread (rumps): a Timer polls self._state and drives ALL UI (menu bar
  title, HUD pill, live transcript, sounds). AppKit is not thread-safe, so UI
  only ever changes here — the other threads just flip plain attributes.

Everything that belongs to one dictation (its target app, its live partial, its
stop Event) lives on a `Dictation`, never on FlowApp. Two dictations can be in
flight at once — the user can press again while the previous paste is still
computing — and sharing those slots is what used to make the second one paste
with the first one's tone, or stop the first one's recording out from under it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

LOCK_PATH = Path.home() / ".flowclone.lock"
SHOW_TRIGGER = Path.home() / ".flowclone_show_dashboard"

from flow import context, dashboard, dictionary, stats
from flow.audio import SAMPLE_RATE, Recorder
from flow.config import Config
from flow.formatter import format_text
from flow.hotkey import HoldToTalk
from flow.hud import Hud
from flow.injector import inject
from flow.transcriber import Transcriber

IDLE, RECORDING, BUSY = "🎤", "🔴", "⚙️"
MAX_HISTORY = 20
_POLL_SECS = 0.3  # how often the dictation thread drains the mic while recording


@dataclass
class Dictation:
    """One press-to-release take. Owned end-to-end by its own thread."""

    target_app: str = ""              # frontmost app captured at key press
    partial: str = ""                 # live transcript, read by the main thread
    stop: threading.Event = field(default_factory=threading.Event)
    take: object | None = None        # audio.Take, this dictation's own recording


class FlowApp:
    def __init__(self, cfg: Config, recorder=None, transcriber=None):
        # recorder/transcriber are injectable so the dictation state machine can
        # be tested with fakes — it is the most concurrency-dense code here and
        # needs no microphone or model to exercise.
        self.cfg = cfg
        self.recorder = recorder or Recorder()
        self.transcriber = transcriber or Transcriber.from_config(cfg)
        self.vocab = dictionary.load()
        self.history: deque[str] = deque(maxlen=MAX_HISTORY)
        self._state = "idle"        # set by any thread; read by the main-thread tick
        self._last_state = None
        self._app = None            # rumps app, set in run()
        self._hud = Hud()
        self._history_menu = None
        self._current: Dictation | None = None  # the take the UI should render
        self._pipeline = threading.Lock()    # serialises model use across dictations

    # --- pipeline (background threads) ---------------------------------------

    def _on_press(self) -> None:
        d = Dictation(target_app=context.frontmost_app())
        d.take = self.recorder.start()  # this dictation's own frames
        self._current = d
        self._state = "recording"
        # One thread owns the whole dictation: it feeds the stream while the key
        # is down, finalises the session, then runs the pipeline. Release only
        # sets that dictation's Event — so every feed and the teardown are issued
        # from this thread in order, with no race against the session closing.
        threading.Thread(target=self._dictate, args=(d,), daemon=True).start()

    def _on_release(self) -> None:
        d = self._current
        if d is not None:
            d.stop.set()  # _dictate() owns everything from here

    def _dictate(self, d: Dictation) -> None:
        # Held for the whole dictation: a streaming session and a batch
        # generate() must never interleave on the model (opening a session
        # switches the encoder's attention mode). A press that arrives while a
        # previous take is still in flight queues here rather than being dropped.
        with self._pipeline:
            try:
                with self.transcriber.stream(enabled=self.cfg.stream) as session:
                    while not d.stop.wait(_POLL_SECS):
                        d.partial = session.feed(d.take.drain())
                    audio = self.recorder.stop(d.take)
                    if self._current is d:
                        self._state = "busy"  # not ours to set if a new take began
                    secs = len(audio) / SAMPLE_RATE
                    streamed = ""
                    # Only pay for the final flush when the text will be used;
                    # otherwise _process re-transcribes and discards it anyway.
                    # close() still happens, via the context manager.
                    if session.active and secs > self.cfg.stream_finalize_secs:
                        session.feed(d.take.drain())
                        streamed = session.finish()
                self._process(d, audio, streamed)
            except Exception as e:  # never wedge: the tick must get back to idle
                print(f"[flow] dictation error: {e}")
            finally:
                d.partial = ""
                # stop() only closes the mic if this take is still the live one,
                # so this is safe even once the user has pressed again. The UI
                # state, though, is only ours to reset while we own it.
                self.recorder.stop(d.take)
                if self._current is d:
                    self._state = "idle"
                    self._current = None

    def _process(self, d: Dictation, audio, streamed: str = "") -> None:
        try:
            t0 = time.perf_counter()
            secs = len(audio) / SAMPLE_RATE
            # Short dictations: re-transcribe in one pass (more accurate, and
            # cheap at ~0.03x realtime). Long ones: trust the stream, because
            # that is exactly where waiting hurts.
            if streamed and secs > self.cfg.stream_finalize_secs:
                raw = streamed
            else:
                raw = self.transcriber.transcribe(
                    audio, initial_prompt=dictionary.initial_prompt(self.vocab)
                ) or streamed
            if raw:
                raw = dictionary.apply(raw, self.vocab)
                # d.target_app, not a shared attribute: a second press must not
                # retarget the take that is still being formatted here.
                tone = context.tone_for(d.target_app)
                text = format_text(
                    raw,
                    self.cfg.formatter,
                    self.cfg.ollama_model,
                    tone=tone,
                    vocab=", ".join(self.vocab.get("words") or []),
                )
                if text:
                    inject(text, self.cfg.restore_clipboard)
                    self.history.appendleft(text)
                    latency = time.perf_counter() - t0
                    stats.record(text, secs, latency, d.target_app)
                    print(f"[flow] {latency:.2f}s [{d.target_app or '?'}:{tone}]: {text!r}")
        except Exception as e:
            print(f"[flow] pipeline error: {e}")

    # --- UI (main thread only) ----------------------------------------------

    def _tick(self, _timer) -> None:
        """Runs on the rumps main thread — safe to touch AppKit/HUD here."""
        try:
            self._tick_inner()
        except Exception as e:  # a UI hiccup must never kill the app
            print(f"[flow] ui error: {e}")

    def _tick_inner(self) -> None:
        # double-clicking Flow.app touches SHOW_TRIGGER (see _single_instance)
        self._trigger_count = getattr(self, "_trigger_count", 0) + 1
        if self._trigger_count % 10 == 0 and SHOW_TRIGGER.exists():
            SHOW_TRIGGER.unlink(missing_ok=True)
            dashboard.show_window()
        state = self._state
        d = self._current
        if state == "recording" and d is not None:
            self._hud.set_level(self.recorder.level)
            self._hud.set_text(d.partial)
        if state == self._last_state:
            return
        self._last_state = state
        if state == "recording":
            self._app.title = RECORDING
            self._hud.listening()
            self._play("Tink")
        elif state == "busy":
            self._app.title = BUSY
            self._hud.busy()
            self._play("Pop")
        else:
            self._app.title = IDLE
            self._hud.hide()
            self._refresh_history()

    @staticmethod
    def _play(name: str) -> None:
        try:
            from AppKit import NSSound

            s = NSSound.soundNamed_(name)
            s.setVolume_(0.3)
            s.play()
        except Exception:
            pass

    def _refresh_history(self) -> None:
        import rumps

        if self._history_menu is None or not self.history:
            return
        if self._history_menu._menu is not None:  # rumps creates the submenu lazily
            self._history_menu.clear()
        for text in self.history:
            label = text.replace("\n", " ")[:60] or "(empty)"
            item = rumps.MenuItem(label, callback=self._copy_history)
            item._full_text = text
            self._history_menu.add(item)

    @staticmethod
    def _copy_history(item) -> None:
        import pyperclip

        pyperclip.copy(item._full_text)

    def run(self) -> None:
        import rumps  # lazy: macOS only

        _check_permissions()
        print(f"[flow] loading {self.cfg.backend} model '{self.transcriber.label}'...")
        self.transcriber.load()
        self.transcriber.warm_up()
        print(f"[flow] ready — hold '{self.cfg.hotkey}' to dictate")

        hotkey = HoldToTalk(self.cfg.hotkey, self._on_press, self._on_release)
        hotkey.start()

        self._app = rumps.App("Flow", title=IDLE, quit_button="Quit Flow")
        self._history_menu = rumps.MenuItem("History")
        self._app.menu = [
            rumps.MenuItem("Dashboard…", callback=lambda _: dashboard.show_window()),
            self._history_menu,
            f"Hotkey: hold {self.cfg.hotkey}",
            f"Model: {self.transcriber.label}",
        ]
        rumps.Timer(self._tick, 0.05).start()  # 20fps: waveform + state changes
        self._app.run()


def _check_permissions() -> None:
    """Report missing macOS permissions and register us in System Settings.

    The Request* calls make this python binary show up in the Accessibility /
    Input Monitoring panes so the user just has to flip the toggle.
    """
    from Quartz import (
        CGPreflightListenEventAccess,
        CGPreflightPostEventAccess,
        CGRequestListenEventAccess,
        CGRequestPostEventAccess,
    )

    listen, post = CGPreflightListenEventAccess(), CGPreflightPostEventAccess()
    if not listen:
        CGRequestListenEventAccess()
        print("[flow] MISSING Input Monitoring permission — hotkey will not work")
    if not post:
        CGRequestPostEventAccess()
        print("[flow] MISSING Accessibility permission — paste will not work")
    if listen and post:
        print("[flow] permissions OK (input monitoring + accessibility)")
    else:
        print(
            "[flow] fix in System Settings > Privacy & Security > "
            "Accessibility / Input Monitoring: enable 'python3.12', then run: "
            "launchctl kickstart -k gui/501/com.rajpatel.flowclone"
        )


def _single_instance() -> None:
    """If Flow already runs, signal it to open the dashboard window and exit.

    This makes double-clicking Flow.app act like opening the app's window
    instead of spawning a second dictation pipeline (which would double-paste).
    """
    if LOCK_PATH.exists():
        try:
            pid = int(LOCK_PATH.read_text().strip())
            os.kill(pid, 0)  # raises if dead
            comm = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True
            ).stdout
            if "python" in comm.lower():
                SHOW_TRIGGER.touch()
                sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # stale lock — take over
    LOCK_PATH.write_text(str(os.getpid()))


def main() -> None:
    _single_instance()
    FlowApp(Config.load()).run()


if __name__ == "__main__":
    main()
