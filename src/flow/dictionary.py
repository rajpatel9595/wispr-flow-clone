"""Personal dictionary: vocabulary bias, forced replacements, snippets.

~/.flowclone_dict.json:
  words        — names/jargon Whisper should recognize (fed to initial_prompt)
  replacements — {"wrong": "right"} forced post-transcription fixes
  snippets     — {"my email": "you@x.com"}; say "insert my email" to expand
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DICT_PATH = Path.home() / ".flowclone_dict.json"

_DEFAULT = {
    "words": ["Raj", "Wispr Flow", "Claude", "uv", "Ollama"],
    "replacements": {},
    "snippets": {"my email": "rajspatel2004@gmail.com"},
}


def load() -> dict:
    if not DICT_PATH.exists():
        DICT_PATH.write_text(json.dumps(_DEFAULT, indent=2))
        return dict(_DEFAULT)
    try:
        data = json.loads(DICT_PATH.read_text())
    except json.JSONDecodeError:
        return dict(_DEFAULT)
    return {k: data.get(k, _DEFAULT[k]) for k in _DEFAULT}


def initial_prompt(d: dict) -> str | None:
    """Bias Whisper toward the user's vocabulary."""
    words = d.get("words") or []
    return ("Glossary: " + ", ".join(words) + ".") if words else None


def apply(text: str, d: dict) -> str:
    """Forced replacements + snippet expansion ("insert <name>")."""
    for wrong, right in (d.get("replacements") or {}).items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    for name, expansion in (d.get("snippets") or {}).items():
        text = re.sub(
            rf"\binsert {re.escape(name)}\b[.,]?", expansion, text, flags=re.IGNORECASE
        )
    return text
