"""Menu bar app orchestrating the dictation pipeline.

Threading model:
- pynput listener thread: sets self._state on key press/release.
- worker thread: runs transcribe/format/inject, then resets self._state.
- main thread (rumps): a Timer polls self._state and drives ALL UI (menu bar
  title + the floating HUD). AppKit is not thread-safe, so UI only ever changes
  here — the other threads just flip a string.
"""
from __future__ import annotations

import threading
import time

from flow.audio import Recorder
from flow.config import Config
from flow.formatter import format_text
from flow.hotkey import HoldToTalk
from flow.hud import Hud
from flow.injector import inject
from flow.transcriber import Transcriber

IDLE, RECORDING, BUSY = "🎤", "🔴", "⚙️"


class FlowApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.recorder = Recorder(cfg.sample_rate)
        self.transcriber = Transcriber(cfg.model_size, cfg.language)
        self._state = "idle"        # set by any thread; read by the main-thread tick
        self._last_state = None
        self._app = None            # rumps app, set in run()
        self._hud = Hud()

    # --- pipeline (background threads) ---------------------------------------

    def _on_press(self) -> None:
        self._state = "recording"
        self.recorder.start()

    def _on_release(self) -> None:
        audio = self.recorder.stop()
        self._state = "busy"
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio) -> None:
        try:
            t0 = time.perf_counter()
            raw = self.transcriber.transcribe(audio)
            if raw:
                text = format_text(raw, self.cfg.formatter, self.cfg.ollama_model)
                inject(text, self.cfg.restore_clipboard)
                print(f"[flow] {time.perf_counter() - t0:.2f}s: {text!r}")
        except Exception as e:
            print(f"[flow] pipeline error: {e}")
        finally:
            self._state = "idle"

    # --- UI (main thread only) ----------------------------------------------

    def _tick(self, _timer) -> None:
        """Runs on the rumps main thread — safe to touch AppKit/HUD here."""
        state = self._state
        if state == self._last_state:
            return
        self._last_state = state
        if state == "recording":
            self._app.title = RECORDING
            self._hud.listening()
        elif state == "busy":
            self._app.title = BUSY
            self._hud.busy()
        else:
            self._app.title = IDLE
            self._hud.hide()

    def run(self) -> None:
        import rumps  # lazy: macOS only

        _check_permissions()
        print(f"[flow] loading whisper model '{self.cfg.model_size}'...")
        self.transcriber.load()
        print(f"[flow] ready — hold '{self.cfg.hotkey}' to dictate")

        hotkey = HoldToTalk(self.cfg.hotkey, self._on_press, self._on_release)
        hotkey.start()

        self._app = rumps.App("Flow", title=IDLE, quit_button="Quit Flow")
        self._app.menu = [f"Hotkey: hold {self.cfg.hotkey}", f"Model: {self.cfg.model_size}"]
        rumps.Timer(self._tick, 0.1).start()
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


def main() -> None:
    FlowApp(Config.load()).run()


if __name__ == "__main__":
    main()
