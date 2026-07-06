"""Clean up raw transcription: none (regex) | ollama | claude."""
from __future__ import annotations

import os
import re

FILLERS = re.compile(r"\b(um+|uh+|erm+|you know,?)\b[,\s]*", re.IGNORECASE)

PROMPT = (
    "Clean up this dictated text: fix punctuation and capitalization, remove filler "
    "words and false starts, keep the speaker's words and meaning otherwise unchanged. "
    "Output ONLY the cleaned text with no preamble.\n\nDictation: {text}"
)


def _basic(text: str) -> str:
    text = FILLERS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _ollama(text: str, model: str) -> str:
    import requests

    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": PROMPT.format(text=text), "stream": False},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["response"].strip()


def _claude(text: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(text=text)}],
    )
    return msg.content[0].text.strip()


def format_text(text: str, mode: str = "none", ollama_model: str = "llama3.2") -> str:
    if not text:
        return text
    try:
        if mode == "ollama":
            return _ollama(text, ollama_model)
        if mode == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
            return _claude(text)
    except Exception as e:  # LLM down/slow — degrade to basic, never lose the dictation
        print(f"[formatter] {mode} failed ({e}); falling back to basic cleanup")
    return _basic(text)
