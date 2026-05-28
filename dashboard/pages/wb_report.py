"""Wire Bond — Utilization & Downtime Report by Package.

Shift-based view (Day 07:00-19:00 / Night 19:00-07:00).
Filters: date → package. Shows per-machine breakdown with
wait/repair time split and inline event pills.
"""
from datetime import datetime, timedelta, date as _date

import dash
from dash import html, dcc, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc

from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, TEAL, PURPLE,
    MED_GRAY, DARK_GRAY, LIGHT_GRAY, WHITE, DARK_TEXT, BG_GRAY,
)

dash.register_page(__name__, path='/wb-report', name='WB Report')

SHIFT_MIN = 720  # 12 h × 60 min

LOST_TYPES = frozenset((
    'SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD',
    'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN',
))

_JOB_ABBR = {
    'M/C DOWN': 'DOWN', 'ENGINEERING DOWN': 'ENG↓', 'FACILITY DOWN': 'FAC↓',
    'PM': 'PM', 'SETUP': 'SETUP', 'SETUP BY OPERATOR': 'SBO',
    'CONVERT': 'CONV', 'CLEAN MOLD': 'CLEAN', 'CHANGE CAP': 'CHG CAP',
}
_JOB_PILL = {
    'M/C DOWN':          {'bg': RED,        'tx': WHITE},
    'ENGINEERING DOWN':  {'bg': '#990000',  'tx': WHITE},
    'FACILITY DOWN':     {'bg': ORANGE,     'tx': WHITE},
    'PM':                {'bg': PURPLE,     'tx': WHITE},
    'SETUP':             {'bg': LIGHT_BLUE, 'tx': WHITE},
    'SETUP BY OPERATOR': {'bg': '#17A2B8',  'tx': WHITE},
    'CONVERT':           {'bg': TEAL,       'tx': WHITE},
    'CLEAN MOLD':        {'bg': GREEN,      'tx': WHITE},
    'CHANGE CAP':        {'bg': MED_GRAY,   'tx': WHITE},
}


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _shift_window(date_str: str, shift: str):
    d = datetime.strptime(date_str, '%Y-%m-%d').date()
    if shift == 'Day':
        return (datetime(d.year, d.month, d.day, 7, 0),
                datetime(d.year, d.month, d.day, 19, 0))
    # Night of date d = previous evening 19:00 → d 07:00  (per CLAUDE.md convention)
    end = datetime(d.year, d.month, d.day, 7, 0)
    return end - timedelta(hours=12), end


def _util_color(pct):
    if pct >= 90:
        return GREEN
    if pct >= 85:
        return ORANGE
    return RED


def _fmt_min(val):
    return '—' if not val else str(int(val))


def _progress_bar(pct):
    color = _util_color(pct)
    return html.Div([
        html.Div(style={
            'width': f'{min(pct, 100):.1f}%', 'height': '10px',
            'background': color, 'borderRadius': '3px',
        }),
    ], style={
        'width': '100%', 'height': '10px',
        'background': LIGHT_GRAY, 'borderRadius': '3px',
        'minWidth': '80px', 'marginBottom': '3px',
    })


def _event_pill(ev):
    jt = (ev.get('job_type') or '').upper().strip()
    colors = _JOB_PILL.get(jt, {'bg': MED_GRAY, 'tx': WHITE})
    abbr = _JOB_ABBR.get(jt, jt[:6])
    t0, t1 = ev.get('t_start', ''), ev.get('t_end', '')
    desc = (ev.get('des_job') or '')[:30]
    dur = ev.get('dur_min', 0)
    body = f"{abbr}  {t0}–{t1}  {desc} ({dur}m)" if desc else f"{abbr}  {t0}–{t1} ({dur}m)"
    return html.Span(body, style={
        'background': colors['bg'], 'color': colors['tx'],
        'padding': '2px 8px', 'borderRadius': '4px',
        'fontSize': '11px', 'fontWeight': '600',
        'marginRight': '4px', 'marginBottom': '3px',
        'display': 'inline-block', 'whiteSpace': 'nowrap',
    })


def _chip_btn(label, value, active):
    is_alert = value == '<85%'
    bg = (RED if is_alert else PRIMARY_BLUE) if active else WHITE
    return html.Button(
        ['⚠ ', label] if is_alert else label,
        id={'type': 'wb-chip', 'value': value},
        n_clicks=0,
        style={
            'background': bg,
            'color': WHITE if active else DARK_GRAY,
            'border': f'1.5px solid {RED if is_alert else PRIMARY_BLUE}',
            'borderRadius': '16px', 'padding': '4px 14px',
            'fontSize': '12px', 'fontWeight': '700', 'cursor': 'pointer',
            'marginRight': '6px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
    )


def _chip_row(active, counts):
    defs = [
        ('ALL',   f"All ({counts.get('ALL', 0)})"),
        ('DOWN',  f"M/C Down ({counts.get('DOWN', 0)})"),
        ('SETUP', f"Setup Loss ({counts.get('SETUP', 0)})"),
        ('FULL',  f"100% Util ({counts.get('FULL', 0)})"),
        ('<85%',  f"Util < 85% ({counts.get('<85%', 0)})"),
    ]
    return html.Div([_chip_btn(lbl, val, val == active) for val, lbl in defs],
                    style={'display': 'inline-flex', 'flexWrap': 'wrap', 'gap': '4px'})


def _kpi_card(value, label, color, sub=None, card_id=None):
    extra = {'id': card_id} if card_id else {}
    return html.Div([
        html.Div(str(value), style={
            'fontSize': '32px', 'fontWeight': '800',
            'color': color, 'lineHeight': '1.1',
        }),
        html.Div(label, style={
            'fontSize': '11px', 'fontWeight': '700', 'color': DARK_GRAY,
            'marginTop': '4px', 'letterSpacing': '0.5px',
        }),
        *([html.Div(sub, style={'fontSize': '10px', 'color': MED_GRAY, 'marginTop': '2px'})]
          if sub else []),
    ], style={
        'background': WHITE, 'borderRadius': '8px', 'padding': '14px 18px',
        'borderTop': f'4px solid {color}',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.08)',
        'minWidth': '120px', 'flex': '1',
    }, **extra)


def _kpi_divider(label):
    return html.Div(label, style={
        'alignSelf': 'center', 'fontSize': '10px', 'fontWeight': '700',
        'color': MED_GRAY, 'letterSpacing': '1px',
        'borderLeft': f'2px solid {LIGHT_GRAY}', 'paddingLeft': '10px',
        'marginLeft': '4px', 'whiteSpace': 'nowrap',
    })


def _kpi_row(total, full, setup_only, down, avg_util,
             down_pct=0.0, wait_pct=0.0, setup_conv_pct=0.0, sbo_pct=0.0,
             n_tech_pkg=0, n_tech_all=0):
    uc = _util_color(avg_util)
    return [
        _kpi_card(total,          'TOTAL MACHINES',  PRIMARY_BLUE),
        _kpi_card(down,           'M/C DOWN',        RED),
        _kpi_card(f'{avg_util}%', 'AVG UTILIZATION', uc),
        _kpi_divider('SHIFT LOSS %'),
        _kpi_card(f'{down_pct:.1f}%',       '%DOWN TIME',    RED,        'M/C DOWN repair'),
        _kpi_card(f'{wait_pct:.1f}%',       '%WAIT',         ORANGE,     'All waiting for tech'),
        _kpi_card(f'{setup_conv_pct:.1f}%', '%SETUP+CONV',   LIGHT_BLUE, 'Setup / Convert'),
        _kpi_card(f'{sbo_pct:.1f}%',        '%SBO',          TEAL,       'Setup by Operator'),
        _kpi_divider('TECHS'),
        _kpi_card(f'{n_tech_pkg}/{n_tech_all}', 'TECH ON SHIFT', PURPLE, 'pkg / all WB',
                  card_id='wb-tech-kpi-card'),
    ]


