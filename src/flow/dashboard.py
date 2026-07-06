"""Wispr-style stats dashboard: self-contained dark HTML, opened in the browser.

No external assets/CDNs — works fully offline.
"""
from __future__ import annotations

import html
import subprocess
import time
from datetime import datetime
from pathlib import Path

from flow import stats

OUT_PATH = Path.home() / ".flowclone_dashboard.html"

_CSS = """
:root{
  --bg:#0a0a0f;
  --surface:rgba(255,255,255,.035);
  --surface2:rgba(255,255,255,.065);
  --line:rgba(255,255,255,.07);
  --line2:rgba(255,255,255,.13);
  --txt:#f4f4f8;
  --txt2:#b9b9c6;
  --dim:#70707d;
  --acc:#8b7cff;
  --acc2:#c0b4ff;
  --glow:rgba(124,108,255,.16);
  --tipbg:rgba(30,30,40,.92);
  --shadow:0 14px 36px -20px rgba(0,0,0,.55);
  --inset:inset 0 1px 0 rgba(255,255,255,.05);
}
@media (prefers-color-scheme: light){
  :root{
    --bg:#f6f6f9;
    --surface:rgba(22,22,48,.035);
    --surface2:rgba(22,22,48,.07);
    --line:rgba(22,22,48,.08);
    --line2:rgba(22,22,48,.15);
    --txt:#16161d;
    --txt2:#4c4c58;
    --dim:#8a8a95;
    --acc:#6a58f0;
    --acc2:#8f7ff5;
    --glow:rgba(106,88,240,.11);
    --tipbg:rgba(255,255,255,.94);
    --shadow:0 14px 30px -22px rgba(30,30,70,.3);
    --inset:inset 0 1px 0 rgba(255,255,255,.85);
  }
}
*{margin:0;padding:0;box-sizing:border-box}
::selection{background:rgba(139,124,255,.35)}
::-webkit-scrollbar{width:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:5px;border:3px solid transparent;background-clip:padding-box}
body{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif;
  background:var(--bg);color:var(--txt);
  -webkit-font-smoothing:antialiased;min-height:100vh;overflow-x:hidden;
}
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(640px 320px at 50% -110px,var(--glow),transparent 70%);
}
.wrap{max-width:836px;margin:0 auto;padding:34px 48px 56px;position:relative;z-index:1}

/* entrance */
.in{opacity:0;animation:rise .55s cubic-bezier(.2,.7,.3,1) forwards;animation-delay:var(--d,0ms)}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}

/* header */
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:40px}
.brand{display:flex;align-items:center;gap:10px;font-size:15px;font-weight:600;letter-spacing:-.01em}
.brand svg{display:block;filter:drop-shadow(0 3px 10px var(--glow))}
.date{font-size:13px;color:var(--dim);font-variant-numeric:tabular-nums}

/* hero */
.hero{margin:4px 0 38px}
.hero-label{font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);margin-bottom:12px}
.hero-num{
  font-family:-apple-system,"SF Pro Display",sans-serif;
  font-size:84px;font-weight:700;line-height:1;letter-spacing:-.035em;
  font-variant-numeric:tabular-nums;
  background:linear-gradient(175deg,var(--txt) 45%,var(--acc2) 135%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-sub{margin-top:14px;font-size:14px;color:var(--txt2)}
.hero-sub b{color:var(--acc2);font-weight:600}
@media (prefers-color-scheme: light){.hero-sub b{color:var(--acc)}}

/* secondary stat strip */
.stats{display:flex;margin-bottom:40px}
.mini{flex:1;padding:2px 22px;border-left:1px solid var(--line)}
.mini:first-child{padding-left:0;border-left:none}
.mini b{display:block;font-size:22px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.mini b i{font-style:normal;font-size:14px;font-weight:500;color:var(--txt2);margin-left:1px}
.mini.muted b{color:var(--dim)}
.mini .ml{display:block;font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:.11em;color:var(--dim);margin-top:5px;white-space:nowrap}

/* sections + cards */
section{margin-bottom:30px}
.shead{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px}
.shead h2{font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
.shead .sm{font-size:12px;color:var(--dim);font-variant-numeric:tabular-nums}
.card{
  background:var(--surface);border:1px solid var(--line);border-radius:16px;
  box-shadow:var(--inset),var(--shadow);
}

/* chart */
.chartwrap{position:relative;padding:20px 14px 8px}
.chartwrap svg{display:block;width:100%;height:auto}
.xl{font-size:10px;fill:var(--dim);font-family:-apple-system,sans-serif}
.tip{
  position:absolute;top:10px;left:0;padding:5px 10px;border-radius:8px;
  background:var(--tipbg);border:1px solid var(--line2);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
  font-size:11.5px;font-weight:500;color:var(--txt);font-variant-numeric:tabular-nums;
  white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .15s;
  box-shadow:0 8px 20px -8px rgba(0,0,0,.45);
}
.flat{
  position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:13px;color:var(--dim);pointer-events:none;
}

/* two-column zone */
.cols{display:grid;grid-template-columns:292px 1fr;gap:20px;align-items:start}

/* list rows */
.rows{padding:6px}
.row{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:11px;transition:background .15s}
.row:hover{background:var(--surface2)}
.badge{
  width:30px;height:30px;border-radius:9px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:600;
  background:hsla(var(--h),72%,62%,.16);color:hsl(var(--h),75%,72%);
  box-shadow:inset 0 0 0 1px hsla(var(--h),72%,62%,.22);
}
@media (prefers-color-scheme: light){
  .badge{background:hsla(var(--h),70%,50%,.12);color:hsl(var(--h),65%,40%);
    box-shadow:inset 0 0 0 1px hsla(var(--h),70%,50%,.2)}
}
.badge.s{width:26px;height:26px;border-radius:8px;font-size:11.5px;align-self:flex-start;margin-top:2px}

/* top apps */
.am{flex:1;min-width:0}
.al{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.al .nm{font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.al .ct{font-size:12.5px;color:var(--txt2);font-variant-numeric:tabular-nums}
.track{height:3px;border-radius:2px;background:var(--line);margin-top:7px;overflow:hidden}
.fill{
  height:100%;border-radius:2px;background:linear-gradient(90deg,var(--acc),var(--acc2));
  transform:scaleX(var(--w,0));transform-origin:left;
  animation:grow .8s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--d,0ms);
}
@keyframes grow{from{transform:scaleX(0)}}

/* recent */
.rrow{align-items:flex-start}
.rrow + .rrow{border-top:1px solid var(--line)}
.rm{flex:1;min-width:0}
.rl{display:flex;align-items:baseline;gap:8px;min-width:0}
.rl .nm{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.rl .tm{font-size:11.5px;color:var(--dim);white-space:nowrap}
.rl .meta{margin-left:auto;font-size:11.5px;color:var(--dim);font-variant-numeric:tabular-nums;white-space:nowrap}
.txt{
  margin-top:3px;font-size:13px;line-height:1.45;color:var(--txt2);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  overflow-wrap:break-word;
}

/* empty state */
.empty{padding:88px 0 48px;display:flex;flex-direction:column;align-items:center;text-align:center}
.orb{
  width:104px;height:104px;border-radius:50%;margin-bottom:30px;
  display:flex;align-items:center;justify-content:center;gap:5px;
  background:
    radial-gradient(circle at 35% 28%,rgba(255,255,255,.12),transparent 55%),
    linear-gradient(150deg,rgba(139,124,255,.24),rgba(139,124,255,.05));
  box-shadow:inset 0 0 0 1px var(--line2),0 22px 60px -14px var(--glow);
}
.orb i{
  display:block;width:5px;border-radius:3px;
  background:linear-gradient(180deg,var(--acc2),var(--acc));
  animation:wave 1.7s cubic-bezier(.45,0,.55,1) infinite;animation-delay:var(--d,0s);
}
@keyframes wave{0%,100%{transform:scaleY(.5)}50%{transform:scaleY(1)}}
.empty h2{font-size:24px;font-weight:700;letter-spacing:-.02em;margin-bottom:10px}
.empty p{font-size:14px;color:var(--txt2);line-height:1.75;max-width:380px}
.kbd{
  display:inline-block;padding:2px 9px;border-radius:6px;margin:0 1px;
  background:var(--surface2);color:var(--txt);
  box-shadow:inset 0 0 0 1px var(--line2),inset 0 -1.5px 0 var(--line2);
  font-size:12.5px;font-weight:600;
}

/* narrow window */
@media (max-width: 720px){
  .wrap{padding:28px 28px 48px}
  .hero-num{font-size:60px}
  .stats{flex-wrap:wrap;gap:18px 0}
  .mini{flex-basis:33%;padding:0 16px}
  .mini:nth-child(4){border-left:none;padding-left:0}
  .cols{grid-template-columns:1fr}
}

@media (prefers-reduced-motion: reduce){
  .in{animation:none;opacity:1}
  .fill{animation:none}
  .orb i{animation:none;transform:scaleY(.8)}
}
"""

