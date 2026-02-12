"""
Dashboard Generator - Bloomberg 风格金融仪表盘 HTML 生成器
白底专业风格、数据密集、数据源链接可点击
"""
import json
from datetime import datetime
from models import SwarmReport, Signal, FactorCategory
from config import DATA_SOURCES, DASHBOARD_SOURCES


def _signal_text(signal: Signal) -> tuple:
    """返回 (label_cn, css_class)"""
    m = {
        Signal.BULLISH: ("BULLISH", "sig-bull"),
        Signal.BEARISH: ("BEARISH", "sig-bear"),
        Signal.NEUTRAL: ("NEUTRAL", "sig-neutral"),
    }
    return m[signal]


def _source_link(name: str, url: str) -> str:
    if not url:
        return f'<span class="src-calc">{name}</span>'
    return f'<a href="{url}" target="_blank" class="src-link">{name}<svg width="10" height="10" viewBox="0 0 12 12" style="margin-left:3px;vertical-align:middle;"><path d="M3.5 3H2.5A1.5 1.5 0 001 4.5v5A1.5 1.5 0 002.5 11h5A1.5 1.5 0 009 9.5V8.5M7 1h4v4M11 1L5.5 6.5" stroke="currentColor" fill="none" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg></a>'


def _live_badge(is_live: bool) -> str:
    if is_live:
        return '<span class="badge-live"><span class="live-dot"></span>LIVE</span>'
    return '<span class="badge-cached">CACHED</span>'