def _header_bar(shift, package, date_str, time_range, n_machines):
    try:
        d_fmt = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b %Y')
    except Exception:
        d_fmt = date_str or '—'
    return [
        html.H2("Wire Bond — Utilization & Downtime Report", style={
            'color': WHITE, 'margin': '0', 'fontSize': '22px', 'fontWeight': '700'}),
        html.Div(
            f"{shift} Shift  ·  {d_fmt}  ·  {time_range}  ·  {package}  ·  {n_machines} machines",
            style={'color': 'rgba(255,255,255,0.85)', 'fontSize': '13px', 'marginTop': '4px'},
        ),
    ]


def _empty_state(msg):
    return html.Div(msg, style={
        'textAlign': 'center', 'color': MED_GRAY, 'padding': '60px', 'fontSize': '16px',
    })


def _build_table(rows, chip='ALL'):
    """Render machine rows as an HTML table, applying chip filter."""
    if chip == 'DOWN':
        rows = [r for r in rows if r['down_min'] > 0]
    elif chip == 'SETUP':
        rows = [r for r in rows if r['down_min'] == 0
                and r['setup_min'] + r['wait_setup_min'] > 0]
    elif chip == 'FULL':
        rows = [r for r in rows if r['total_loss_min'] == 0]
    elif chip == '<85%':
        rows = [r for r in rows if r['util_pct'] < 85]

    if not rows:
        return _empty_state("No machines match this filter")

    TH = {
        'padding': '10px 12px', 'textAlign': 'left', 'fontSize': '12px',
        'fontWeight': '700', 'letterSpacing': '0.5px',
        'background': PRIMARY_BLUE, 'whiteSpace': 'nowrap',
    }
    header = html.Tr([
        html.Th('#',           style={**TH, 'color': WHITE, 'width': '36px'}),
        html.Th('MACHINE',     style={**TH, 'color': WHITE}),
        html.Th('WAIT DOWN',   style={**TH, 'color': '#ffb3b3', 'textAlign': 'right'}),
        html.Th('M/C DOWN',    style={**TH, 'color': '#ff8080', 'textAlign': 'right'}),
        html.Th('WAIT SETUP',  style={**TH, 'color': '#ffd599', 'textAlign': 'right'}),
        html.Th('SETUP',       style={**TH, 'color': '#ffbe6f', 'textAlign': 'right'}),
        html.Th('TOTAL LOSS',  style={**TH, 'color': WHITE, 'textAlign': 'right'}),
        html.Th('UTILIZATION', style={**TH, 'color': WHITE, 'minWidth': '160px'}),
        html.Th('EVENTS IN SHIFT', style={**TH, 'color': WHITE}),
    ])

    TD = {'padding': '8px 12px', 'fontSize': '13px',
          'borderBottom': f'1px solid {LIGHT_GRAY}', 'verticalAlign': 'middle'}

    table_rows = []
    for i, r in enumerate(rows):
        util = r['util_pct']
        loss = r['total_loss_min']

        row_bg = '#fff0f0' if util < 85 else ('#fff8ee' if util < 90 else
                  (WHITE if i % 2 == 0 else BG_GRAY))

        # Machine name + Insight badge
        machine_cell = [html.Span(r['machine_id'],
                                  style={'fontWeight': '700', 'color': PRIMARY_BLUE})]
        if util < 85:
            machine_cell.append(html.Span('⚠ Insight', style={
                'background': '#ffebeb', 'color': RED,
                'border': f'1px solid {RED}', 'borderRadius': '4px',
                'fontSize': '10px', 'fontWeight': '700',
                'padding': '1px 6px', 'marginLeft': '8px',
            }))

        # Utilization column
        util_col = html.Div([
            _progress_bar(util),
            html.Span(f'{util:.1f}%', style={
                'fontWeight': '700', 'fontSize': '13px', 'color': _util_color(util),
            }),
        ])

        # Events column
        pills = [_event_pill(e) for e in r.get('events', [])]
        events_col = (html.Div(pills, style={'display': 'flex', 'flexWrap': 'wrap'})
                      if pills else html.Span('—', style={'color': MED_GRAY}))

        def _td_num(val, color_if_nonzero):
            c = color_if_nonzero if val else MED_GRAY
            fw = '700' if val else '400'
            return html.Td(_fmt_min(val), style={**TD, 'textAlign': 'right',
                                                  'color': c, 'fontWeight': fw})

        loss_color = RED if util < 85 else (ORANGE if loss > 0 else MED_GRAY)

        table_rows.append(html.Tr([
            html.Td(str(i + 1), style={**TD, 'color': MED_GRAY, 'fontWeight': '600'}),
            html.Td(machine_cell, style=TD),
            _td_num(r['wait_down_min'],  RED),
            _td_num(r['down_min'],       RED),
            _td_num(r['wait_setup_min'], ORANGE),
            _td_num(r['setup_min'],      ORANGE),
            html.Td(_fmt_min(loss), style={**TD, 'textAlign': 'right',
                                           'color': loss_color,
                                           'fontWeight': '700' if loss else '400'}),
            html.Td(util_col, style={**TD, 'minWidth': '160px'}),
            html.Td(events_col, style={**TD, 'maxWidth': '520px'}),
        ], style={'background': row_bg}))

    return html.Table(
        [html.Thead(header), html.Tbody(table_rows)],
        style={'width': '100%', 'borderCollapse': 'collapse',
               'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif'},
    )


# ── HTML export ───────────────────────────────────────────────────────────────

_TH = ("padding:10px 12px;text-align:left;font-size:12px;font-weight:700;"
       "letter-spacing:0.5px;white-space:nowrap;")
_TD = ("padding:8px 12px;font-size:13px;border-bottom:1px solid #e0e0e0;"
       "vertical-align:middle;")


def _ai_insight_to_html(ai_data: dict) -> str:
    """Convert stored AI text into a styled HTML section."""
    import re
    if not ai_data or not ai_data.get('text'):
        return ''
    text = ai_data['text']
    ts   = ai_data.get('ts', '')
    lang = ai_data.get('lang', 'EN')

    SECTIONS = [
        ('KEY PATTERNS',    'คีย์แพทเทิร์น',  '📊', '#0E3689', '#EEF3FF'),
        ('TOP MACHINES',    'เครื่องที่ต้องดูแล', '⚠️',  '#CC0000', '#FFF5F5'),
        ('RECOMMENDATIONS', 'คำแนะนำ',         '✅', '#2D8E4E', '#F2FBF4'),
    ]
    hdr_map = {}
    for en, th, icon, color, bg in SECTIONS:
        hdr_map[en] = (en, icon, color, bg)
        hdr_map[th] = (en, icon, color, bg)

    def _strip_md(s):
        return re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', s)

    def _bullet_html(line):
        line = _strip_md(line.lstrip('•*-– \t').strip())
        if not line:
            return ''
        # Highlight machine names
        line = re.sub(
            r'(W[/]?B\s*#\w+)',
            r'<span style="background:#0E3689;color:#fff;border-radius:3px;'
            r'padding:1px 5px;font-size:11px;font-weight:700">\1</span>',
            line, flags=re.IGNORECASE)
        # Color util %
        def _color_pct(m):
            val = float(re.sub(r'[^0-9.]', '', m.group()))
            c = '#CC0000' if val < 75 else ('#FD7F20' if val < 85 else '#5EBF33')
            return f'<span style="color:{c};font-weight:700">{m.group()}</span>'
        line = re.sub(r'\d+\.?\d*\s*%', _color_pct, line)
        return (f'<div style="display:flex;align-items:flex-start;margin-bottom:8px">'
                f'<span style="color:#0E3689;font-weight:900;font-size:14px;'
                f'margin-right:8px;flex-shrink:0;margin-top:1px">▸</span>'
                f'<span style="flex:1;line-height:1.6">{line}</span></div>')

    all_keys = '|'.join(re.escape(k) for k in hdr_map)
    parts  = re.split(rf'##\s*({all_keys})', text, flags=re.IGNORECASE)
    blocks_html = ''
    it = iter(parts)
    next(it, None)
    for raw_hdr in it:
        body = next(it, '').strip()
        meta = hdr_map.get(raw_hdr.strip().upper(), hdr_map.get(raw_hdr.strip()))
        if not meta:
            continue
        label, icon, color, bg = meta
        bullets = ''.join(_bullet_html(ln) for ln in body.split('\n'))
        blocks_html += (
            f'<div style="background:{bg};border-left:4px solid {color};'
            f'border-radius:6px;padding:12px 16px;margin-bottom:10px">'
            f'<div style="font-size:11px;font-weight:800;color:{color};'
            f'letter-spacing:.08em;border-bottom:2px solid {color};'
            f'padding-bottom:6px;margin-bottom:10px">'
            f'{icon} {label}</div>'
            f'{bullets}</div>'
        )

    if not blocks_html:
        blocks_html = f'<pre style="white-space:pre-wrap;font-size:13px">{_strip_md(text)}</pre>'

    lang_lbl = 'TH' if lang == 'TH' else 'EN'
    return (
        f'<div style="margin:0 0 16px;padding:16px 20px;background:#fff;'
        f'border:1px solid #e0e0e0;border-left:4px solid #702076;'
        f'border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.06)">'
        f'<div style="margin-bottom:12px">'
        f'<span style="font-weight:700;font-size:14px;color:#702076">🤖 AI Insight</span>'
        f'<span style="font-size:11px;color:#8a8a8a;margin-left:8px">'
        f'generated {ts} &nbsp;·&nbsp; {lang_lbl}</span></div>'
        f'{blocks_html}</div>'
    )


