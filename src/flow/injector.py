"""Insert text into the frontmost app: clipboard swap + synthetic Cmd+V.

Uses Quartz CGEvent directly (not osascript/System Events) — one permission
(Accessibility) instead of two, no subprocess, and we can detect the missing
permission instead of failing silently.
"""
from __future__ import annotations

import time

_KEY_V = 9  # ANSI keyboard code for 'v'


def can_post_events() -> bool:
    """True if we have Accessibility permission to send keystrokes."""
    from Quartz import CGPreflightPostEventAccess

    return bool(CGPreflightPostEventAccess())


def request_post_access() -> None:
    """Prompt + register this binary in System Settings > Accessibility."""
    from Quartz import CGRequestPostEventAccess

    CGRequestPostEventAccess()


def _press_cmd_v() -> None:
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )

    for is_down in (True, False):
        ev = CGEventCreateKeyboardEvent(None, _KEY_V, is_down)
        CGEventSetFlags(ev, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, ev)


def inject(text: str, restore_clipboard: bool = True) -> None:
    if not text:
        return
    import pyperclip

    old = pyperclip.paste() if restore_clipboard else None
    pyperclip.copy(text)

    if not can_post_events():
        # Leave the text on the clipboard so the user can Cmd+V manually —
        # do NOT restore the old clipboard, that would destroy the dictation.
        request_post_access()
        print(
            "[flow] NO ACCESSIBILITY PERMISSION — text copied to clipboard, paste "
            "manually. Fix: System Settings > Privacy & Security > Accessibility "
            "> enable python3.12, then restart flow."
        )
        return

    time.sleep(0.05)  # let the clipboard settle before the paste keystroke
    _press_cmd_v()
    if restore_clipboard and old is not None:
        time.sleep(0.3)  # paste must read the buffer before we restore it
        pyperclip.copy(old)