def generate_dashboard(report: SwarmReport) -> str:
    ts = report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    sig = report.overall_signal

    # 综合信号样式
    sig_map = {
        Signal.BULLISH: ("bull", "#0d7340", "#e6f4ed", "多头主导 — 宏观环境偏多", "BULLISH 多头"),
        Signal.BEARISH: ("bear", "#c41e3a", "#fce8ec", "空头主导 — 宏观环境偏空", "BEARISH 空头"),
        Signal.NEUTRAL: ("neutral", "#b8860b", "#fdf6e3", "多空均衡 — 无明确方向性信号", "NEUTRAL 中性"),
    }
    sig_cls, sig_color, sig_bg, sig_desc, sig_label = sig_map[sig]

    # Score bar position (range -1 to +1, map to 0%-100%)
    score_pct = max(0, min(100, (report.weighted_score + 1) / 2 * 100))

    # Agent sections
    agent_sections = ""
    cat_meta = {
        FactorCategory.LIQUIDITY: ("LIQUIDITY", "流动性", "liq"),
        FactorCategory.VALUATION: ("VALUATION", "估值", "val"),
        FactorCategory.RISK_SENTIMENT: ("RISK / SENTIMENT", "风险与情绪", "risk"),
    }

    for r in report.agent_results:
        if r.error:
            continue
        en_name, cn_name, cls = cat_meta.get(r.category, ("OTHER", "其他", "other"))
        sig_text, sig_css = _signal_text(r.signal)

        # Build factor rows
        factor_rows = ""
        for f in r.factors:
            val_display = f"{f.current_value}{f.unit}" if f.unit not in ('x', '%', 'T', 'B') else f"{f.current_value}{f.unit}"
            fsig_text, fsig_css = _signal_text(f.signal)

            hist_html = ""
            if f.historical_avg is not None:
                diff = f.current_value - f.historical_avg
                direction = "up" if diff > 0 else "down" if diff < 0 else ""
                hist_html = f'<div class="hist">avg {f.historical_avg}{f.unit} <span class="hist-{direction}">({diff:+.1f})</span></div>'

            conditions = ""
            if f.bull_condition or f.bear_condition:
                parts = []
                if f.bull_condition:
                    parts.append(f'<span class="cond-b">Bull: {f.bull_condition}</span>')
                if f.bear_condition:
                    parts.append(f'<span class="cond-r">Bear: {f.bear_condition}</span>')
                conditions = f'<div class="conds">{" ".join(parts)}</div>'

            src_html = _source_link(f.source.name, f.source.url) if f.source else ""
            live_html = _live_badge(f.is_live)

            factor_rows += f"""
              <tr class="frow">
                <td class="fcol-name">
                  <div class="fname">{f.name}</div>
                  <div class="fname-en">{f.name_en}</div>
                </td>
                <td class="fcol-val">{val_display}</td>
                <td class="fcol-sig"><span class="{fsig_css}">{fsig_text}</span></td>
                <td class="fcol-interp">
                  <div>{f.interpretation}</div>
                  {hist_html}
                  {conditions}
                </td>
                <td class="fcol-src">{src_html}<br>{live_html}</td>
              </tr>"""

        agent_sections += f"""
    <div class="agent-section agent-{cls}">
      <div class="agent-header">
        <div class="agent-label">
          <span class="agent-tag">{en_name}</span>
          <span class="agent-cn">{cn_name}</span>
        </div>
        <div class="agent-signal-wrap">
          <span class="{sig_css} sig-pill">{sig_text}</span>
          <span class="agent-conf">{r.confidence:.0%}</span>
        </div>
      </div>
      <div class="agent-formula-bar">
        <code>{r.formula}</code>
        <span class="formula-result">{r.summary}</span>
      </div>
      <table class="ftable">
        <thead>
          <tr>
            <th style="width:160px">INDICATOR</th>
            <th style="width:100px">VALUE</th>
            <th style="width:80px">SIGNAL</th>
            <th>INTERPRETATION</th>
            <th style="width:170px">SOURCE</th>
          </tr>
        </thead>
        <tbody>{factor_rows}</tbody>
      </table>
    </div>"""

    # Bull / Bear factor summary
    def _pill_list(items, cls):
        if not items:
            return '<span class="no-factors">—</span>'
        return "".join(f'<span class="factor-pill {cls}">{i}</span>' for i in items)

    bull_pills = _pill_list(report.bull_factors, "pill-bull")
    neutral_pills = _pill_list(report.neutral_factors, "pill-neutral")
    bear_pills = _pill_list(report.bear_factors, "pill-bear")

    # Data sources table
    source_rows = ""
    seen = set()
    for src in report.all_sources:
        if src.url and src.url not in seen:
            seen.add(src.url)
            source_rows += f"""
              <tr>
                <td class="ds-name">{src.name}</td>
                <td class="ds-url"><a href="{src.url}" target="_blank">{src.url}</a></td>
                <td class="ds-freq">{src.frequency}</td>
              </tr>"""
    for name, url in DASHBOARD_SOURCES.items():
        if url not in seen:
            source_rows += f"""
              <tr>
                <td class="ds-name">{name}</td>
                <td class="ds-url"><a href="{url}" target="_blank">{url}</a></td>
                <td class="ds-freq">—</td>
              </tr>"""

    # Data health
    total = report.live_count + report.fallback_count
    live_pct = (report.live_count / total * 100) if total else 0

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Factor Monitor | 美股宏观因子监控</title>
<style>
/* ═══════════════════════════════════════════════════
   Bloomberg-Inspired Light Theme
   Professional financial data dashboard
   ═══════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
  --white: #ffffff;
  --bg-page: #f5f6f8;
  --bg-card: #ffffff;
  --bg-subtle: #f8f9fb;
  --bg-hover: #f0f2f5;
  --border: #e2e5ea;
  --border-light: #eef0f4;
  --text-primary: #1a1e2c;
  --text-secondary: #5a6170;
  --text-tertiary: #8b919e;
  --text-muted: #b0b5c0;

  --green-600: #0d7340;
  --green-500: #16a34a;
  --green-100: #dcfce7;
  --green-50: #f0fdf4;
  --red-600: #c41e3a;
  --red-500: #dc2626;
  --red-100: #fee2e2;
  --red-50: #fef2f2;
  --amber-600: #b45309;
  --amber-500: #d97706;
  --amber-100: #fef3c7;
  --amber-50: #fffbeb;
  --blue-600: #1d4ed8;
  --blue-500: #2563eb;
  --blue-100: #dbeafe;
  --blue-50: #eff6ff;

  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg-page); color:var(--text-primary); font-family:var(--font-sans); font-size:13px; line-height:1.5; -webkit-font-smoothing:antialiased; }}

/* ── Top Bar (Bloomberg-style orange header bar) ── */
.topbar {{
  background: #f57c00;
  height: 4px;
  width: 100%;
}}

