"""Dictation stats: append-only JSONL + aggregates for the dashboard."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

STATS_PATH = Path.home() / ".flowclone_stats.jsonl"
TYPING_WPM = 40.0  # average typing speed, for "time saved"


def record(text: str, audio_secs: float, latency: float, app: str) -> None:
    entry = {
        "ts": time.time(),
        "words": len(text.split()),
        "chars": len(text),
        "secs": round(audio_secs, 2),
        "latency": round(latency, 2),
        "app": app or "?",
        "text": text[:200],
    }
    with STATS_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def load() -> list[dict]:
    if not STATS_PATH.exists():
        return []
    out = []
    for line in STATS_PATH.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def aggregate(entries: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    total_words = sum(e["words"] for e in entries)
    total_secs = sum(e["secs"] for e in entries)
    speak_wpm = (total_words / (total_secs / 60.0)) if total_secs > 0 else 0.0
    # time typing would have taken, minus time spent speaking
    saved_min = max(0.0, total_words / TYPING_WPM - total_secs / 60.0)

    days = {datetime.fromtimestamp(e["ts"]).date() for e in entries}
    streak = 0
    d = today
    while d in days:
        streak += 1
        d -= timedelta(days=1)

    daily: dict[str, int] = {}
    for i in range(13, -1, -1):
        daily[(today - timedelta(days=i)).isoformat()] = 0
    for e in entries:
        k = datetime.fromtimestamp(e["ts"]).date().isoformat()
        if k in daily:
            daily[k] += e["words"]

    apps: dict[str, int] = {}
    for e in entries:
        apps[e["app"]] = apps.get(e["app"], 0) + 1
    top_apps = sorted(apps.items(), key=lambda kv: -kv[1])[:6]

    latencies = [e["latency"] for e in entries if e.get("latency")]
    return {
        "dictations": len(entries),
        "total_words": total_words,
        "speak_wpm": round(speak_wpm),
        "saved_min": round(saved_min, 1),
        "streak": streak,
        "daily": daily,
        "top_apps": top_apps,
        "avg_latency": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
    }