def _to_html_report(rows, date_str, shift, pkg_label, chip='ALL',
                    n_tech_pkg=0, n_tech_all=0, ai_data=None):
    """Return a self-contained HTML string for download."""
    if chip == 'DOWN':
        rows = [r for r in rows if r['down_min'] > 0]
    elif chip == 'SETUP':
        rows = [r for r in rows if r['down_min'] == 0
                and r['setup_min'] + r['wait_setup_min'] > 0]
    elif chip == 'FULL':
        rows = [r for r in rows if r['total_loss_min'] == 0]
    elif chip == '<85%':
        rows = [r for r in rows if r['util_pct'] < 85]

    try:
        d_fmt = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b %Y')
    except Exception:
        d_fmt = date_str or '—'

    shift_start, shift_end = _shift_window(date_str, shift)
    time_range = f"{shift_start.strftime('%H:%M')} → {shift_end.strftime('%H:%M')}"
    generated = datetime.now().strftime('%d %b %Y  %H:%M')
    n = len(rows)

    # ── KPI ──────────────────────────────────────────────────────────────────
    n_down  = sum(1 for r in rows if r['down_min'] > 0)
    n_setup = sum(1 for r in rows if r['down_min'] == 0
                  and r['setup_min'] + r['wait_setup_min'] > 0)
    n_full  = sum(1 for r in rows if r['total_loss_min'] == 0)
    avg_u   = round(sum(r['util_pct'] for r in rows) / n, 1) if n else 0.0
    uc      = '#5EBF33' if avg_u >= 90 else ('#FD7F20' if avg_u >= 85 else '#CC0000')

    fm = n * 720 or 1
    down_pct  = round(sum(r['down_min'] for r in rows) / fm * 100, 1)
    wait_pct  = round(sum(r['wait_down_min'] + r['wait_setup_min'] for r in rows) / fm * 100, 1)
    sconv_pct = round(sum(r.get('setup_conv_min', 0) for r in rows) / fm * 100, 1)
    sbo_pct   = round(sum(r.get('sbo_min', 0) for r in rows) / fm * 100, 1)


    def kpi(val, lbl, col, sub=''):
        sub_html = (f'<div style="font-size:10px;color:#999;margin-top:2px">{sub}</div>'
                    if sub else '')
        return (f'<div style="background:#fff;border-radius:8px;padding:12px 16px;'
                f'border-top:4px solid {col};box-shadow:0 2px 6px rgba(0,0,0,.08);'
                f'flex:1;min-width:110px">'
                f'<div style="font-size:28px;font-weight:800;color:{col};line-height:1.1">{val}</div>'
                f'<div style="font-size:11px;font-weight:700;color:#555;margin-top:3px;'
                f'letter-spacing:.5px">{lbl}</div>{sub_html}</div>')

    def divider(lbl):
        return (f'<div style="align-self:center;font-size:10px;font-weight:700;color:#aaa;'
                f'letter-spacing:1px;border-left:2px solid #e0e0e0;padding-left:10px;'
                f'margin-left:4px;white-space:nowrap">{lbl}</div>')

    kpis_html = (kpi(n, 'TOTAL MACHINES', '#0E3689') +
                 kpi(n_down, 'M/C DOWN', '#CC0000') +
                 kpi(f'{avg_u}%', 'AVG UTILIZATION', uc) +
                 divider('SHIFT LOSS %') +
                 kpi(f'{down_pct}%', '%DOWN TIME',   '#CC0000', 'M/C DOWN repair') +
                 kpi(f'{wait_pct}%', '%WAIT',        '#FD7F20', 'All waiting for tech') +
                 kpi(f'{sconv_pct}%', '%SETUP+CONV', '#1D9CE4', 'Setup / Convert') +
                 kpi(f'{sbo_pct}%',  '%SBO',         '#00897B', 'Setup by Operator') +
                 divider('TECHS') +
                 kpi(f'{n_tech_pkg}/{n_tech_all}', 'TECH ON SHIFT', '#702076', 'pkg / all WB'))

    # ── Table rows ────────────────────────────────────────────────────────────
    def fv(val, col):
        if not val:
            return '<span style="color:#aaa">—</span>'
        return f'<span style="color:{col};font-weight:700">{int(val)}</span>'

    def pill(ev):
        jt    = (ev.get('job_type') or '').upper().strip()
        c     = _JOB_PILL.get(jt, {'bg': '#8A8A8A', 'tx': '#fff'})
        abbr  = _JOB_ABBR.get(jt, jt[:6])
        desc  = (ev.get('des_job') or '')[:25]
        dur   = ev.get('dur_min', 0)
        body  = (f"{abbr} {ev.get('t_start','')}–{ev.get('t_end','')} "
                 f"{desc} ({dur}m)" if desc else
                 f"{abbr} {ev.get('t_start','')}–{ev.get('t_end','')} ({dur}m)")
        return (f'<span style="background:{c["bg"]};color:{c["tx"]};padding:2px 8px;'
                f'border-radius:4px;font-size:11px;font-weight:600;margin:2px;'
                f'display:inline-block;white-space:nowrap">{body}</span>')

    trs = ''
    for i, r in enumerate(rows):
        util = r['util_pct']
        loss = r['total_loss_min']
        if util < 85:
            bg = '#fff0f0'
        elif util < 90:
            bg = '#fff8ee'
        else:
            bg = '#fff' if i % 2 == 0 else '#f7f7f7'
        uc2 = '#5EBF33' if util >= 90 else ('#FD7F20' if util >= 85 else '#CC0000')
        lc  = '#CC0000' if util < 85 else ('#FD7F20' if loss > 0 else '#aaa')

        badge = (' <span style="background:#ffebeb;color:#CC0000;border:1px solid #CC0000;'
                 'border-radius:4px;font-size:10px;font-weight:700;padding:1px 5px">⚠ Insight</span>'
                 if util < 85 else '')
        bar = (f'<div style="width:100%;height:8px;background:#e0e0e0;border-radius:3px;margin-bottom:3px">'
               f'<div style="width:{min(util,100):.1f}%;height:8px;background:{uc2};border-radius:3px"></div></div>'
               f'<span style="font-weight:700;color:{uc2}">{util:.1f}%</span>')
        evs = ''.join(pill(e) for e in r.get('events', []))
        if not evs:
            evs = '<span style="color:#aaa">—</span>'

        trs += (f'<tr style="background:{bg}">'
                f'<td style="{_TD}color:#aaa;font-weight:600">{i+1}</td>'
                f'<td style="{_TD}"><strong style="color:#0E3689">{r["machine_id"]}</strong>{badge}</td>'
                f'<td style="{_TD}text-align:right">{fv(r["wait_down_min"],"#CC0000")}</td>'
                f'<td style="{_TD}text-align:right">{fv(r["down_min"],"#CC0000")}</td>'
                f'<td style="{_TD}text-align:right">{fv(r["wait_setup_min"],"#FD7F20")}</td>'
                f'<td style="{_TD}text-align:right">{fv(r["setup_min"],"#FD7F20")}</td>'
                f'<td style="{_TD}text-align:right"><span style="color:{lc};font-weight:{"700" if loss else "400"}">'
                f'{int(loss) if loss else "—"}</span></td>'
                f'<td style="{_TD}min-width:150px">{bar}</td>'
                f'<td style="{_TD}max-width:500px">{evs}</td>'
                f'</tr>\n')

    filter_label = {'DOWN': 'M/C Down', 'SETUP': 'Setup Loss Only',
                    'FULL': '100% Util', '<85%': 'Util < 85%'}.get(chip, 'All machines')

    ai_section = _ai_insight_to_html(ai_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WB Report — {d_fmt} {shift} Shift</title>
<style>
  body{{font-family:'Segoe UI',Calibri,Arial,sans-serif;margin:0;background:#f7f7f7;color:#222}}
  @media print{{body{{background:#fff}}.no-print{{display:none}}}}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0E3689 0%,#1a4a9e 100%);padding:16px 28px;color:#fff">
  <div style="font-size:20px;font-weight:700;margin-bottom:4px">Wire Bond — Utilization &amp; Downtime Report</div>
  <div style="font-size:13px;opacity:.85">{shift} Shift &nbsp;·&nbsp; {d_fmt} &nbsp;·&nbsp; {time_range} &nbsp;·&nbsp; {pkg_label} &nbsp;·&nbsp; {n} machines</div>
</div>
<div style="padding:16px 24px 8px;display:flex;gap:12px;flex-wrap:wrap">{kpis_html}</div>
<div style="padding:4px 24px 12px;font-size:12px;color:#777">
  Showing: <strong>{filter_label}</strong> &nbsp;|&nbsp; Generated: {generated} &nbsp;|&nbsp; Microchip Technology &middot; Proprietary
</div>
{f'<div style="padding:0 24px 8px">{ai_section}</div>' if ai_section else ''}
<div style="padding:0 24px 28px;overflow-x:auto">
<table style="width:100%;border-collapse:collapse;font-family:'Segoe UI',Calibri,sans-serif;font-size:13px">
<thead><tr style="background:#0E3689">
  <th style="{_TH}color:#fff;width:36px">#</th>
  <th style="{_TH}color:#fff">MACHINE</th>
  <th style="{_TH}color:#ffb3b3;text-align:right">WAIT DOWN</th>
  <th style="{_TH}color:#ff8080;text-align:right">M/C DOWN</th>
  <th style="{_TH}color:#ffd599;text-align:right">WAIT SETUP</th>
  <th style="{_TH}color:#ffbe6f;text-align:right">SETUP</th>
  <th style="{_TH}color:#fff;text-align:right">TOTAL LOSS</th>
  <th style="{_TH}color:#fff">UTILIZATION</th>
  <th style="{_TH}color:#fff">EVENTS IN SHIFT</th>
</tr></thead>
<tbody>{trs}</tbody>
</table>
</div>
</body></html>"""


# ── Layout ────────────────────────────────────────────────────────────────────
_today = _date.today().strftime('%Y-%m-%d')

layout = html.Div([
    # Dynamic header bar
    html.Div(id='wb-header-bar', children=_header_bar('—', '—', _today, '—', 0),
             style={
                 'background': f'linear-gradient(135deg, {PRIMARY_BLUE} 0%, #1a4a9e 100%)',
                 'padding': '16px 24px',
             }),

    # Filter bar
    html.Div([
        html.Div([
            # Date
            html.Div([
                html.Label("DATE", style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': DARK_GRAY,
                    'letterSpacing': '0.8px', 'display': 'block', 'marginBottom': '4px'}),
                dcc.DatePickerSingle(
                    id='wb-date-picker', date=_today,
                    display_format='D MMM YYYY',
                    style={'fontSize': '13px'},
                ),
            ], style={'marginRight': '28px'}),

            # Shift
            html.Div([
                html.Label("SHIFT", style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': DARK_GRAY,
                    'letterSpacing': '0.8px', 'display': 'block', 'marginBottom': '4px'}),
                dbc.RadioItems(
                    id='wb-shift-toggle',
                    options=[
                        {'label': '☀ Day (07:00–19:00)',  'value': 'Day'},
                        {'label': '🌙 Night (19:00–07:00)', 'value': 'Night'},
                    ],
                    value='Night', inline=True,
                    labelStyle={'marginRight': '16px', 'fontSize': '13px',
                                'fontWeight': '600', 'cursor': 'pointer'},
                ),
            ], style={'marginRight': '28px'}),

            # Package (disabled until date chosen)
            html.Div([
                html.Label("PACKAGE", style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': DARK_GRAY,
                    'letterSpacing': '0.8px', 'display': 'block', 'marginBottom': '4px'}),
                dcc.Dropdown(
                    id='wb-package-dropdown',
                    placeholder='Select Package(s)...',
                    disabled=True, clearable=True, multi=True,
                    style={'minWidth': '320px', 'fontSize': '13px'},
                ),
            ]),
        ], style={'display': 'flex', 'alignItems': 'flex-end',
                  'flexWrap': 'wrap', 'gap': '8px', 'flex': '1'}),

        # Right side: AI Insight + Export
        html.Div([
            html.Label("ACTIONS", style={
                'fontSize': '11px', 'fontWeight': '700', 'color': DARK_GRAY,
                'letterSpacing': '0.8px', 'display': 'block', 'marginBottom': '6px'}),
            html.Div([
                # Language toggle
                html.Div([
                    html.Span('Lang:', style={
                        'fontSize': '11px', 'color': MED_GRAY, 'marginRight': '5px',
                        'fontWeight': '600', 'alignSelf': 'center'}),
                    html.Button('EN', id='wb-lang-en-btn', n_clicks=0, style={
                        'background': PRIMARY_BLUE, 'color': WHITE,
                        'border': 'none', 'borderRadius': '4px 0 0 4px',
                        'padding': '4px 10px', 'fontSize': '11px', 'fontWeight': '700',
                        'cursor': 'pointer',
                    }),
                    html.Button('ภาษาไทย', id='wb-lang-th-btn', n_clicks=0, style={
                        'background': LIGHT_GRAY, 'color': DARK_TEXT,
                        'border': 'none', 'borderRadius': '0 4px 4px 0',
                        'padding': '4px 10px', 'fontSize': '11px', 'fontWeight': '700',
                        'cursor': 'pointer',
                    }),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '12px'}),
                html.Button(
                    '🤖 AI Insight',
                    id='wb-ai-btn',
                    n_clicks=0,
                    title='Analyze machines below 85% utilization',
                    style={
                        'background': PURPLE, 'color': WHITE,
                        'border': 'none', 'borderRadius': '6px',
                        'padding': '7px 16px', 'fontSize': '13px',
                        'fontWeight': '700', 'cursor': 'pointer',
                        'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                        'marginRight': '8px',
                    },
                ),
                html.Button(
                    '↓ HTML Report',
                    id='wb-export-btn',
                    n_clicks=0,
                    style={
                        'background': PRIMARY_BLUE, 'color': WHITE,
                        'border': 'none', 'borderRadius': '6px',
                        'padding': '7px 16px', 'fontSize': '13px',
                        'fontWeight': '700', 'cursor': 'pointer',
                        'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                    },
                ),
            ], style={'display': 'flex', 'alignItems': 'center'}),
        ]),
    ], style={
        'display': 'flex', 'alignItems': 'flex-end', 'justifyContent': 'space-between',
        'flexWrap': 'wrap', 'gap': '8px',
        'padding': '14px 24px', 'background': WHITE,
        'borderBottom': f'1px solid {LIGHT_GRAY}',
    }),

    # KPI row
    html.Div(id='wb-kpi-row',
             style={'padding': '16px 24px 8px', 'display': 'flex',
                    'gap': '12px', 'flexWrap': 'wrap'}),

    # AI Insight panel (hidden until triggered)
    html.Div(id='wb-ai-panel', style={'display': 'none'},
             children=[
                 dcc.Loading(type='dot', color=PURPLE, children=[
                     html.Div(id='wb-ai-output'),
                 ]),
             ]),

    # Chip filter + legend
    html.Div([
        html.Div([
            html.Span("SHOW:", style={
                'fontSize': '12px', 'fontWeight': '700', 'color': DARK_GRAY,
                'marginRight': '10px', 'letterSpacing': '0.8px'}),
            html.Div(id='wb-chip-row',
                     children=_chip_row('ALL', {})),
        ], style={'marginBottom': '8px'}),
        html.Div([
            html.Span('● M/C Down',
                      style={'color': RED,    'fontSize': '12px', 'marginRight': '16px', 'fontWeight': '600'}),
            html.Span('● Setup Loss Only',
                      style={'color': ORANGE, 'fontSize': '12px', 'marginRight': '16px', 'fontWeight': '600'}),
            html.Span('● 100% Utilization',
                      style={'color': GREEN,  'fontSize': '12px', 'marginRight': '16px', 'fontWeight': '600'}),
            html.Span('● Util < 85% (ต้องการ Insight)',
                      style={'color': RED,    'fontSize': '12px', 'fontWeight': '600'}),
        ]),
    ], style={'padding': '10px 24px', 'background': WHITE,
              'borderBottom': f'1px solid {LIGHT_GRAY}'}),

    # Machine table
    html.Div(id='wb-machine-table',
             children=_empty_state("Select a date, shift, and package to load report"),
             style={'padding': '16px 24px', 'overflowX': 'auto'}),

    # Stores + Download
    dcc.Store(id='wb-data-store', data=[]),
    dcc.Store(id='wb-chip-store', data='ALL'),
    dcc.Store(id='wb-tech-store', data={'pkg': 0, 'all': 0, 'pkg_names': [], 'all_names': []}),
    dbc.Tooltip(id='wb-tech-tooltip', target='wb-tech-kpi-card', placement='bottom',
                style={'maxWidth': '320px', 'textAlign': 'left', 'fontSize': '12px'}),
    dcc.Store(id='wb-ai-store', data=None),
    dcc.Store(id='wb-ai-lang', data='EN'),
    dcc.Download(id='wb-export-download'),
], style={'background': BG_GRAY, 'minHeight': 'calc(100vh - 52px)'})


# ── Callback 1: Date changes → reload package options ────────────────────────
@callback(
    Output('wb-package-dropdown', 'options'),
    Output('wb-package-dropdown', 'disabled'),
    Output('wb-package-dropdown', 'value'),
    Input('wb-date-picker', 'date'),
)
def load_packages(date_str):
    if not date_str:
        return [], True, None
    try:
        from db import query_df
        from utils.queries import wb_package_options
        df = query_df(wb_package_options(), {'date_val': date_str})
        pkgs = [p for p in df['package_type'].dropna().tolist() if p]
        special = [{'label': '— All Packages —', 'value': '__ALL__'}]
        if any('QFN' in p.upper() for p in pkgs):
            special.append({'label': '— All QFN —', 'value': '__QFN__'})
        opts = special + [{'label': p, 'value': p} for p in pkgs]
        return opts, False, []
    except Exception as e:
        import logging
        logging.warning(f"wb_package_options failed: {e}")
        return [], True, []


# ── Callback 2: Package selected → load data ─────────────────────────────────
@callback(
    Output('wb-header-bar', 'children'),
    Output('wb-kpi-row', 'children'),
    Output('wb-data-store', 'data'),
    Output('wb-machine-table', 'children'),
    Output('wb-chip-row', 'children'),
    Output('wb-chip-store', 'data', allow_duplicate=True),
    Output('wb-tech-store', 'data'),
    Input('wb-package-dropdown', 'value'),
    State('wb-date-picker', 'date'),
    State('wb-shift-toggle', 'value'),
    prevent_initial_call=True,
)
def load_data(package, date_str, shift):
    # package is a list (multi=True); normalise
    pkg_list = package if isinstance(package, list) else ([package] if package else [])
    if not pkg_list or not date_str:
        hdr = _header_bar('—', '—', date_str or '—', '—', 0)
        return hdr, [], [], _empty_state("Select a package to view report"), _chip_row('ALL', {}), 'ALL', {'pkg': 0, 'all': 0}
    # sentinel flags
    has_all = '__ALL__' in pkg_list
    has_qfn = '__QFN__' in pkg_list
    # real packages (non-sentinel) for error label / fallback
    pkg_set = set(p for p in pkg_list if p and not p.startswith('__'))

    shift_start, shift_end = _shift_window(date_str, shift)
    time_range = f"{shift_start.strftime('%H:%M')} → {shift_end.strftime('%H:%M')}"

    import time
    t0 = time.time()
    try:
        from db import query_df
        from utils.queries import wb_shift_report

        df = query_df(
            wb_shift_report(),
            {'shift_start': shift_start, 'shift_end': shift_end,
             'ref_date': date_str},
        )
        t1 = time.time()
        print(f"[wb_report] query {t1-t0:.2f}s — {len(df)} rows, "
              f"{df['code_machine'].nunique()} machines")

    except Exception as e:
        print(f"[wb_report] DB error: {e}")
        _lbl = 'All Packages' if has_all else ('All QFN' if has_qfn else ', '.join(sorted(pkg_set)))
        hdr = _header_bar(shift, _lbl, date_str, time_range, 0)
        return hdr, [], [], _empty_state(f"Database error — {e}"), _chip_row('ALL', {}), 'ALL', {'pkg': 0, 'all': 0}

    # ── Determine package per machine from combined result ─────────────────────
    df['code_machine'] = df['code_machine'].astype(str).str.strip()
    df['package_type'] = df['package_type'].fillna('').astype(str).str.strip()

    machine_pkg = {}
    for mid, grp in df.groupby('code_machine'):
        pkgs = grp.loc[grp['package_type'].ne('') & grp['package_type'].ne('nan'),
                       'package_type']
        if not pkgs.empty:
            machine_pkg[mid] = pkgs.iloc[-1]

    # events_df = rows that have actual shift events (job_type not null)
    events_df = df[df['job_type'].notna()].copy()
    all_ids = df['code_machine'].unique().tolist()

    # Resolve target machines based on sentinel or explicit package set
    if has_all:
        target    = sorted(machine_pkg.keys())
        pkg_label = 'All Packages'
    elif has_qfn:
        target    = sorted(m for m, p in machine_pkg.items() if 'QFN' in p.upper())
        pkg_label = 'All QFN'
    else:
        target    = sorted(m for m, p in machine_pkg.items() if p in pkg_set)
        pkg_label = (', '.join(sorted(pkg_set)) if len(pkg_set) <= 2
                     else f"{len(pkg_set)} packages")
    if not target:
        hdr = _header_bar(shift, pkg_label, date_str, time_range, 0)
        return (hdr, _kpi_row(0, 0, 0, 0, 0.0), [],
                _empty_state("No machines found for this package in the selected period"),
                _chip_row('ALL', {}), 'ALL', {'pkg': 0, 'all': 0})

    # ── Aggregate per machine ─────────────────────────────────────────────────
    machine_rows = []
    techs_down  = set()
    techs_setup = set()
    techs_conv  = set()
    _TECH_SETUP = frozenset(('SETUP',))
    _TECH_CONV  = frozenset(('CONVERT',))

    for mid in target:
        m_ev = (events_df[events_df['code_machine'] == mid].copy()
                if not events_df.empty and mid in events_df['code_machine'].values
                else None)

        wait_down = down_min = wait_setup = setup_min = 0
        setup_conv_min = sbo_min = 0  # sub-buckets within setup_min
        event_list = []

        _SETUP_CONV = frozenset(('SETUP', 'CONVERT', 'CLEAN MOLD', 'CHANGE CAP'))

        if m_ev is not None and not m_ev.empty:
            for _, ev in m_ev.iterrows():
                jt  = (ev.get('job_type') or '').upper().strip()
                wt  = int(ev.get('wait_min') or 0)
                t0  = ev.get('datex')
                ack = ev.get('date_ack')
                t1  = ev.get('date_close')

                # Repair = date_ack → date_close (fallback: total − wait)
                if ack is not None and t1 is not None and t1 > ack:
                    repair = int((t1 - ack).total_seconds() / 60)
                elif t0 is not None and t1 is not None:
                    repair = max(0, int((t1 - t0).total_seconds() / 60) - wt)
                else:
                    repair = 0

                if jt == 'M/C DOWN':
                    wait_down += wt
                    down_min  += repair
                elif jt in LOST_TYPES:
                    wait_setup += wt
                    setup_min  += repair
                    if jt == 'SETUP BY OPERATOR':
                        sbo_min += repair
                    elif jt in _SETUP_CONV:
                        setup_conv_min += repair

                tech = str(ev.get('tech_name') or '').strip()
                if tech:
                    if jt == 'M/C DOWN':
                        techs_down.add(tech)
                    elif jt in _TECH_SETUP:
                        techs_setup.add(tech)
                    elif jt in _TECH_CONV:
                        techs_conv.add(tech)

                event_list.append({
                    'job_type': ev.get('job_type', ''),
                    't_start':  t0.strftime('%H:%M') if hasattr(t0, 'strftime') else '',
                    't_end':    t1.strftime('%H:%M') if hasattr(t1, 'strftime') else '',
                    'des_job':  str(ev.get('des_job') or ''),
                    'dur_min':  wt + repair,
                    'tech':     str(ev.get('tech_name') or '').strip(),
                })

        total_loss = wait_down + down_min + wait_setup + setup_min
        util_pct   = round(max(0.0, min(100.0,
                        (SHIFT_MIN - total_loss) / SHIFT_MIN * 100)), 1)

        machine_rows.append({
            'machine_id':      mid,
            'wait_down_min':   wait_down,
            'down_min':        down_min,
            'wait_setup_min':  wait_setup,
            'setup_min':       setup_min,
            'setup_conv_min':  setup_conv_min,
            'sbo_min':         sbo_min,
            'total_loss_min':  total_loss,
            'util_pct':        util_pct,
            'events':          event_list,
        })

    # Sort: lowest util first
    machine_rows.sort(key=lambda r: r['util_pct'])

    # ── KPI counters ──────────────────────────────────────────────────────────
    n = len(machine_rows)
    n_down  = sum(1 for r in machine_rows if r['down_min'] > 0)
    n_setup = sum(1 for r in machine_rows
                  if r['down_min'] == 0 and r['setup_min'] + r['wait_setup_min'] > 0)
    n_full  = sum(1 for r in machine_rows if r['total_loss_min'] == 0)
    avg_u   = round(sum(r['util_pct'] for r in machine_rows) / n, 1) if n else 0.0

    fleet_min = n * SHIFT_MIN or 1
    down_pct       = round(sum(r['down_min']       for r in machine_rows) / fleet_min * 100, 1)
    wait_pct       = round(sum(r['wait_down_min'] + r['wait_setup_min']
                               for r in machine_rows) / fleet_min * 100, 1)
    setup_conv_pct = round(sum(r['setup_conv_min'] for r in machine_rows) / fleet_min * 100, 1)
    sbo_pct        = round(sum(r['sbo_min']        for r in machine_rows) / fleet_min * 100, 1)

    counts = {
        'ALL':  n,
        'DOWN': n_down,
        'SETUP': n_setup,
        'FULL': n_full,
        '<85%': sum(1 for r in machine_rows if r['util_pct'] < 85),
    }

    pkg_tech_names = sorted(techs_down | techs_setup | techs_conv)
    n_tech_pkg = len(pkg_tech_names)

    # All distinct techs on shift across all WB machines (not filtered by package)
    _ALL_TECH_JT = _TECH_SETUP | _TECH_CONV | {'M/C DOWN'}
    if 'tech_name' in events_df.columns:
        _mask = events_df['job_type'].str.upper().str.strip().isin(_ALL_TECH_JT)
        _t = events_df.loc[_mask, 'tech_name'].dropna()
        _t = _t[_t.astype(str).str.strip() != '']
        all_tech_names = sorted(_t.unique().tolist())
        n_tech_all = len(all_tech_names)
    else:
        all_tech_names = []
        n_tech_all = 0

    hdr   = _header_bar(shift, pkg_label, date_str, time_range, n)
    kpis  = _kpi_row(n, n_full, n_setup, n_down, avg_u,
                     down_pct, wait_pct, setup_conv_pct, sbo_pct,
                     n_tech_pkg, n_tech_all)
    table = _build_table(machine_rows, 'ALL')
    chips = _chip_row('ALL', counts)

    return hdr, kpis, machine_rows, table, chips, 'ALL', {
        'pkg': n_tech_pkg, 'all': n_tech_all,
        'pkg_names': pkg_tech_names, 'all_names': all_tech_names,
    }


# ── Callback 3: Chip click → update store ────────────────────────────────────
@callback(
    Output('wb-chip-store', 'data'),
    Input({'type': 'wb-chip', 'value': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def on_chip_click(_):
    triggered = ctx.triggered_id
    if not triggered:
        return no_update
    return triggered.get('value', 'ALL')


# ── Callback 3b: Tech tooltip ────────────────────────────────────────────────
@callback(
    Output('wb-tech-tooltip', 'children'),
    Input('wb-tech-store', 'data'),
)
def update_tech_tooltip(tc):
    if not tc:
        return "No data"
    pkg_names = tc.get('pkg_names', [])
    all_names = tc.get('all_names', [])
    n_pkg = tc.get('pkg', 0)
    n_all = tc.get('all', 0)

    # Techs only in all-WB (not in this pkg)
    pkg_set  = set(pkg_names)
    rest     = sorted(n for n in all_names if n not in pkg_set)

    def _name_list(names, color):
        if not names:
            return html.Span("—", style={'color': MED_GRAY})
        return html.Div([
            html.Span(n, style={
                'display': 'inline-block', 'background': color,
                'color': WHITE, 'borderRadius': '3px',
                'padding': '1px 6px', 'margin': '2px 2px',
                'fontSize': '11px', 'fontWeight': '600',
            }) for n in names
        ])

    return html.Div([
        html.Div([
            html.Strong(f"Package ({n_pkg})", style={'color': PRIMARY_BLUE, 'fontSize': '11px'}),
            html.Span(" — M/C DOWN · SETUP · CONVERT",
                      style={'color': MED_GRAY, 'fontSize': '10px', 'marginLeft': '4px'}),
        ], style={'marginBottom': '4px'}),
        _name_list(pkg_names, PRIMARY_BLUE),
        html.Hr(style={'margin': '8px 0', 'borderColor': LIGHT_GRAY}),
        html.Div([
            html.Strong(f"Other WB ({len(rest)})", style={'color': MED_GRAY, 'fontSize': '11px'}),
            html.Span(" — same job types, other packages",
                      style={'color': MED_GRAY, 'fontSize': '10px', 'marginLeft': '4px'}),
        ], style={'marginBottom': '4px'}),
        _name_list(rest, MED_GRAY),
    ], style={'padding': '6px 2px'})


# ── Callback 4: Chip store changes → filter table ────────────────────────────
@callback(
    Output('wb-machine-table', 'children', allow_duplicate=True),
    Output('wb-chip-row', 'children', allow_duplicate=True),
    Input('wb-chip-store', 'data'),
    State('wb-data-store', 'data'),
    prevent_initial_call=True,
)
def filter_table(chip, store):
    if not store:
        return no_update, no_update
    chip = chip or 'ALL'
    counts = {
        'ALL':  len(store),
        'DOWN': sum(1 for r in store if r['down_min'] > 0),
        'SETUP': sum(1 for r in store
                     if r['down_min'] == 0 and r['setup_min'] + r['wait_setup_min'] > 0),
        'FULL': sum(1 for r in store if r['total_loss_min'] == 0),
        '<85%': sum(1 for r in store if r['util_pct'] < 85),
    }
    return _build_table(store, chip), _chip_row(chip, counts)


# ── Callback 5: Export HTML report ───────────────────────────────────────────
@callback(
    Output('wb-export-download', 'data'),
    Input('wb-export-btn', 'n_clicks'),
    State('wb-data-store', 'data'),
    State('wb-date-picker', 'date'),
    State('wb-shift-toggle', 'value'),
    State('wb-package-dropdown', 'value'),
    State('wb-chip-store', 'data'),
    State('wb-tech-store', 'data'),
    State('wb-ai-store', 'data'),
    prevent_initial_call=True,
)
def export_html(n_clicks, store, date_str, shift, package, chip, tech_counts, ai_data):
    if not store or not date_str:
        return no_update

    pkg_list  = package if isinstance(package, list) else ([package] if package else [])
    pkg_label = (', '.join(sorted(pkg_list)) if len(pkg_list) <= 2
                 else f"{len(pkg_list)} packages")
    chip      = chip or 'ALL'
    tc        = tech_counts or {'pkg': 0, 'all': 0}

    html_str  = _to_html_report(list(store), date_str, shift or 'Night',
                                 pkg_label, chip,
                                 n_tech_pkg=tc.get('pkg', 0),
                                 n_tech_all=tc.get('all', 0),
                                 ai_data=ai_data)
    filename  = f"wb_report_{date_str}_{shift or 'Night'}.html"
    return dcc.send_string(html_str, filename=filename)


# ── Callback 6a: Language toggle ─────────────────────────────────────────────
_LANG_ACTIVE   = {'background': PRIMARY_BLUE, 'color': WHITE,   'border': 'none',
                  'borderRadius': '4px 0 0 4px', 'padding': '4px 10px',
                  'fontSize': '11px', 'fontWeight': '700', 'cursor': 'pointer'}
_LANG_INACTIVE = {'background': LIGHT_GRAY,   'color': DARK_TEXT, 'border': 'none',
                  'borderRadius': '4px 0 0 4px', 'padding': '4px 10px',
                  'fontSize': '11px', 'fontWeight': '700', 'cursor': 'pointer'}

@callback(
    Output('wb-ai-lang', 'data'),
    Output('wb-lang-en-btn', 'style'),
    Output('wb-lang-th-btn', 'style'),
    Input('wb-lang-en-btn', 'n_clicks'),
    Input('wb-lang-th-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def toggle_lang(n_en, n_th):
    lang = 'TH' if ctx.triggered_id == 'wb-lang-th-btn' else 'EN'
    en_s = {**_LANG_ACTIVE,   'borderRadius': '4px 0 0 4px'}
    th_s = {**_LANG_INACTIVE, 'borderRadius': '0 4px 4px 0'}
    if lang == 'TH':
        en_s = {**_LANG_INACTIVE, 'borderRadius': '4px 0 0 4px'}
        th_s = {**_LANG_ACTIVE,   'borderRadius': '0 4px 4px 0'}
    return lang, en_s, th_s


# ── Callback 6: AI Insight analysis ──────────────────────────────────────────
_PANEL_SHOW = {
    'display': 'block',
    'margin': '0 24px 0',
    'padding': '16px 20px',
    'background': WHITE,
    'border': f'1px solid {LIGHT_GRAY}',
    'borderLeft': f'4px solid {PURPLE}',
    'borderRadius': '8px',
    'boxShadow': '0 2px 8px rgba(0,0,0,0.06)',
    'marginBottom': '4px',
}
_PANEL_HIDE = {'display': 'none'}


def _build_ai_prompt(rows_low, n_total, date_str, shift, pkg_label, lang='EN'):
    try:
        d_fmt = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b %Y')
    except Exception:
        d_fmt = date_str

    lines = [
        "You are a Wire Bond manufacturing maintenance analyst.",
        "Analyze the following shift utilization data and provide actionable insights.",
        "",
        f"Date: {d_fmt}  |  Shift: {shift}  |  Package: {pkg_label}",
        f"Fleet: {n_total} machines total  |  Below 85%: {len(rows_low)} machines",
        "",
        "MACHINES BELOW 85% UTILIZATION (sorted by utilization, worst first):",
        "",
    ]
    for r in rows_low:
        mid       = r.get('machine_id', '?')
        util      = r.get('util_pct', 0)
        loss      = r.get('total_loss_min', 0)
        down      = r.get('down_min', 0)
        wait_d    = r.get('wait_down_min', 0)
        setup     = r.get('setup_min', 0)
        wait_s    = r.get('wait_setup_min', 0)
        events    = r.get('events', [])
        lines.append(f"{mid}  —  {util}% util  ({loss}min lost / 720min shift)")
        if down or wait_d:
            lines.append(f"  Repair: {down}min  |  Wait-for-tech: {wait_d}min")
        if setup or wait_s:
            lines.append(f"  Setup/Convert: {setup}min  |  Wait-setup: {wait_s}min")
        if events:
            ev_summary = ',  '.join(
                f"{e.get('job_type','?')} {e.get('t_start','')}–{e.get('t_end','')} ({e.get('dur_min',0)}m)"
                + (f" [{e.get('des_job','')}]" if e.get('des_job') else '')
                for e in events[:6]
            )
            lines.append(f"  Events: {ev_summary}")
        lines.append("")

    lang_instruction = (
        "ตอบเป็นภาษาไทย สำหรับทีม Maintenance และวิศวกร Wire Bond\n"
        "กฎการใช้ภาษา:\n"
        "- คำเทคนิคต่อไปนี้ให้ใช้ภาษาอังกฤษเสมอ (ห้ามแปล): "
        "Machine Down, Setup, Convert, Utilization, Technician, Wait-for-tech, "
        "Cratering, Calibration, PM, SBO, NSOP, PRS Error, VLL Error, "
        "Ball Size, Tail Too Short, Wire Bond, Shift, Repair, Parameter, "
        "ชื่อ Error Code ทุกชนิด, ชื่อกระบวนการทุกชนิด\n"
        "- ชื่อเครื่อง (W/B #xxx) ให้คงไว้ตามเดิม\n"
        "- ตัวเลข % และเวลา (นาที) ให้แสดงตัวเลขตามเดิม\n"
        "- ใช้ภาษาไทยสำหรับคำวิเคราะห์ คำอธิบาย และคำแนะนำเท่านั้น\n"
        "- เขียนให้กระชับ ตรงประเด็น เหมือนรายงานทางเทคนิค"
        if lang == 'TH' else
        "Respond in English."
    )
    lines += [
        f"Language: {lang_instruction}",
        "",
        "Please provide exactly 3 sections using these EXACT headers (## prefix required):",
        "",
        "## KEY PATTERNS",
        "2-3 bullet points (•) on what types of loss dominate and why",
        "",
        "## TOP MACHINES",
        "Top 3 machines needing immediate attention — one bullet per machine,",
        "format: • MachineName (util%) — reason and recommended action",
        "",
        "## RECOMMENDATIONS",
        "3-5 concrete action bullets for the maintenance team next shift",
        "",
        "Rules: bullet points only (•), concise and actionable. No other markdown.",
    ]
    return "\n".join(lines)


def _render_ai_text(text: str):
    """Parse ## section AI output into styled card components."""
    import re

    SECTION_META = [
        ('KEY PATTERNS',    'คีย์แพทเทิร์น',  '📊', PRIMARY_BLUE, '#EEF3FF'),
        ('TOP MACHINES',    'เครื่องที่ต้องดูแล', '⚠️',  RED,          '#FFF5F5'),
        ('RECOMMENDATIONS', 'คำแนะนำ',         '✅', GREEN,        '#F2FBF4'),
    ]
    # Map both EN and TH header names to meta
    _HDR_MAP = {}
    for en, th, icon, accent, bg in SECTION_META:
        _HDR_MAP[en]  = (en, icon, accent, bg)
        _HDR_MAP[th]  = (en, icon, accent, bg)

    def _strip_md(s):
        # Remove **bold** and *italic* markers, keep the text
        return re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', s)

    def _bullet(line: str):
        line = _strip_md(line.lstrip('•*-– \t').strip())
        if not line:
            return None
        # Highlight machine names  W/B #339L  or  WB#339L  or  W/B#339L
        parts = re.split(r'(W[/]?B\s*#\w+)', line, flags=re.IGNORECASE)
        children = []
        for p in parts:
            if re.match(r'W[/]?B\s*#\w+', p, flags=re.IGNORECASE):
                children.append(html.Span(p, style={
                    'background': PRIMARY_BLUE, 'color': WHITE,
                    'borderRadius': '4px', 'padding': '1px 6px',
                    'fontSize': '11px', 'fontWeight': '700', 'marginRight': '2px',
                }))
            else:
                # Color util %
                subs = re.split(r'(\d+\.?\d*\s*%)', p)
                for s in subs:
                    if re.match(r'\d+\.?\d*\s*%', s):
                        try:
                            pct = float(re.sub(r'[^0-9.]', '', s))
                            c = RED if pct < 75 else (ORANGE if pct < 85 else GREEN)
                        except ValueError:
                            c = DARK_TEXT
                        children.append(html.Span(s, style={'color': c, 'fontWeight': '700'}))
                    else:
                        children.append(s)
        return html.Div([
            html.Span('▸', style={
                'color': PRIMARY_BLUE, 'fontWeight': '900', 'fontSize': '14px',
                'marginRight': '8px', 'flexShrink': '0', 'marginTop': '2px'}),
            html.Span(children, style={'flex': '1'}),
        ], style={
            'display': 'flex', 'alignItems': 'flex-start',
            'marginBottom': '9px', 'fontSize': '13px',
            'lineHeight': '1.65', 'color': DARK_TEXT,
        })

    # Split on ## headers (EN or TH, case-insensitive)
    all_headers = '|'.join(re.escape(k) for k in _HDR_MAP)
    sections = re.split(rf'##\s*({all_headers})', text, flags=re.IGNORECASE)

    blocks = []
    it = iter(sections)
    next(it, None)  # skip pre-header text
    for raw_header in it:
        body = next(it, '').strip()
        meta = _HDR_MAP.get(raw_header.strip().upper(),
                _HDR_MAP.get(raw_header.strip(), None))
        if meta is None:
            continue
        label, icon, accent, bg = meta
        bullets = [_bullet(ln) for ln in body.split('\n')]
        bullets = [b for b in bullets if b is not None]
        blocks.append(html.Div([
            html.Div([
                html.Span(icon, style={'marginRight': '7px', 'fontSize': '14px'}),
                html.Span(label, style={
                    'fontWeight': '800', 'fontSize': '11px',
                    'letterSpacing': '0.08em', 'color': accent,
                }),
            ], style={
                'marginBottom': '10px', 'paddingBottom': '7px',
                'borderBottom': f'2px solid {accent}', 'opacity': '0.9',
            }),
            html.Div(bullets),
        ], style={
            'background': bg, 'borderLeft': f'4px solid {accent}',
            'borderRadius': '8px', 'padding': '14px 18px', 'marginBottom': '10px',
        }))

    if not blocks:
        return html.Pre(_strip_md(text), style={
            'fontFamily': 'inherit', 'fontSize': '13px',
            'lineHeight': '1.7', 'whiteSpace': 'pre-wrap', 'margin': 0,
        })
    return html.Div(blocks)


@callback(
    Output('wb-ai-output', 'children'),
    Output('wb-ai-panel', 'style'),
    Output('wb-ai-store', 'data'),
    Input('wb-ai-btn', 'n_clicks'),
    State('wb-data-store', 'data'),
    State('wb-date-picker', 'date'),
    State('wb-shift-toggle', 'value'),
    State('wb-package-dropdown', 'value'),
    State('wb-ai-lang', 'data'),
    prevent_initial_call=True,
)
def run_ai_insight(n_clicks, store, date_str, shift, package, lang):
    import os
    from datetime import datetime as _dt

    def _panel(content, ai_text=None):
        ts = _dt.now().strftime('%H:%M:%S')
        return (
            html.Div([
                html.Div([
                    html.Span('🤖 AI Insight', style={
                        'fontWeight': '700', 'fontSize': '14px', 'color': PURPLE}),
                    html.Span(f' — {date_str}  {shift or ""}  |  generated {ts}',
                              style={'fontSize': '12px', 'color': MED_GRAY, 'marginLeft': '8px'}),
                ], style={'marginBottom': '10px'}),
                content,
            ]),
            _PANEL_SHOW,
            {'text': ai_text, 'lang': lang or 'EN', 'ts': ts,
             'date': date_str, 'shift': shift} if ai_text else None,
        )

    if not store or not date_str:
        return _panel(html.Div("No data loaded — select a date, shift, and package first.",
                               style={'color': MED_GRAY, 'fontSize': '13px'}))

    rows_low = sorted(
        [r for r in store if isinstance(r, dict) and r.get('util_pct', 100) < 85],
        key=lambda r: r.get('util_pct', 100)
    )[:30]

    if not rows_low:
        return _panel(html.Div(
            "✅ No machines below 85% utilization in this shift.",
            style={'color': GREEN, 'fontWeight': '600', 'fontSize': '13px'}))

    # Check credentials — SDK will auto-read ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL from env
    auth_token = os.getenv('ANTHROPIC_AUTH_TOKEN', os.getenv('ANTHROPIC_API_KEY', ''))
    if not auth_token:
        return _panel(html.Div(
            "⚠️ ANTHROPIC_AUTH_TOKEN not set in .env",
            style={'color': ORANGE, 'fontWeight': '600', 'fontSize': '13px'}))

    pkg_list  = package if isinstance(package, list) else ([package] if package else [])
    real_pkgs = [p for p in pkg_list if p and not p.startswith('__')]
    if '__ALL__' in pkg_list:
        pkg_label = 'All Packages'
    elif '__QFN__' in pkg_list:
        pkg_label = 'All QFN'
    elif len(real_pkgs) <= 2:
        pkg_label = ', '.join(sorted(real_pkgs)) or '—'
    else:
        pkg_label = f"{len(real_pkgs)} packages"

    lang   = lang or 'EN'
    prompt = _build_ai_prompt(rows_low, len(store), date_str, shift or 'Night', pkg_label, lang)
    model  = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')

    try:
        import anthropic, httpx
        # Microchip internal CA not in Python's cert bundle → disable SSL verify for pedro proxy
        client = anthropic.Anthropic(
            http_client=httpx.Client(verify=False)
        )  # auto-reads ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = msg.content[0].text.strip()
        return _panel(_render_ai_text(text), ai_text=text)
    except Exception as e:
        return _panel(html.Div(
            f"❌ AI error: {e}",
            style={'color': RED, 'fontSize': '13px', 'fontWeight': '600'}))