.container {{ max-width:1360px; margin:0 auto; padding:24px 32px 48px; }}

/* ── Header ── */
.header {{
  display:flex; justify-content:space-between; align-items:flex-start;
  padding:20px 0 16px; border-bottom:2px solid var(--text-primary); margin-bottom:24px;
}}
.header-left h1 {{
  font-size:20px; font-weight:800; color:var(--text-primary); letter-spacing:-0.5px;
  text-transform:uppercase;
}}
.header-left .subtitle {{
  font-size:11px; color:var(--text-tertiary); margin-top:2px;
  font-weight:500; letter-spacing:0.5px; text-transform:uppercase;
}}
.header-right {{
  text-align:right; font-variant-numeric:tabular-nums;
}}
.header-right .ts {{
  font-size:13px; font-weight:600; color:var(--text-primary);
  font-family:var(--font-mono);
}}
.header-right .health-row {{
  display:flex; align-items:center; justify-content:flex-end;
  gap:8px; margin-top:6px; font-size:11px; color:var(--text-tertiary);
}}
.health-bar {{
  width:64px; height:5px; background:var(--border); border-radius:3px; overflow:hidden;
}}
.health-fill {{
  height:100%; border-radius:3px;
}}

/* ── Signal Hero ── */
.signal-hero {{
  background: {sig_bg};
  border: 1px solid {sig_color}30;
  border-left: 5px solid {sig_color};
  border-radius: 2px;
  padding: 20px 28px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.signal-hero-left {{
  display:flex; align-items:center; gap:20px;
}}
.signal-hero-label {{
  font-size:10px; font-weight:700; color:var(--text-tertiary);
  text-transform:uppercase; letter-spacing:1.5px; margin-bottom:2px;
}}
.signal-hero-value {{
  font-size:26px; font-weight:800; color:{sig_color};
  letter-spacing:-0.5px;
}}
.signal-hero-desc {{
  font-size:12px; color:var(--text-secondary); margin-top:2px;
}}
.signal-hero-right {{
  text-align:right;
}}
.signal-score-label {{
  font-size:10px; color:var(--text-tertiary); text-transform:uppercase;
  letter-spacing:1px; margin-bottom:4px; font-weight:600;
}}
.score-bar-container {{
  width:200px; position:relative; margin-bottom:4px;
}}
.score-bar-bg {{
  width:100%; height:8px; background:linear-gradient(to right, var(--red-500), var(--amber-500), var(--green-500));
  border-radius:4px; opacity:0.25;
}}
.score-bar-indicator {{
  position:absolute; top:-2px; width:12px; height:12px;
  background:{sig_color}; border:2px solid var(--white);
  border-radius:50%; box-shadow:0 1px 3px rgba(0,0,0,0.2);
  transform:translateX(-50%);
  left:{score_pct:.1f}%;
}}
.score-meta {{
  font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);
  font-weight:500;
}}

/* ── Factor Summary Strip ── */
.factor-strip {{
  display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin-bottom:24px;
}}
.strip-col {{
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:2px; padding:14px 16px;
}}
.strip-col-title {{
  font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:1.2px; margin-bottom:10px; display:flex;
  align-items:center; gap:6px;
}}
.strip-col-title.bull {{ color:var(--green-600); }}
.strip-col-title.bear {{ color:var(--red-600); }}
.strip-col-title.neutral {{ color:var(--amber-600); }}
.strip-col-title .count {{
  background:currentColor; color:var(--white);
  font-size:10px; font-weight:700; width:18px; height:18px;
  display:inline-flex; align-items:center; justify-content:center;
  border-radius:9px;
}}
.factor-pill {{
  display:inline-block; padding:3px 10px; margin:2px 4px 2px 0;
  border-radius:2px; font-size:11px; font-weight:500;
}}
.pill-bull {{ background:var(--green-50); color:var(--green-600); border:1px solid var(--green-100); }}
.pill-bear {{ background:var(--red-50); color:var(--red-600); border:1px solid var(--red-100); }}
.pill-neutral {{ background:var(--bg-subtle); color:var(--text-secondary); border:1px solid var(--border-light); }}
.no-factors {{ color:var(--text-muted); font-size:12px; }}

/* ── Agent Sections ── */
.agent-section {{
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:2px; margin-bottom:20px; overflow:hidden;
}}
.agent-header {{
  display:flex; justify-content:space-between; align-items:center;
  padding:14px 20px; border-bottom:1px solid var(--border);
  background:var(--bg-subtle);
}}
.agent-label {{
  display:flex; align-items:center; gap:10px;
}}
.agent-tag {{
  font-size:11px; font-weight:800; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-primary);
}}
.agent-cn {{
  font-size:12px; color:var(--text-tertiary); font-weight:500;
}}
.agent-signal-wrap {{
  display:flex; align-items:center; gap:10px;
}}
.sig-pill {{
  padding:3px 12px; border-radius:2px; font-size:11px;
  font-weight:700; letter-spacing:0.5px;
}}
.sig-bull {{ background:var(--green-100); color:var(--green-600); }}
.sig-bear {{ background:var(--red-100); color:var(--red-600); }}
.sig-neutral {{ background:var(--amber-100); color:var(--amber-600); }}
.agent-conf {{
  font-size:11px; color:var(--text-tertiary); font-family:var(--font-mono);
}}
.agent-liq .agent-header {{ border-top:3px solid var(--blue-500); }}
.agent-val .agent-header {{ border-top:3px solid var(--amber-500); }}
.agent-risk .agent-header {{ border-top:3px solid var(--red-500); }}

