"""Clean up raw transcription: spoken commands + tone-aware edits.

Pipeline: scratch-that → spoken commands → (LLM if configured) or regex cleanup.
Tone: 'default' full prose, 'casual' chat style (no trailing period),
'code' verbatim (no invented punctuation/caps — safe for terminals/IDEs).
"""
from __future__ import annotations

import os
import re

FILLERS = re.compile(r"\b(um+|uh+|erm+|you know,?)\b[,\s]*", re.IGNORECASE)

# spoken word -> literal, applied at word boundaries, optional trailing punct
_COMMANDS = [
    (r"new paragraph", "\n\n"),
    (r"new line", "\n"),
    (r"period", "."),
    (r"full stop", "."),
    (r"comma", ","),
    (r"question mark", "?"),
    (r"exclamation (?:mark|point)", "!"),
    (r"colon", ":"),
    (r"semicolon", ";"),
]

PROMPT = (
    "You are a dictation transcript cleaner. Apply ONLY these edits:\n"
    "1. fix punctuation and capitalization\n"
    "2. delete filler words (um, uh, you know) and false starts\n"
    "3. if the speaker self-corrects (\"at 2pm... no wait, 4pm\"), keep only the correction\n"
    "NEVER rephrase, summarize, add words, or swap word choices. Every remaining "
    "word must appear in the input. Tone context (affects punctuation style only): "
    "{tone_hint} Known vocabulary: {vocab}. "
    "Output ONLY the cleaned text, no preamble.\n\nDictation: {text}"
)

_TONE_HINTS = {
    "casual": "casual chat message (it's for a messaging app — relaxed, no stiff formality).",
    "code": "verbatim technical text for a code editor — do NOT add punctuation or rephrase.",
    "default": "clear, well-formed prose.",
}


def apply_commands(text: str) -> str:
    """'scratch that' discard + spoken punctuation/layout commands."""
    # keep only what follows the last "scratch that"
    parts = re.split(r"\bscratch that\b[.,]?", text, flags=re.IGNORECASE)
    text = parts[-1].strip()
    for spoken, literal in _COMMANDS:
        # layout commands (\n) swallow surrounding spaces; punctuation attaches
        # to the preceding word but keeps the space after it
        trail = r"\s*" if literal.startswith("\n") else ""
        text = re.sub(rf"\s*\b{spoken}\b[.,]?{trail}", literal, text, flags=re.IGNORECASE)
    # tidy space before punctuation introduced by commands
    return re.sub(r"\s+([.,!?;:])", r"\1", text).strip()


def _basic(text: str, tone: str = "default") -> str:
    text = FILLERS.sub("", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if tone == "code":
        return text  # verbatim: never invent punctuation in a terminal/IDE
    if text and text[0].islower() and tone != "casual":
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".!?\n" and tone == "default":
        text += "."
    return text


def _ollama(text: str, model: str, tone: str, vocab: str) -> str:
    import requests

    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": PROMPT.format(
                tone_hint=_TONE_HINTS[tone], vocab=vocab or "none", text=text
            ),
            "stream": False,
            "keep_alive": "24h",  # avoid 4-5s cold reload after Ollama's idle unload
            "options": {"temperature": 0},  # deterministic, least creative
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["response"].strip()


def _claude(text: str, tone: str, vocab: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": PROMPT.format(
                tone_hint=_TONE_HINTS[tone], vocab=vocab or "none", text=text
            ),
        }],
    )
    return msg.content[0].text.strip()


def format_text(
    text: str,
    mode: str = "none",
    ollama_model: str = "llama3.2",
    tone: str = "default",
    vocab: str = "",
) -> str:
    if not text:
        return text
    text = apply_commands(text)
    if not text:
        return ""  # entire dictation was scratched
    try:
        if mode == "ollama":
            return _ollama(text, ollama_model, tone, vocab)
        if mode == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
            return _claude(text, tone, vocab)
    except Exception as e:  # LLM down/slow — degrade to basic, never lose the dictation
        print(f"[formatter] {mode} failed ({e}); falling back to basic cleanup")
    return _basic(text, tone)
