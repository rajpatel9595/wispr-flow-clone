"""Frontmost-app detection and tone selection (Wispr's per-app awareness)."""
from __future__ import annotations

CASUAL_APPS = {"slack", "discord", "messages", "whatsapp", "telegram", "signal"}
CODE_APPS = {"terminal", "iterm2", "code", "visual studio code", "cursor", "xcode",
             "warp", "ghostty", "alacritty", "kitty", "intellij idea", "pycharm"}


def frontmost_app() -> str:
    """Name of the app that will receive the paste. Safe to call off-main."""
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return str(app.localizedName()) if app else ""
    except Exception:
        return ""


def tone_for(app_name: str) -> str:
    """'casual' (chat apps), 'code' (verbatim, no auto-punctuation), 'default'."""
    name = app_name.lower()
    if name in CASUAL_APPS:
        return "casual"
    if name in CODE_APPS:
        return "code"
    return "default"