/* ── Formula Bar ── */
.agent-formula-bar {{
  display:flex; align-items:center; gap:16px;
  padding:10px 20px; background:var(--bg-page);
  border-bottom:1px solid var(--border-light);
}}
.agent-formula-bar code {{
  font-family:var(--font-mono); font-size:12px;
  color:var(--blue-600); font-weight:500;
  background:var(--blue-50); padding:2px 10px;
  border-radius:2px; border:1px solid var(--blue-100);
  white-space:nowrap;
}}
.formula-result {{
  font-size:12px; color:var(--text-secondary);
  font-family:var(--font-mono); font-weight:400;
}}

/* ── Factor Table ── */
.ftable {{
  width:100%; border-collapse:collapse;
}}
.ftable thead th {{
  text-align:left; padding:8px 16px;
  font-size:10px; font-weight:700; color:var(--text-tertiary);
  text-transform:uppercase; letter-spacing:0.8px;
  background:var(--bg-subtle); border-bottom:1px solid var(--border);
}}
.ftable thead th:nth-child(2),
.ftable thead th:nth-child(3) {{ text-align:center; }}
.frow {{ border-bottom:1px solid var(--border-light); transition:background 0.1s; }}
.frow:hover {{ background:var(--bg-hover); }}
.frow:last-child {{ border-bottom:none; }}
.frow td {{ padding:10px 16px; vertical-align:top; }}

.fcol-name {{ }}
.fname {{ font-size:13px; font-weight:600; color:var(--text-primary); }}
.fname-en {{ font-size:10px; color:var(--text-muted); margin-top:1px; }}
.fcol-val {{
  text-align:center; font-size:14px; font-weight:700;
  color:var(--text-primary); font-family:var(--font-mono);
  font-variant-numeric:tabular-nums;
}}
.fcol-sig {{ text-align:center; }}
.fcol-interp {{
  font-size:12px; color:var(--text-secondary);
}}
.hist {{
  font-size:11px; color:var(--text-tertiary); margin-top:2px;
}}
.hist-up {{ color:var(--green-600); }}
.hist-down {{ color:var(--red-600); }}
.conds {{ margin-top:3px; display:flex; gap:8px; }}
.cond-b {{ font-size:10px; color:var(--green-600); }}
.cond-r {{ font-size:10px; color:var(--red-600); }}