_JS = """
(function () {
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function fmt(v, dec) {
    return v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var target = parseFloat(el.getAttribute('data-count')) || 0;
    var dec = parseInt(el.getAttribute('data-dec') || '0', 10);
    var dur = parseInt(el.getAttribute('data-dur') || '900', 10);
    if (reduce || target === 0) { el.textContent = fmt(target, dec); return; }
    var t0 = null;
    function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * e, dec);
      if (p < 1) { requestAnimationFrame(step); } else { el.textContent = fmt(target, dec); }
    }
    requestAnimationFrame(step);
  });

  var wrap = document.getElementById('chartwrap');
  if (!wrap) return;
  var tip = document.getElementById('tip');
  var dot = document.getElementById('cdot');
  var svg = wrap.querySelector('svg');
  var vw = svg.viewBox.baseVal.width;
  wrap.querySelectorAll('.hit').forEach(function (r) {
    r.addEventListener('mouseenter', function () {
      tip.textContent = r.getAttribute('data-tip');
      dot.setAttribute('cx', r.getAttribute('data-px'));
      dot.setAttribute('cy', r.getAttribute('data-py'));
      dot.style.opacity = 1;
      tip.style.opacity = 1;
      var sb = svg.getBoundingClientRect(), wb = wrap.getBoundingClientRect();
      var x = sb.left - wb.left + (parseFloat(r.getAttribute('data-px')) / vw) * sb.width;
      var lx = Math.max(6, Math.min(wb.width - tip.offsetWidth - 6, x - tip.offsetWidth / 2));
      tip.style.left = lx + 'px';
    });
  });
  wrap.addEventListener('mouseleave', function () {
    tip.style.opacity = 0;
    dot.style.opacity = 0;
  });
})();
"""

