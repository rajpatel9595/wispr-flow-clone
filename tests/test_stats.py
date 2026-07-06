from datetime import date, datetime, timedelta

from flow.stats import TYPING_WPM, aggregate


def _e(ts: float, words: int, secs: float, app: str = "Notes") -> dict:
    return {"ts": ts, "words": words, "chars": words * 5, "secs": secs,
            "latency": 1.0, "app": app, "text": "x " * words}


def test_empty():
    agg = aggregate([])
    assert agg["dictations"] == 0 and agg["streak"] == 0


def test_wpm_and_saved():
    today = date(2026, 7, 6)
    ts = datetime(2026, 7, 6, 12).timestamp()
    agg = aggregate([_e(ts, words=80, secs=60.0)], today=today)
    assert agg["speak_wpm"] == 80
    assert agg["saved_min"] == round(80 / TYPING_WPM - 1.0, 1)  # 1.0
    assert agg["streak"] == 1


def test_streak_consecutive_days():
    today = date(2026, 7, 6)
    entries = [
        _e(datetime(2026, 7, 6, 9).timestamp(), 10, 5.0),
        _e(datetime(2026, 7, 5, 9).timestamp(), 10, 5.0),
        _e(datetime(2026, 7, 3, 9).timestamp(), 10, 5.0),  # gap on the 4th
    ]
    assert aggregate(entries, today=today)["streak"] == 2


def test_top_apps_and_daily():
    today = date(2026, 7, 6)
    ts = datetime(2026, 7, 6, 12).timestamp()
    agg = aggregate([_e(ts, 5, 3.0, "Slack"), _e(ts, 5, 3.0, "Slack"),
                     _e(ts, 5, 3.0, "Notes")], today=today)
    assert agg["top_apps"][0] == ("Slack", 2)
    assert agg["daily"]["2026-07-06"] == 15