.fcol-src {{
  text-align:right; font-size:11px;
}}
.src-link {{
  color:var(--blue-600); text-decoration:none;
  font-size:11px; font-weight:500;
}}
.src-link:hover {{ text-decoration:underline; }}
.src-calc {{ color:var(--text-muted); font-size:11px; font-style:italic; }}
.badge-live {{
  display:inline-flex; align-items:center; gap:3px;
  background:var(--green-50); color:var(--green-600);
  padding:1px 6px; border-radius:2px; font-size:9px;
  font-weight:700; letter-spacing:0.5px; border:1px solid var(--green-100);
}}
.live-dot {{
  width:5px; height:5px; background:var(--green-500);
  border-radius:50%; animation:pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
  0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }}
}}
.badge-cached {{
  background:var(--amber-50); color:var(--amber-600);
  padding:1px 6px; border-radius:2px; font-size:9px;
  font-weight:700; letter-spacing:0.5px; border:1px solid var(--amber-100);
}}

/* ── Data Sources Section ── */
.sources-section {{
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:2px; margin-top:24px; overflow:hidden;
}}
.sources-section h3 {{
  padding:12px 20px; font-size:11px; font-weight:800;
  color:var(--text-primary); text-transform:uppercase;
  letter-spacing:1px; background:var(--bg-subtle);
  border-bottom:1px solid var(--border);
}}
.dstable {{
  width:100%; border-collapse:collapse;
}}
.dstable thead th {{
  text-align:left; padding:8px 20px; font-size:10px;
  font-weight:700; color:var(--text-tertiary);
  text-transform:uppercase; letter-spacing:0.8px;
  border-bottom:1px solid var(--border);
}}
.dstable tbody tr {{
  border-bottom:1px solid var(--border-light); transition:background 0.1s;
}}
.dstable tbody tr:hover {{ background:var(--bg-hover); }}
.dstable td {{ padding:7px 20px; font-size:12px; }}
.ds-name {{ font-weight:600; color:var(--text-primary); white-space:nowrap; }}
.ds-url a {{
  color:var(--blue-600); text-decoration:none;
  font-family:var(--font-mono); font-size:11px; word-break:break-all;
}}
.ds-url a:hover {{ text-decoration:underline; }}
.ds-freq {{ color:var(--text-tertiary); font-size:11px; }}

/* ── Notes ── */
.notes-section {{
  background:var(--bg-card); border:1px solid var(--border);
  border-radius:2px; padding:20px 24px; margin-top:16px;
}}
.notes-section h3 {{
  font-size:12px; font-weight:700; color:var(--text-primary);
  text-transform:uppercase; letter-spacing:0.5px; margin-bottom:12px;
}}
.notes-grid {{
  display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px;
}}
.note-item {{
  display:flex; gap:10px; font-size:12px; color:var(--text-secondary);
}}
.note-num {{
  flex-shrink:0; width:20px; height:20px;
  background:var(--bg-page); border:1px solid var(--border);
  border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:10px; font-weight:700; color:var(--text-tertiary);
}}
.note-item strong {{ color:var(--text-primary); font-weight:600; }}

/* ── Footer ── */
.footer {{
  display:flex; justify-content:space-between; align-items:center;
  padding:20px 0 0; margin-top:24px; border-top:2px solid var(--text-primary);
  font-size:10px; color:var(--text-muted); text-transform:uppercase;
  letter-spacing:0.5px;
}}

/* ── Responsive ── */
@media (max-width:960px) {{
  .container {{ padding:16px; }}
  .factor-strip {{ grid-template-columns:1fr; }}
  .signal-hero {{ flex-direction:column; gap:16px; text-align:center; }}
  .signal-hero-right {{ text-align:center; }}
  .ftable {{ font-size:12px; }}
  .ftable thead th:nth-child(4),
  .ftable thead th:nth-child(5),
  .frow td:nth-child(4),
  .frow td:nth-child(5) {{ display:none; }}
  .agent-formula-bar {{ flex-direction:column; align-items:flex-start; gap:6px; }}
  .notes-grid {{ grid-template-columns:1fr; }}
}}

