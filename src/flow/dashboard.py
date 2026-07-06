"""Wispr-style stats dashboard: self-contained dark HTML, opened in the browser.

No external assets/CDNs — works fully offline.
"""
from __future__ import annotations

import html
import subprocess
from datetime import datetime
from pathlib import Path

from flow import stats

OUT_PATH = Path.home() / ".flowclone_dashboard.html"

_CSS = """
:root{--bg:#0b0b0f;--card:#16161d;--txt:#f2f2f5;--dim:#8a8a93;--acc:#7c6cff;--bar:#7c6cff}
*{margin:0;box-sizing:border-box;font-family:-apple-system,'SF Pro Display',sans-serif}
body{background:var(--bg);color:var(--txt);padding:40px;max-width:900px;margin:0 auto}
h1{font-size:26px;font-weight:700;margin-bottom:4px}
.sub{color:var(--dim);margin-bottom:28px;font-size:14px}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:28px}
.card{background:var(--card);border-radius:14px;padding:18px 16px;border:1px solid #ffffff0d}
.card b{display:block;font-size:26px;font-weight:700}
.card span{color:var(--dim);font-size:12px}
h2{font-size:15px;margin:26px 0 12px;color:var(--dim);font-weight:600}
.chart{display:flex;align-items:flex-end;gap:6px;height:120px;background:var(--card);
border-radius:14px;padding:16px;border:1px solid #ffffff0d}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}
.bar{width:100%;background:var(--bar);border-radius:4px 4px 0 0;min-height:2px}
.col em{font-size:9px;color:var(--dim);font-style:normal;margin-top:6px}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{background:var(--card);border:1px solid #ffffff0d;border-radius:20px;padding:6px 14px;font-size:13px}
.chip b{color:var(--acc)}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:14px;overflow:hidden;border:1px solid #ffffff0d}
td{padding:10px 14px;font-size:13px;border-top:1px solid #ffffff0a;vertical-align:top}
td.t{color:var(--dim);white-space:nowrap;width:110px}td.a{color:var(--acc);white-space:nowrap;width:90px}
"""


def build_html(agg: dict, recent: list[dict]) -> str:
    max_daily = max(agg["daily"].values()) or 1
    cols = "".join(
        f'<div class="col"><div class="bar" style="height:{max(2, round(v / max_daily * 100))}%"></div>'
        f"<em>{k[5:].replace('-', '/')}</em></div>"
        for k, v in agg["daily"].items()
    )
    chips = "".join(
        f'<div class="chip">{html.escape(a)} <b>{n}</b></div>' for a, n in agg["top_apps"]
    )
    rows = "".join(
        f'<tr><td class="t">{datetime.fromtimestamp(e["ts"]).strftime("%b %d %H:%M")}</td>'
        f'<td class="a">{html.escape(e["app"])}</td><td>{html.escape(e["text"])}</td></tr>'
        for e in reversed(recent[-25:])
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Flow — Dashboard</title>
<style>{_CSS}</style></head><body>
<h1>Flow</h1><div class="sub">Your dictation stats — all local, all yours.</div>
<div class="cards">
<div class="card"><b>{agg["total_words"]:,}</b><span>words dictated</span></div>
<div class="card"><b>{agg["dictations"]:,}</b><span>dictations</span></div>
<div class="card"><b>{agg["speak_wpm"]}</b><span>speaking WPM</span></div>
<div class="card"><b>{agg["saved_min"]:g}m</b><span>saved vs typing</span></div>
<div class="card"><b>{agg["streak"]}🔥</b><span>day streak</span></div>
</div>
<h2>LAST 14 DAYS (WORDS)</h2><div class="chart">{cols}</div>
<h2>TOP APPS</h2><div class="chips">{chips or '<div class="chip">no data yet</div>'}</div>
<h2>RECENT DICTATIONS · avg latency {agg["avg_latency"]}s</h2>
<table>{rows or '<tr><td>Dictate something first!</td></tr>'}</table>
</body></html>"""


def open_dashboard() -> None:
    """Fallback: render to file and open in the browser."""
    entries = stats.load()
    OUT_PATH.write_text(build_html(stats.aggregate(entries), entries))
    subprocess.run(["open", str(OUT_PATH)], check=False)


_window = None  # kept alive between opens


def show_window() -> None:
    """Native in-app dashboard window (WKWebView). MAIN THREAD ONLY."""
    global _window
    from AppKit import NSApplication, NSMakeRect
    from WebKit import WKWebView

    if _window is None:
        from AppKit import NSWindow

        rect = NSMakeRect(0, 0, 940, 700)
        style = 1 | 2 | 4 | 8  # titled | closable | miniaturizable | resizable
        _window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, 2, False
        )
        _window.setTitle_("Flow")
        _window.setReleasedWhenClosed_(False)  # reuse across open/close
        _window.setContentView_(WKWebView.alloc().initWithFrame_(rect))
        _window.center()

    entries = stats.load()
    html_doc = build_html(stats.aggregate(entries), entries)
    _window.contentView().loadHTMLString_baseURL_(html_doc, None)
    _window.makeKeyAndOrderFront_(None)
    # LSUIElement apps don't come forward on their own
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
