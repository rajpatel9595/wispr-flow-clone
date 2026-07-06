"""Menu bar app orchestrating the dictation pipeline.

Threading model:
- pynput listener thread: sets self._state on key press/release.
- worker thread: runs transcribe/format/inject, then resets self._state.
- main thread (rumps): a Timer polls self._state and drives ALL UI (menu bar
  title, HUD, sounds). AppKit is not thread-safe, so UI only ever changes
  here — the other threads just flip a string.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

LOCK_PATH = Path.home() / ".flowclone.lock"
SHOW_TRIGGER = Path.home() / ".flowclone_show_dashboard"

from flow import context, dashboard, dictionary, stats
from flow.audio import Recorder
from flow.config import Config
from flow.formatter import format_text
from flow.hotkey import HoldToTalk
from flow.hud import Hud
from flow.injector import inject
from flow.transcriber import Transcriber

IDLE, RECORDING, BUSY = "🎤", "🔴", "⚙️"
MAX_HISTORY = 20


class FlowApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.recorder = Recorder(cfg.sample_rate)
        self.transcriber = Transcriber(cfg.model_size, cfg.language)
        self.vocab = dictionary.load()
        self.history: deque[str] = deque(maxlen=MAX_HISTORY)
        self._state = "idle"        # set by any thread; read by the main-thread tick
        self._last_state = None
        self._target_app = ""       # frontmost app captured at key press
        self._app = None            # rumps app, set in run()
        self._hud = Hud()
        self._history_menu = None

    # --- pipeline (background threads) ---------------------------------------

    def _on_press(self) -> None:
        self._target_app = context.frontmost_app()
        self._state = "recording"
        self.recorder.start()

    def _on_release(self) -> None:
        audio = self.recorder.stop()
        self._state = "busy"
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio) -> None:
        try:
            t0 = time.perf_counter()
            raw = self.transcriber.transcribe(
                audio, initial_prompt=dictionary.initial_prompt(self.vocab)
            )
            if raw:
                raw = dictionary.apply(raw, self.vocab)
                tone = context.tone_for(self._target_app)
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
                    stats.record(text, len(audio) / self.cfg.sample_rate, latency, self._target_app)
                    print(f"[flow] {latency:.2f}s [{self._target_app or '?'}:{tone}]: {text!r}")
        except Exception as e:
            print(f"[flow] pipeline error: {e}")
        finally:
            self._state = "idle"

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
        if state == "recording":
            self._hud.set_level(self.recorder.level)
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
        print(f"[flow] loading whisper model '{self.cfg.model_size}'...")
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
            f"Model: {self.cfg.model_size}",
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