@media print {{
  body {{ background:#fff; }}
  .topbar {{ display:none; }}
  .container {{ padding:0; max-width:100%; }}
}}
</style>
</head>
<body>

<div class="topbar"></div>

<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <h1>MACRO FACTOR MONITOR</h1>
      <div class="subtitle">US Equity Multi-Factor Dashboard &mdash; Agent Swarm v3.0</div>
    </div>
    <div class="header-right">
      <div class="ts">{ts}</div>
      <div class="health-row">
        DATA HEALTH
        <div class="health-bar">
          <div class="health-fill" style="width:{live_pct:.0f}%;background:{'var(--green-500)' if live_pct > 70 else 'var(--amber-500)' if live_pct > 30 else 'var(--red-500)'}"></div>
        </div>
        <span>{report.live_count}/{total} live</span>
      </div>
    </div>
  </div>

  <!-- Overall Signal -->
  <div class="signal-hero">
    <div class="signal-hero-left">
      <div>
        <div class="signal-hero-label">COMPOSITE SIGNAL</div>
        <div class="signal-hero-value">{sig_label}</div>
        <div class="signal-hero-desc">{sig_desc}</div>
      </div>
    </div>
    <div class="signal-hero-right">
      <div class="signal-score-label">WEIGHTED SCORE</div>
      <div class="score-bar-container">
        <div class="score-bar-bg"></div>
        <div class="score-bar-indicator"></div>
      </div>
      <div class="score-meta">{report.weighted_score:+.3f} &nbsp;&bull;&nbsp; Bull {len(report.bull_factors)} &bull; Neutral {len(report.neutral_factors)} &bull; Bear {len(report.bear_factors)}</div>
    </div>
  </div>

  <!-- Factor Summary Strip -->
  <div class="factor-strip">
    <div class="strip-col">
      <div class="strip-col-title bull">
        BULLISH FACTORS <span class="count">{len(report.bull_factors)}</span>
      </div>
      {bull_pills}
    </div>
    <div class="strip-col">
      <div class="strip-col-title neutral">
        NEUTRAL FACTORS <span class="count">{len(report.neutral_factors)}</span>
      </div>
      {neutral_pills}
    </div>
    <div class="strip-col">
      <div class="strip-col-title bear">
        BEARISH FACTORS <span class="count">{len(report.bear_factors)}</span>
      </div>
      {bear_pills}
    </div>
  </div>

  <!-- Agent Detail Sections -->
  {agent_sections}

  <!-- Data Sources -->
  <div class="sources-section">
    <h3>DATA SOURCES</h3>
    <table class="dstable">
      <thead>
        <tr>
          <th style="width:180px">Indicator</th>
          <th>Source URL</th>
          <th style="width:80px">Frequency</th>
        </tr>
      </thead>
      <tbody>{source_rows}</tbody>
    </table>
  </div>

  <!-- Usage Notes -->
  <div class="notes-section">
    <h3>METHODOLOGY NOTES</h3>
    <div class="notes-grid">
      <div class="note-item">
        <div class="note-num">1</div>
        <div><strong>Filter, Not Predictor</strong> &mdash; 宏观因子用于确认趋势方向，配合技术分析选择入场点</div>
      </div>
      <div class="note-item">
        <div class="note-num">2</div>
        <div><strong>Marginal Changes</strong> &mdash; 因子的变化趋势比绝对值更重要，关注边际变化</div>
      </div>
      <div class="note-item">
        <div class="note-num">3</div>
        <div><strong>Multi-Factor Resonance</strong> &mdash; 单一因子信号弱，多因子同向共振时信号更强</div>
      </div>
      <div class="note-item">
        <div class="note-num">4</div>
        <div><strong>Daily Updates</strong> &mdash; 每日检查流动性数据，重大经济数据发布后及时更新</div>
      </div>
      <div class="note-item">
        <div class="note-num">5</div>
        <div><strong>Technical Confluence</strong> &mdash; 宏观因子确定方向，技术分析确定时机与执行</div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <span>MACRO FACTOR SWARM V3.0 &mdash; AGENT SWARM + SQLITE PERSISTENCE</span>
    <span>{report.live_count} LIVE + {report.fallback_count} CACHED &mdash; {ts}</span>
  </div>

</div>
</body>
</html>"""

    return html
