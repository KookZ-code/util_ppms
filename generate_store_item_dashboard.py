#!/usr/bin/env python3
"""Store Item Usage/Cost Interactive Dashboard Generator — MTHAI only

Usage:  python generate_store_item_dashboard.py
Output: Output/store_item_dashboard.html

To add a new month: drop the SUM ISSUED ASSY <MON>'<YY>_*.xlsx file into
raw/Store item/ and re-run this script. No code changes needed.
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.store_item_loader import (
    BASE, MONTH_ORDER, ASO_MONTHS,
    load_aso2025, load_sum_assy, normalize,
)

OUTPUT = Path(r"D:\claude\Project\Output\store_item_dashboard.html")
OUTPUT.parent.mkdir(exist_ok=True)


# ── Build data JSON ────────────────────────────────────────────────────────────
def build_json(df: pd.DataFrame) -> str:
    out = df[["Month","Source","Item","Description","Process","Machine_model",
              "Category","Quantity","Total"]].copy()
    out["Month"] = out["Month"].astype(str)
    out["Total"] = out["Total"].round(2)

    present_months = [m for m in MONTH_ORDER if m in out["Month"].values]

    def clean(s):
        return sorted([x for x in s.dropna().unique() if x and x not in ('nan','None','')])

    return json.dumps({
        "records":      out.to_dict(orient="records"),
        "month_order":  present_months,
        "aso_months":   [m for m in present_months if m in ASO_MONTHS],
        "filters": {
            "months":     present_months,
            "processes":  clean(df["Process"]),
            "categories": clean(df["Category"]),
        },
        "generated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False, default=str)


# ── HTML template ──────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Store Item Monitor — MTHAI</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#1B3A5C;--blue:#2E75B6;--blue-lt:#7AB3DE;
  --green:#2D8E4E;--red:#C0392B;--orange:#E67E22;
  --bg:#EEF1F5;--surface:#fff;--border:#DDE2E9;
  --text:#0F1C2E;--muted:#64748B;--muted2:#94A3B8;
}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px;-webkit-font-smoothing:antialiased}

/* ── RESET & BASE ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);
  min-height:100vh;font-size:14px;-webkit-font-smoothing:antialiased}

/* ── HEADER ── */
.header{
  background:linear-gradient(135deg,#1B3A5C 0%,#1e4876 100%);
  height:58px;padding:0 28px;display:flex;align-items:center;
  justify-content:space-between;position:sticky;top:0;z-index:200;
  box-shadow:0 2px 16px rgba(15,28,46,.35)}
.hd-left{display:flex;align-items:center;gap:12px}
.hd-logo{width:32px;height:32px;background:rgba(255,255,255,.15);border-radius:8px;
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-weight:800;font-size:14px;letter-spacing:-.5px;flex-shrink:0;
  border:1px solid rgba(255,255,255,.2)}
.hd-divider{width:1px;height:28px;background:rgba(255,255,255,.15)}
.hd-title{color:#fff;font-size:15px;font-weight:700;letter-spacing:-.01em}
.hd-sub{color:rgba(255,255,255,.45);font-size:11px;font-weight:400;margin-top:1px}
.hd-right{display:flex;align-items:center;gap:10px}
.hd-badge{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);
  color:rgba(255,255,255,.7);font-size:10.5px;font-weight:500;
  padding:3px 10px;border-radius:20px}

/* ── SCOPE BANNER ── */
.scope-banner{background:#FFFBEB;border-bottom:1px solid #FDE68A;
  border-left:4px solid #F59E0B;padding:8px 28px;font-size:11.5px;
  color:#78350F;display:flex;align-items:center;gap:8px;font-weight:500}
.scope-banner.hidden{display:none}

/* ── FILTER BAR ── */
.filter-bar{background:var(--surface);border-bottom:1px solid var(--border);
  padding:10px 28px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  position:sticky;top:58px;z-index:100;
  box-shadow:0 2px 8px rgba(15,28,46,.06)}
.fl{font-size:10.5px;font-weight:700;color:var(--muted2);text-transform:uppercase;
  letter-spacing:.06em;white-space:nowrap;flex-shrink:0}
.fdiv{width:1px;height:24px;background:var(--border);flex-shrink:0;margin:0 2px}

/* Period selector */
.period-wrap{display:flex;align-items:center;gap:8px;
  background:#F8FAFC;border:1.5px solid var(--border);
  border-radius:8px;padding:4px 12px 4px 10px}
.period-sel{border:none;background:transparent;font-size:13px;font-weight:600;
  color:var(--navy);cursor:pointer;font-family:inherit;outline:none;
  padding:2px 18px 2px 0;appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='9' height='5'%3E%3Cpath d='M0 0l4.5 5L9 0z' fill='%231B3A5C'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 2px center}
.period-arrow{color:var(--muted2);font-size:13px;user-select:none}
.period-count{font-size:11px;font-weight:600;color:var(--blue);
  background:#EAF2FB;padding:2px 8px;border-radius:12px;white-space:nowrap}

/* Dropdowns */
.fsel{padding:5px 26px 5px 10px;border:1.5px solid var(--border);border-radius:8px;
  font-size:12px;font-family:inherit;color:var(--text);background:var(--bg);
  appearance:none;cursor:pointer;outline:none;font-weight:500;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='9' height='5'%3E%3Cpath d='M0 0l4.5 5L9 0z' fill='%2364748B'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 8px center;transition:border-color .12s}
.fsel:focus{border-color:var(--blue)}

/* Search */
.search-wrap{position:relative;margin-left:auto}
.search-wrap svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted2)}
.search-inp{padding:6px 10px 6px 32px;border:1.5px solid var(--border);border-radius:8px;
  font-size:12.5px;font-family:inherit;width:220px;outline:none;
  transition:border-color .12s;background:var(--bg);font-weight:400}
.search-inp:focus{border-color:var(--blue);background:#fff}
.search-inp::placeholder{color:var(--muted2)}

/* Reset */
.reset-btn{padding:5px 13px;border:1.5px solid var(--border);border-radius:8px;
  font-size:12px;font-weight:600;font-family:inherit;background:transparent;
  color:var(--muted);cursor:pointer;transition:all .12s;white-space:nowrap}
.reset-btn:hover{border-color:var(--red);color:var(--red);background:#FEF2F2}

/* ── MAIN LAYOUT ── */
.main{padding:20px 28px;display:flex;flex-direction:column;gap:16px;max-width:1600px;margin:0 auto;width:100%}
.main-full{padding:20px 28px 28px;display:flex;flex-direction:column;gap:16px}

/* ── KPI CARDS ── */
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi{background:var(--surface);border-radius:12px;padding:18px 20px 16px;
  box-shadow:0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.06);
  border:1px solid var(--border);position:relative;overflow:hidden;
  transition:box-shadow .2s}
.kpi:hover{box-shadow:0 4px 24px rgba(0,0,0,.1)}
.kpi-stripe{position:absolute;top:0;left:0;right:0;height:3px;border-radius:12px 12px 0 0}
.kpi-top{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.kpi-lbl{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.kpi-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;
  justify-content:center;flex-shrink:0}
.kpi-val{font-size:28px;font-weight:800;line-height:1;color:var(--text);letter-spacing:-.02em}
.kpi-val-unit{font-size:13px;font-weight:500;color:var(--muted);margin-left:3px}
.kpi-sub{font-size:11.5px;color:var(--muted);margin-top:6px;display:flex;align-items:center;gap:5px}
.kpi-badge{display:inline-flex;align-items:center;gap:3px;font-size:11.5px;font-weight:700;
  padding:2px 8px;border-radius:20px}
.kpi-badge.up{background:#FEE2E2;color:#B91C1C}
.kpi-badge.dn{background:#DCFCE7;color:#15803D}
.kpi-badge.neu{background:#F1F5F9;color:var(--muted)}

/* ── GENERIC CARD ── */
.card{background:var(--surface);border-radius:12px;padding:18px 22px;
  box-shadow:0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.06);
  border:1px solid var(--border)}
.card-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.card-title{font-size:13.5px;font-weight:700;color:var(--text);letter-spacing:-.01em}
.card-right{display:flex;align-items:center;gap:10px}
.card-badge{font-size:10.5px;font-weight:700;color:var(--muted);
  background:var(--bg);border:1px solid var(--border);padding:3px 8px;border-radius:6px;
  letter-spacing:.02em;text-transform:uppercase}
.legend{display:flex;gap:14px;align-items:center}
.legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);font-weight:500}
.ldot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}

/* ── TABLE ── */
.tbl-toolbar{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px}
.tbl-meta{font-size:11px;color:var(--muted2);margin-top:4px}
.tbl-search-wrap{position:relative}
.tbl-search-wrap svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted2)}
.tbl-search{padding:7px 12px 7px 32px;border:1.5px solid var(--border);border-radius:8px;
  font-size:12.5px;font-family:inherit;width:260px;outline:none;transition:border-color .12s;background:var(--bg)}
.tbl-search:focus{border-color:var(--blue);background:#fff}

table{width:100%;border-collapse:collapse;font-size:12.5px}
thead tr{background:var(--bg)}
thead th{text-align:left;padding:9px 14px;font-size:10.5px;font-weight:700;
  color:var(--muted2);text-transform:uppercase;letter-spacing:.06em;
  border-bottom:2px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none;
  transition:color .1s}
thead th:hover{color:var(--navy)}
thead th.sorted-asc::after{content:' ↑';color:var(--blue);font-size:11px}
thead th.sorted-desc::after{content:' ↓';color:var(--blue);font-size:11px}
tbody tr{border-bottom:1px solid #F1F4F8;transition:background .1s}
tbody tr:nth-child(even){background:#FAFBFC}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:#EEF4FF !important}
tbody td{padding:9px 14px;vertical-align:middle;color:var(--text)}
.mono{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:var(--muted);font-weight:500}
.cost{font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--navy);text-align:right}
.ptag{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;
  font-weight:600;background:#F1F5F9;color:#475569}

/* ── PAGINATION ── */
.pagination{display:flex;align-items:center;justify-content:space-between;
  margin-top:14px;padding-top:12px;border-top:1px solid var(--border)}
.pg-info{font-size:11px;color:var(--muted2);font-weight:500}
.pg-btns{display:flex;gap:3px}
.pg-btn{min-width:30px;height:30px;padding:0 8px;display:flex;align-items:center;
  justify-content:center;border:1.5px solid var(--border);border-radius:7px;
  font-size:12px;font-weight:600;cursor:pointer;background:var(--bg);
  color:var(--muted);transition:all .12s;font-family:inherit}
.pg-btn.active{background:var(--navy);border-color:var(--navy);color:#fff}
.pg-btn:hover:not(.active):not(:disabled){border-color:var(--blue);color:var(--blue);background:#EAF2FB}
.pg-btn:disabled{opacity:.3;cursor:default}

/* ── EXPORT BUTTON ── */
.export-btn{display:flex;align-items:center;gap:6px;padding:6px 14px;
  border:1.5px solid var(--blue);border-radius:8px;font-size:12px;font-weight:600;
  font-family:inherit;color:var(--blue);background:#fff;cursor:pointer;
  transition:all .12s;white-space:nowrap}
.export-btn:hover{background:var(--blue);color:#fff}

/* ── FOOTER ── */
.footer{padding:14px 28px;text-align:right;font-size:11px;color:var(--muted2);
  border-top:1px solid var(--border);background:var(--surface)}
</style>
</head>
<body>

<header class="header">
  <div class="hd-left">
    <div class="hd-logo">SI</div>
    <div class="hd-divider"></div>
    <div>
      <div class="hd-title">Store Item Usage Monitor</div>
      <div class="hd-sub">ASSY Division · MTHAI</div>
    </div>
  </div>
  <div class="hd-right">
    <span class="hd-badge" id="gen-date"></span>
  </div>
</header>


<div class="filter-bar">
  <span class="fl">Period</span>
  <div class="period-wrap">
    <select id="from-month" class="period-sel"></select>
    <span class="period-arrow">→</span>
    <select id="to-month" class="period-sel"></select>
    <span class="period-count" id="period-count"></span>
  </div>
  <div class="fdiv"></div>
  <span class="fl">Process</span>
  <select id="proc-sel" class="fsel"><option value="">All Processes</option></select>
  <span class="fl">Category</span>
  <select id="cat-sel" class="fsel"><option value="">All Categories</option></select>
  <div class="search-wrap">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input id="srch" class="search-inp" type="text" placeholder="Item # or description…"/>
  </div>
  <button id="reset-btn" class="reset-btn">↺ Reset</button>
</div>

<div class="main-full">
<div class="main">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-stripe" style="background:#1B3A5C"></div>
      <div class="kpi-top">
        <div class="kpi-lbl">Total Cost</div>
        <div class="kpi-icon" style="background:#EAF2FB">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2E75B6" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        </div>
      </div>
      <div class="kpi-val" id="kpi-total">—</div>
      <div class="kpi-sub" id="kpi-total-sub"></div>
    </div>
    <div class="kpi">
      <div class="kpi-stripe" style="background:#2E75B6"></div>
      <div class="kpi-top">
        <div class="kpi-lbl">Latest Month</div>
        <div class="kpi-icon" style="background:#EAF2FB">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2E75B6" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        </div>
      </div>
      <div class="kpi-val" id="kpi-latest">—</div>
      <div class="kpi-sub" id="kpi-latest-sub"></div>
    </div>
    <div class="kpi">
      <div class="kpi-stripe" style="background:#E67E22"></div>
      <div class="kpi-top">
        <div class="kpi-lbl">MoM Change</div>
        <div class="kpi-icon" style="background:#FEF3E7">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E67E22" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
        </div>
      </div>
      <div class="kpi-val" id="kpi-mom" style="font-size:24px">—</div>
      <div class="kpi-sub" id="kpi-mom-sub"></div>
    </div>
    <div class="kpi">
      <div class="kpi-stripe" style="background:#2D8E4E"></div>
      <div class="kpi-top">
        <div class="kpi-lbl">Unique Items</div>
        <div class="kpi-icon" style="background:#EAFAF0">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2D8E4E" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
        </div>
      </div>
      <div class="kpi-val" id="kpi-items">—</div>
      <div class="kpi-sub">distinct part numbers</div>
    </div>
  </div>

  <!-- Trend Chart -->
  <div class="card">
    <div class="card-hd">
      <span class="card-title">Monthly Cost Trend</span>
      <span class="card-badge" id="trend-total-badge"></span>
    </div>
    <div style="height:250px;padding-top:8px"><canvas id="trendChart"></canvas></div>
  </div>

  <!-- Process + Machine -->
  <div class="chart-row">
    <div class="card">
      <div class="card-hd">
        <span class="card-title">Cost by Process</span>
        <span class="card-badge">Top 10</span>
      </div>
      <div style="height:310px"><canvas id="procChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-hd">
        <span class="card-title">Cost by Machine Model</span>
        <span class="card-badge">Top 10</span>
      </div>
      <div style="height:280px"><canvas id="machChart"></canvas></div>
    </div>
  </div>

  <!-- Detail Table -->
  <div class="card">
    <div class="tbl-toolbar">
      <div>
        <div class="card-title">Transaction Detail</div>
        <div class="tbl-meta" id="tbl-meta"></div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <div class="tbl-search-wrap">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input id="tbl-srch" class="tbl-search" type="text" placeholder="Filter table by item or description…"/>
        </div>
        <button id="export-csv" class="export-btn">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export CSV
        </button>
      </div>
    </div>
    <table id="dtbl">
      <thead><tr>
        <th data-col="Item">Item #</th>
        <th data-col="Description">Description</th>
        <th data-col="Process">Process</th>
        <th data-col="Machine_model">Machine</th>
        <th data-col="Category">Category</th>
        <th data-col="Quantity" style="text-align:right">Qty</th>
        <th data-col="Total" style="text-align:right" class="sorted-desc">Total Cost</th>
      </tr></thead>
      <tbody id="tbl-body"></tbody>
    </table>
    <div class="pagination">
      <span class="pg-info" id="pg-info"></span>
      <div class="pg-btns" id="pg-btns"></div>
    </div>
  </div>

</div><!-- .main -->
</div><!-- .main-full -->

<div class="footer" id="footer-gen"></div>

<script>
const DATA = __DATA_JSON__;

// ── State ─────────────────────────────────────────────────────────────────────
const _M0 = DATA.filters.months;
const _defaultMonths = new Set(_M0.slice(Math.max(0, _M0.length - 12)));
const state = { months: _defaultMonths, process:'', category:'', search:'', tblSearch:'' };
let filtered=[], tableData=[], tablePage=0, sortCol='Total', sortAsc=false;
const PAGE = 50;

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  document.getElementById('gen-date').textContent = 'Generated ' + DATA.generated;
  document.getElementById('footer-gen').textContent =
    'Store Item Dashboard · MTHAI · ' + DATA.generated;

  // Period selector
  const M = DATA.filters.months;
  const fromSel = document.getElementById('from-month');
  const toSel   = document.getElementById('to-month');
  M.forEach(m => {
    const o1 = new Option(m, m); const o2 = new Option(m, m);
    fromSel.appendChild(o1); toSel.appendChild(o2);
  });
  const toIdx   = M.length - 1;
  const fromIdx = Math.max(0, toIdx - 11);  // default: last 12 months
  fromSel.value = M[fromIdx];
  toSel.value   = M[toIdx];
  updatePeriodCount();

  fromSel.addEventListener('change', () => {
    const fi = M.indexOf(fromSel.value), ti = M.indexOf(toSel.value);
    if (fi > ti) toSel.value = fromSel.value;
    applyPeriod();
  });
  toSel.addEventListener('change', () => {
    const fi = M.indexOf(fromSel.value), ti = M.indexOf(toSel.value);
    if (ti < fi) fromSel.value = toSel.value;
    applyPeriod();
  });

  fill('proc-sel', DATA.filters.processes);
  fill('cat-sel',  DATA.filters.categories);
  document.getElementById('proc-sel').addEventListener('change', e => { state.process = e.target.value; refresh(); });
  document.getElementById('cat-sel').addEventListener('change',  e => { state.category = e.target.value; refresh(); });
  document.getElementById('srch').addEventListener('input', e => { state.search = e.target.value.trim().toLowerCase(); refresh(); });
  document.getElementById('tbl-srch').addEventListener('input', e => { state.tblSearch = e.target.value.trim().toLowerCase(); tablePage = 0; renderTable(); });
  document.getElementById('reset-btn').addEventListener('click', reset);
  document.getElementById('export-csv').addEventListener('click', exportCSV);

  // Table header sort
  document.querySelectorAll('#dtbl thead th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) { sortAsc = !sortAsc; }
      else { sortCol = col; sortAsc = col !== 'Total'; }
      document.querySelectorAll('#dtbl thead th').forEach(t => t.classList.remove('sorted-asc','sorted-desc'));
      th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
      tableData = doSort(filtered); tablePage = 0; renderTable();
    });
  });

  initCharts();
  refresh();
}

function fill(id, vals) {
  const sel = document.getElementById(id);
  vals.forEach(v => { const o = new Option(v, v); sel.appendChild(o); });
}

function applyPeriod() {
  const M  = DATA.filters.months;
  const fi = M.indexOf(document.getElementById('from-month').value);
  const ti = M.indexOf(document.getElementById('to-month').value);
  state.months = new Set(M.slice(Math.min(fi,ti), Math.max(fi,ti)+1));
  updatePeriodCount();
  refresh();
}

function updatePeriodCount() {
  const fi = DATA.filters.months.indexOf(document.getElementById('from-month').value);
  const ti = DATA.filters.months.indexOf(document.getElementById('to-month').value);
  const n  = Math.abs(ti - fi) + 1;
  document.getElementById('period-count').textContent = n + ' month' + (n !== 1 ? 's' : '');
}

function reset() {
  const M      = DATA.filters.months;
  const toIdx  = M.length - 1;
  const fromIdx = Math.max(0, toIdx - 11);
  document.getElementById('from-month').value = M[fromIdx];
  document.getElementById('to-month').value   = M[toIdx];
  state.months = new Set(M.slice(fromIdx, toIdx + 1));
  state.process = state.category = state.search = state.tblSearch = '';
  document.getElementById('proc-sel').value = '';
  document.getElementById('cat-sel').value  = '';
  document.getElementById('srch').value     = '';
  document.getElementById('tbl-srch').value = '';
  updatePeriodCount();
  refresh();
}

// ── Filter ────────────────────────────────────────────────────────────────────
function applyFilter() {
  return DATA.records.filter(r =>
    state.months.has(r.Month) &&
    (!state.process  || r.Process  === state.process) &&
    (!state.category || r.Category === state.category) &&
    (!state.search   || r.Item.toLowerCase().includes(state.search) ||
                        r.Description.toLowerCase().includes(state.search))
  );
}

function refresh() {
  filtered  = applyFilter();
  tableData = doSort(filtered);
  tablePage = 0;
  updateKPIs();
  updateTrend();
  updateProc();
  updateMach();
  renderTable();
}

// ── KPIs ─────────────────────────────────────────────────────────────────────
function updateKPIs() {
  const total   = filtered.reduce((s,r) => s+r.Total, 0);
  const activeM = DATA.month_order.filter(m => state.months.has(m));
  const latest  = activeM[activeM.length-1];
  const prev    = activeM.length >= 2 ? activeM[activeM.length-2] : null;
  const latC    = filtered.filter(r=>r.Month===latest).reduce((s,r)=>s+r.Total,0);
  const preC    = prev ? filtered.filter(r=>r.Month===prev).reduce((s,r)=>s+r.Total,0) : 0;
  const mom     = preC > 0 ? (latC-preC)/preC*100 : null;
  const items   = new Set(filtered.map(r=>r.Item)).size;

  set('kpi-total',     fmt(total));
  set('kpi-total-sub', activeM.length + ' month' + (activeM.length!==1?'s':'') + ' · ' + (activeM[0]||'') + (activeM.length>1?' – '+latest:''));
  set('kpi-latest',    fmt(latC));
  set('kpi-latest-sub', latest || '—');
  set('kpi-items',     items.toLocaleString());
  set('trend-total-badge', 'Total ' + fmtM(total));

  const momEl  = document.getElementById('kpi-mom');
  const momSub = document.getElementById('kpi-mom-sub');
  if (mom !== null) {
    const isUp = mom > 0;
    const badge = `<span class="kpi-badge ${isUp?'up':'dn'}">${isUp?'▲':'▼'} ${Math.abs(mom).toFixed(1)}%</span>`;
    momEl.innerHTML  = badge;
    momSub.textContent = (prev||'') + ' → ' + (latest||'');
  } else {
    momEl.innerHTML = '<span style="color:var(--muted2)">—</span>';
    momSub.textContent = 'Select 2+ months';
  }
}

// ── Charts ────────────────────────────────────────────────────────────────────
let cTrend, cProc, cMach;
Chart.register(ChartDataLabels);

const CAT_ORDER  = ['Emergency','JIT','Consumable','Consignment'];
const CAT_COLORS = {
  'Emergency':   '#C0392B',
  'JIT':         '#E67E22',
  'Consumable':  '#2E75B6',
  'Consignment': '#2D8E4E',
};

function initCharts() {
  Chart.defaults.font      = { family:"'Outfit',sans-serif", size:11 };
  Chart.defaults.color     = '#64748B';

  const dlBase = { font:{size:9.5,weight:'600',family:"'Outfit',sans-serif"}, color:'#475569', clamp:true };

  // Trend
  cTrend = new Chart(document.getElementById('trendChart'), {
    type:'bar',
    data:{ labels:[], datasets:[{ data:[], borderRadius:5 }] },
    options:{
      responsive:true, maintainAspectRatio:false,
      layout:{ padding:{ top:22 } },
      onClick(evt, elements) {
        if (!elements.length) return;
        const m   = cTrend.data.labels[elements[0].index];
        const cur = document.getElementById('from-month').value;
        const to  = document.getElementById('to-month').value;
        if (cur === m && to === m) {
          // already zoomed into this month → toggle back to default 12 months
          reset();
        } else {
          document.getElementById('from-month').value = m;
          document.getElementById('to-month').value   = m;
          applyPeriod();
        }
      },
      plugins:{
        legend:{ display:false },
        tooltip:{ callbacks:{ label: ctx => '  ' + fmt(ctx.raw) } },
        datalabels:{
          ...dlBase,
          anchor:'end', align:'top', offset:2,
          formatter: v => v > 0 ? fmtK(v) : '',
          rotation:-45,
        }
      },
      scales:{
        x:{ grid:{display:false}, ticks:{font:{size:11,weight:'500'}} },
        y:{ grid:{color:'#EEF1F5'}, ticks:{callback: v => fmtK(v)}, border:{dash:[3,3]} },
      },
      cursor:'pointer',
    }
  });
  document.getElementById('trendChart').style.cursor = 'pointer';

  // Process & Machine (horizontal bar) — indexAxis must be inside options at creation time
  const hbarOpts = () => ({
    indexAxis:'y',
    responsive:true, maintainAspectRatio:false,
    layout:{ padding:{ right:64 } },
    plugins:{
      legend:{ display:false },
      tooltip:{ callbacks:{ label: ctx => '  ' + fmt(ctx.raw) } },
      datalabels:{
        ...dlBase,
        anchor:'end', align:'end', offset:4,
        formatter: v => v > 0 ? fmtK(v) : '',
      }
    },
    scales:{
      x:{ grid:{color:'#EEF1F5'}, ticks:{callback:v=>fmtK(v)}, border:{dash:[3,3]} },
      y:{ grid:{display:false}, ticks:{font:{size:11.5}} },
    }
  });

  cProc = new Chart(document.getElementById('procChart'),{
    type:'bar',
    data:{ labels:[], datasets:[] },
    options:{
      indexAxis:'y',
      responsive:true, maintainAspectRatio:false,
      layout:{ padding:{ right:8 } },
      plugins:{
        legend:{
          display:true, position:'top',
          labels:{ font:{size:11,family:"'Outfit',sans-serif"}, boxWidth:11, boxHeight:11, padding:12 }
        },
        tooltip:{ callbacks:{ label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)}` } },
        datalabels:{ display:false },   // controlled per-dataset in updateProc
      },
      scales:{
        x:{ stacked:true, grid:{color:'#EEF1F5'}, ticks:{callback:v=>fmtK(v)}, border:{dash:[3,3]} },
        y:{ stacked:true, grid:{display:false}, ticks:{font:{size:11.5}} },
      }
    }
  });

  cMach = new Chart(document.getElementById('machChart'),{
    type:'bar',
    data:{ labels:[], datasets:[{ data:[], backgroundColor:'#E67E22', borderRadius:4 }] },
    options: hbarOpts()
  });
}

function gsum(records, key) {
  const m = {};
  for (const r of records) { const k = r[key]||'Unknown'; m[k]=(m[k]||0)+r.Total; }
  return m;
}
function topN(obj, n) { return Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n); }

function updateTrend() {
  const byM    = gsum(filtered,'Month');
  const activeM = DATA.month_order.filter(m => state.months.has(m));
  cTrend.data.labels = activeM;
  cTrend.data.datasets[0].data            = activeM.map(m => +(byM[m]||0).toFixed(2));
  cTrend.data.datasets[0].backgroundColor = '#2E75B6';
  cTrend.update();
}

function updateProc() {
  const top10 = topN(gsum(filtered,'Process'), 10).map(x => x[0]);

  // Build cost per [process][category]
  const byPC = {};
  for (const r of filtered) {
    const p = r.Process  || 'Unknown';
    const c = r.Category || 'Unknown';
    if (!top10.includes(p)) continue;
    if (!byPC[p]) byPC[p] = {};
    byPC[p][c] = (byPC[p][c] || 0) + r.Total;
  }

  // Only include categories that have data in current filter
  const activeCats = CAT_ORDER.filter(c => top10.some(p => byPC[p]?.[c]));

  // Precompute totals per process for the label on the last segment
  const procTotals = {};
  top10.forEach(p => {
    procTotals[p] = activeCats.reduce((s, c) => s + (byPC[p]?.[c] || 0), 0);
  });

  const dlCfg = { font:{size:9.5,weight:'600',family:"'Outfit',sans-serif"}, color:'#475569' };

  cProc.data.labels   = top10;
  cProc.data.datasets = activeCats.map((cat, idx) => ({
    label:           cat,
    data:            top10.map(p => +((byPC[p]?.[cat] || 0).toFixed(2))),
    backgroundColor: CAT_COLORS[cat] || '#94A3B8',
    borderWidth:     0,
    datalabels: idx === activeCats.length - 1 ? {
      ...dlCfg,
      display:   true,
      anchor:    'end',
      align:     'end',
      offset:    4,
      formatter: (_, ctx) => {
        const total = procTotals[top10[ctx.dataIndex]];
        return total > 0 ? fmtK(total) : '';
      },
    } : { display: false },
  }));
  cProc.update();
}

function updateMach() {
  const top = topN(gsum(filtered,'Machine_model'), 10);
  cMach.data.labels            = top.map(x=>x[0]);
  cMach.data.datasets[0].data  = top.map(x=>+x[1].toFixed(2));
  cMach.update();
}

// ── Table ─────────────────────────────────────────────────────────────────────
function doSort(recs) {
  return [...recs].sort((a,b) => {
    let va=a[sortCol], vb=b[sortCol];
    if (typeof va==='string'){va=va.toLowerCase();vb=vb.toLowerCase();}
    return va<vb ? (sortAsc?-1:1) : va>vb ? (sortAsc?1:-1) : 0;
  });
}

function renderTable() {
  const ts   = state.tblSearch;
  const data = ts ? tableData.filter(r =>
    r.Item.toLowerCase().includes(ts) || r.Description.toLowerCase().includes(ts)) : tableData;
  const start = tablePage * PAGE;
  const page  = data.slice(start, start+PAGE);

  document.getElementById('tbl-body').innerHTML = page.map(r => `
    <tr>
      <td class="mono">${esc(r.Item)}</td>
      <td>${esc(r.Description)}</td>
      <td><span class="ptag">${esc(r.Process)}</span></td>
      <td style="color:var(--muted)">${esc(r.Machine_model)}</td>
      <td><span class="ptag">${esc(r.Category)}</span></td>
      <td style="text-align:right;color:var(--muted)">${r.Quantity.toLocaleString()}</td>
      <td class="cost">${fmt(r.Total)}</td>
    </tr>`).join('');

  set('tbl-meta', `${data.length.toLocaleString()} records · showing ${data.length===0?0:start+1}–${Math.min(start+PAGE,data.length)}`);
  renderPag(data.length);
}

function renderPag(total) {
  const pages = Math.ceil(total/PAGE);
  const btns  = [];
  btns.push(pgBtn('‹', tablePage-1, tablePage===0));
  let s=Math.max(0,tablePage-3), e=Math.min(pages-1,s+6); s=Math.max(0,e-6);
  for(let i=s;i<=e;i++) btns.push(pgBtn(i+1,i,false,i===tablePage));
  btns.push(pgBtn('›', tablePage+1, tablePage>=pages-1));
  document.getElementById('pg-btns').innerHTML = btns.join('');
  set('pg-info', pages===0 ? 'No records' : `Page ${tablePage+1} / ${pages}`);
}

function pgBtn(label, page, disabled, active=false) {
  return `<button class="pg-btn${active?' active':''}" ${disabled?'disabled':''} onclick="goPage(${page})">${label}</button>`;
}
function goPage(p) {
  const ts    = state.tblSearch;
  const data  = ts ? tableData.filter(r=>r.Item.toLowerCase().includes(ts)||r.Description.toLowerCase().includes(ts)) : tableData;
  const pages = Math.ceil(data.length/PAGE);
  if (p<0||p>=pages) return;
  tablePage = p; renderTable();
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function set(id,v){ const el=document.getElementById(id); if(el) el.textContent=v; }
function fmt(n)   { return '$' + Math.round(n).toLocaleString('en-US'); }
function fmtK(v)  { return v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':String(Math.round(v)); }
function fmtM(v)  { return v>=1e6?(v/1e6).toFixed(2)+'M':v>=1e3?(v/1e3).toFixed(1)+'K':String(Math.round(v)); }
function esc(s)   { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Export CSV ────────────────────────────────────────────────────────────────
function exportCSV() {
  const ts   = state.tblSearch;
  const data = ts ? tableData.filter(r =>
    r.Item.toLowerCase().includes(ts) || r.Description.toLowerCase().includes(ts)
  ) : tableData;

  const headers = ['Item','Description','Process','Machine_model','Category','Month','Quantity','Total'];
  const labels  = ['Item #','Description','Process','Machine','Category','Month','Qty','Total Cost'];

  const escape = v => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g,'""')}"` : s;
  };

  const rows = [labels.join(',')];
  data.forEach(r => rows.push(headers.map(h => escape(r[h])).join(',')));

  const blob = new Blob(['﻿' + rows.join('\r\n')], { type:'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const from = document.getElementById('from-month').value.replace("'","");
  const to   = document.getElementById('to-month').value.replace("'","");
  a.href     = url;
  a.download = `store_item_${from}_${to}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== Store Item Dashboard Generator ===")
    print(f"Source: {BASE}")

    print("\n[1/4] Loading ASO 2025...")
    aso  = load_aso2025()

    print("\n[2/4] Loading SUM ISSUED ASSY files (MTHAI only)...")
    sassy = load_sum_assy()

    print("\n[3/4] Normalizing...")
    combined = pd.concat([aso, sassy], ignore_index=True)
    df = normalize(combined)
    print(f"  Total rows after normalize: {len(df)}")
    print(df.groupby(["Month","Source"], observed=True)["Total"].sum().round(0).to_string())

    print("\n[4/4] Generating HTML...")
    json_str = build_json(df)
    html = HTML_TEMPLATE.replace('__DATA_JSON__', json_str)
    OUTPUT.write_text(html, encoding='utf-8')
    print(f"\nDone → {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()