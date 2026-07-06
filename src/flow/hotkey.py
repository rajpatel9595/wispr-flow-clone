"""Global hold-to-talk hotkey. NOTE: pynput cannot see the Fn key on macOS."""
from __future__ import annotations

from typing import Callable


class HoldToTalk:
    def __init__(self, key_name: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        from pynput import keyboard  # lazy: needs Input Monitoring permission

        self._key = getattr(keyboard.Key, key_name, None) or keyboard.KeyCode.from_char(key_name)
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def _press(self, key) -> None:
        if key == self._key and not self._held:
            self._held = True
            self._on_press()

    def _release(self, key) -> None:
        if key == self._key and self._held:
            self._held = False
            self._on_release()

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