_LOGO = (
    '<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">'
    '<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#a89bff"/><stop offset="1" stop-color="#6a58f0"/>'
    "</linearGradient></defs>"
    '<rect width="22" height="22" rx="7" fill="url(#lg)"/>'
    '<g fill="#fff" fill-opacity=".92">'
    '<rect x="5.4" y="8" width="2.4" height="6" rx="1.2"/>'
    '<rect x="9.8" y="5.5" width="2.4" height="11" rx="1.2"/>'
    '<rect x="14.2" y="8" width="2.4" height="6" rx="1.2"/>'
    "</g></svg>"
)


def _rel_time(ts: float) -> str:
    d = max(0.0, time.time() - ts)
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    if d < 7 * 86400:
        return f"{int(d // 86400)}d ago"
    return datetime.fromtimestamp(ts).strftime("%b %-d")


def _hue(name: str) -> int:
    return (sum(ord(c) * 31 for c in name) + 47) % 360


def _badge(name: str, small: bool = False) -> str:
    letter = html.escape((name.strip()[:1] or "?").upper())
    cls = "badge s" if small else "badge"
    return f'<div class="{cls}" style="--h:{_hue(name)}">{letter}</div>'


def _chart_svg(daily: dict[str, int]) -> str:
    """Smooth gradient area chart, hand-rolled inline SVG with hover targets."""
    W, H, PL, PR, PT, PB = 832, 190, 10, 10, 18, 30
    keys, vals = list(daily.keys()), list(daily.values())
    n = max(2, len(keys))
    vmax = max(vals) or 1
    iw, ih = W - PL - PR, H - PT - PB
    base = PT + ih
    pts = [
        (PL + i * iw / (n - 1), PT + (1 - v / vmax) * ih) for i, v in enumerate(vals)
    ]

    def p(i: int) -> tuple[float, float]:
        return pts[max(0, min(len(pts) - 1, i))]

    def cy(y: float) -> float:  # keep control points inside the plot
        return max(PT, min(base, y))

    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = p(i - 1), p(i), p(i + 1), p(i + 2)
        c1x, c1y = p1[0] + (p2[0] - p0[0]) / 6, cy(p1[1] + (p2[1] - p0[1]) / 6)
        c2x, c2y = p2[0] - (p3[0] - p1[0]) / 6, cy(p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    area = d + f" L{pts[-1][0]:.1f},{base:.1f} L{pts[0][0]:.1f},{base:.1f} Z"

    labels = "".join(
        f'<text class="xl" x="{pts[i][0]:.1f}" y="{H - 8}" text-anchor="middle">'
        f'{datetime.fromisoformat(keys[i]).strftime("%-d")}</text>'
        for i in range(len(keys))
        if i % 2 == 1
    )
    slice_w = iw / (n - 1)  # contiguous hover targets — no dead zones between days
    hits = "".join(
        f'<rect class="hit" x="{pts[i][0] - slice_w / 2:.1f}" y="0" '
        f'width="{slice_w:.1f}" height="{H}" fill="transparent" '
        f'data-px="{pts[i][0]:.1f}" data-py="{pts[i][1]:.1f}" '
        f'data-tip="{datetime.fromisoformat(keys[i]).strftime("%a, %b %-d")} '
        f'&#183; {vals[i]:,} words"/>'
        for i in range(len(keys))
    )
    lx, ly = pts[-1]
    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#8b7cff" stop-opacity=".32"/>'
        '<stop offset="1" stop-color="#8b7cff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="strk" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#8b7cff" stop-opacity=".35"/>'
        '<stop offset="1" stop-color="#a89bff"/></linearGradient></defs>'
        f'<line x1="{PL}" y1="{base:.1f}" x2="{W - PR}" y2="{base:.1f}" '
        'stroke="var(--line)" stroke-width="1"/>'
        f'<path d="{area}" fill="url(#area)"/>'
        f'<path d="{d}" fill="none" stroke="url(#strk)" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="8" fill="#8b7cff" fill-opacity=".18"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="#a89bff" '
        'stroke="var(--bg)" stroke-width="2"/>'
        '<circle id="cdot" r="4" fill="#a89bff" stroke="var(--bg)" stroke-width="2" '
        'style="opacity:0;transition:opacity .12s"/>'
        f"{labels}{hits}</svg>"
    )


def build_html(agg: dict, recent: list[dict]) -> str:
    today_str = datetime.now().strftime("%A, %B %-d")

    if agg["dictations"] == 0:
        main = """<div class="empty in" style="--d:80ms">
<div class="orb">
<i style="height:16px;--d:0s"></i><i style="height:30px;--d:.14s"></i>
<i style="height:44px;--d:.28s"></i><i style="height:30px;--d:.42s"></i>
<i style="height:16px;--d:.56s"></i>
</div>
<h2>Ready when you are</h2>
<p>Hold <span class="kbd">&#8997; right option</span>, speak, and let go.<br>
Your words land wherever your cursor is &mdash; and your story starts here.</p>
</div>"""
    else:
        # hero
        tw = agg["total_words"]
        pages = tw / 275.0
        if tw < 150:
            sub = "Every word counts &mdash; you're just getting started."
        elif pages < 2:
            sub = "About <b>a full page</b> of writing &mdash; spoken, not typed."
        else:
            sub = (
                f"About <b>{round(pages):,} pages</b> of writing "
                "&mdash; spoken, not typed."
            )
        hero = (
            '<div class="hero in" style="--d:60ms">'
            '<div class="hero-label">Words dictated</div>'
            f'<div class="hero-num"><span data-count="{tw}" data-dur="1200">0</span></div>'
            f'<div class="hero-sub">{sub}</div></div>'
        )

        # secondary stat strip
        sm = agg["saved_min"]
        if sm >= 90:
            saved_num, saved_label = f"{sm / 60:.1f}", "hrs saved"
        else:
            saved_num, saved_label = f"{sm:g}", "min saved"
        saved_dec = 0 if float(saved_num).is_integer() else 1
        lat = f"{agg['avg_latency']:.2f}"

        def mini(num: str, dec: int, suffix: str, label: str) -> str:
            muted = " muted" if float(num) == 0 else ""
            sfx = f"<i>{suffix}</i>" if suffix else ""
            return (
                f'<div class="mini{muted}"><b><span data-count="{num}" '
                f'data-dec="{dec}">0</span>{sfx}</b>'
                f'<span class="ml">{label}</span></div>'
            )

        minis = (
            mini(str(agg["dictations"]), 0, "", "dictations")
            + mini(str(agg["speak_wpm"]), 0, "", "speaking wpm")
            + mini(saved_num, saved_dec, "", saved_label)
            + mini(str(agg["streak"]), 0, "", "day streak")
            + mini(lat, 2, "s", "avg response")
        )
        strip = f'<div class="stats in" style="--d:120ms">{minis}</div>'

        # 14-day chart
        period_total = sum(agg["daily"].values())
        flat = (
            '<div class="flat">Quiet fortnight &mdash; nothing dictated yet</div>'
            if period_total == 0
            else ""
        )
        chart = (
            '<section class="in" style="--d:200ms"><div class="shead">'
            f'<h2>Last 14 days</h2><span class="sm">{period_total:,} words</span></div>'
            f'<div class="card chartwrap" id="chartwrap">{_chart_svg(agg["daily"])}'
            f'<div class="tip" id="tip"></div>{flat}</div></section>'
        )

        # top apps
        top = agg["top_apps"]
        maxn = top[0][1] if top else 1
        app_rows = "".join(
            f'<div class="row">{_badge(a)}<div class="am">'
            f'<div class="al"><span class="nm">{html.escape(a)}</span>'
            f'<span class="ct">{n:,}</span></div>'
            f'<div class="track"><div class="fill" '
            f'style="--w:{n / maxn:.3f};--d:{340 + i * 70}ms"></div></div>'
            "</div></div>"
            for i, (a, n) in enumerate(top)
        )

        # recent dictations
        items = list(reversed(recent[-14:]))
        rec_rows = "".join(
            f'<div class="row rrow">{_badge(e.get("app", "?"), small=True)}'
            '<div class="rm"><div class="rl">'
            f'<span class="nm">{html.escape(e.get("app", "?"))}</span>'
            f'<span class="tm">{_rel_time(e["ts"])}</span>'
            f'<span class="meta">{e.get("words", 0)} words &#183; '
            f'{e.get("latency", 0):g}s</span></div>'
            f'<p class="txt">{html.escape(e.get("text", ""))}</p></div></div>'
            for e in items
        )
        cols = (
            '<section class="cols">'
            '<div class="in" style="--d:260ms"><div class="shead"><h2>Top apps</h2>'
            "</div>"
            f'<div class="card rows">{app_rows}</div></div>'
            '<div class="in" style="--d:320ms"><div class="shead"><h2>Recent</h2>'
            f'<span class="sm">last {len(items)}</span></div>'
            f'<div class="card rows">{rec_rows}</div></div></section>'
        )

        main = hero + strip + chart + cols

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="color-scheme" content="dark light">
<title>Flow &mdash; Dashboard</title>
<style>{_CSS}</style></head><body>
<div class="wrap">
<header class="in"><div class="brand">{_LOGO}<span>Flow</span></div>
<div class="date">{today_str}</div></header>
{main}
</div>
<script>{_JS}</script>
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
    # launchd-started processes default to the Prohibited activation policy,
    # which silently refuses to display windows — promote to Accessory
    # (windows allowed, still no Dock icon).
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
    _window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
