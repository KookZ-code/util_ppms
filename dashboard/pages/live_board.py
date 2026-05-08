"""Live Production Board — shop-floor TV dashboard.

Grid of machine tiles colored by status. Auto-refreshes every 30s.
Designed for wall-mount TV in production area: large text, high contrast,
tap-to-filter, zero drilldown. Complements Overview (business-KPI style).
"""
from datetime import datetime, timedelta
import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd

from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, YELLOW, PURPLE,
    MED_GRAY, DARK_GRAY, LIGHT_GRAY, WHITE, DARK_TEXT, BG_GRAY,
)

dash.register_page(__name__, path='/live', name='Live Board')


# ── Status colors (tiles) ─────────────────────────────────────────────────────
STATUS_STYLES = {
    'Running':      {'bg': GREEN,      'text': WHITE, 'icon': 'OK'},
    'M/C DOWN':     {'bg': RED,        'text': WHITE, 'icon': 'X'},
    'Setup':        {'bg': ORANGE,     'text': WHITE, 'icon': '~'},
    'PM':           {'bg': PURPLE,     'text': WHITE, 'icon': 'PM'},
    'Waiting':      {'bg': YELLOW,     'text': DARK_TEXT, 'icon': '!'},
    'Unknown':      {'bg': LIGHT_GRAY, 'text': DARK_GRAY, 'icon': '?'},
}

# Thresholds for alert banners
ALERT_DOWN_THRESHOLD = 5        # N machines M/C DOWN in same area
ALERT_WAIT_MIN_THRESHOLD = 30   # waiting > N minutes with no tech
ALERT_WAIT_COUNT_THRESHOLD = 3  # N waiting jobs simultaneously


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    # Local 60s auto-refresh (separate from the global 5-min interval)
    dcc.Interval(id='live-refresh', interval=60_000, n_intervals=0),

    # Page header (custom — bigger than standard, bold)
    html.Div([
        html.Div([
            html.H1("LIVE PRODUCTION BOARD", style={
                'color': WHITE, 'margin': '0', 'fontSize': '28px',
                'fontWeight': '700', 'letterSpacing': '1px'}),
            html.Div(id='live-subheader', style={
                'color': 'rgba(255,255,255,0.85)', 'fontSize': '14px',
                'marginTop': '4px'}),
        ]),
        html.Div(id='live-clock', style={
            'color': WHITE, 'fontSize': '32px', 'fontWeight': '700',
            'fontFamily': 'Consolas, Monaco, monospace',
            'textShadow': '0 2px 4px rgba(0,0,0,0.3)'}),
    ], style={
        'background': f'linear-gradient(135deg, {PRIMARY_BLUE} 0%, #1a4a9e 100%)',
        'padding': '16px 24px', 'display': 'flex',
        'justifyContent': 'space-between', 'alignItems': 'center',
    }),

    # Alert banner (hidden unless active)
    html.Div(id='live-alert', style={'padding': '0 24px'}),

    # Filters row
    html.Div([
        html.Div([
            html.Span("AREA:", style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': DARK_GRAY, 'marginRight': '10px',
                'letterSpacing': '1px'}),
            html.Div(id='live-area-chips', style={'display': 'inline-block'}),
        ], style={'marginBottom': '8px'}),
        html.Div([
            html.Span("STATUS:", style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': DARK_GRAY, 'marginRight': '10px',
                'letterSpacing': '1px'}),
            dbc.Checklist(
                id='live-status-filter',
                options=[
                    {'label': 'M/C DOWN', 'value': 'M/C DOWN'},
                    {'label': 'Setup',    'value': 'Setup'},
                    {'label': 'Waiting',  'value': 'Waiting'},
                    {'label': 'Running',  'value': 'Running'},
                    {'label': 'PM',       'value': 'PM'},
                ],
                # Default: problem states only — user can check Running/PM
                # to see the whole fleet.
                value=['M/C DOWN', 'Setup', 'Waiting'],
                inline=True,
                labelStyle={'marginRight': '14px', 'fontSize': '13px',
                            'fontWeight': '600', 'cursor': 'pointer'},
            ),
        ]),
    ], style={'padding': '12px 24px', 'background': WHITE,
              'borderBottom': f'1px solid {LIGHT_GRAY}'}),

    # Store for the area filter value
    dcc.Store(id='live-area-store', data=[]),

    # Summary line (above tile grid)
    html.Div(id='live-grid-summary', style={
        'padding': '10px 24px 4px', 'fontSize': '13px',
        'color': DARK_GRAY, 'fontWeight': '500',
    }),

    # Tile grid
    html.Div(id='live-tile-grid', style={'padding': '8px 20px 16px'}),

    # Summary bar (bottom)
    html.Div(id='live-summary', style={
        'background': PRIMARY_BLUE, 'color': WHITE, 'padding': '12px 24px',
        'fontSize': '15px', 'fontWeight': '600', 'textAlign': 'center',
        'letterSpacing': '0.5px',
        'position': 'sticky', 'bottom': '0', 'zIndex': '10',
    }),
], style={'background': BG_GRAY, 'minHeight': 'calc(100vh - 52px)'})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _current_shift():
    """Return (shift_name, time_remaining_minutes)."""
    now = datetime.now()
    if 7 <= now.hour < 19:
        end = now.replace(hour=19, minute=0, second=0, microsecond=0)
        return 'Day', int((end - now).total_seconds() / 60)
    else:
        if now.hour >= 19:
            end = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        else:
            end = now.replace(hour=7, minute=0, second=0, microsecond=0)
        return 'Night', int((end - now).total_seconds() / 60)


def _classify_job(job_type: str, status: str) -> str:
    """Map (job_type, status) → display status key."""
    if status == 'Waiting':
        return 'Waiting'
    jt = (job_type or '').upper()
    if jt == 'M/C DOWN':
        return 'M/C DOWN'
    if jt == 'PM':
        return 'PM'
    # Setup bucket covers all lost-time job types (matches LOST_TYPES
    # in utilization page + api): SETUP variants, CONVERT, CLEAN MOLD,
    # CHANGE CAP, FACILITY DOWN, ENGINEERING DOWN
    if any(k in jt for k in ('SETUP', 'CONVERT', 'CHANGE', 'CLEAN',
                              'FACILITY', 'ENGINEERING')):
        return 'Setup'
    return 'Unknown'


def _make_tile(machine_id: str, status_key: str, sub_lines: list) -> html.Div:
    """Render one machine tile."""
    style_def = STATUS_STYLES.get(status_key, STATUS_STYLES['Unknown'])
    return html.Div([
        html.Div([
            html.Div(style_def['icon'], style={
                'fontSize': '11px', 'fontWeight': '700',
                'opacity': '0.85', 'letterSpacing': '0.5px'}),
            html.Div(machine_id, style={
                'fontSize': '15px', 'fontWeight': '700',
                'marginTop': '2px', 'lineHeight': '1.15',
                'wordBreak': 'break-word'}),
        ], style={'marginBottom': '6px'}),
        html.Div(status_key.upper(), style={
            'fontSize': '11px', 'fontWeight': '700',
            'letterSpacing': '0.5px', 'opacity': '0.95',
            'marginBottom': '4px'}),
        *[
            html.Div(line, style={
                'fontSize': '11px', 'opacity': '0.9',
                'marginTop': '2px', 'lineHeight': '1.2'})
            for line in sub_lines if line
        ],
    ], style={
        'background': style_def['bg'], 'color': style_def['text'],
        'padding': '10px 12px', 'borderRadius': '8px',
        'minHeight': '100px', 'boxShadow': '0 2px 6px rgba(0,0,0,0.12)',
        'display': 'flex', 'flexDirection': 'column',
        'justifyContent': 'flex-start',
    })


def _make_area_chips(all_areas, selected):
    """Render tappable area filter chips."""
    chips = []
    # ALL chip
    all_active = not selected
    chips.append(html.Button('ALL', id={'type': 'live-area-chip', 'area': '__ALL__'},
                             n_clicks=0, style=_chip_style(all_active)))
    for area in all_areas:
        active = area in selected
        chips.append(html.Button(area, id={'type': 'live-area-chip', 'area': area},
                                 n_clicks=0, style=_chip_style(active)))
    return chips


def _chip_style(active: bool) -> dict:
    return {
        'background': PRIMARY_BLUE if active else WHITE,
        'color': WHITE if active else DARK_GRAY,
        'border': f'1.5px solid {PRIMARY_BLUE if active else LIGHT_GRAY}',
        'borderRadius': '16px', 'padding': '4px 14px',
        'fontSize': '12px', 'fontWeight': '700',
        'cursor': 'pointer', 'marginRight': '6px',
        'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        'letterSpacing': '0.3px',
        'transition': 'all 0.15s',
    }


# ── Main callback ─────────────────────────────────────────────────────────────
ALL_STATUSES = ('M/C DOWN', 'Setup', 'Waiting', 'Running', 'PM')


@callback(
    Output('live-clock', 'children'),
    Output('live-subheader', 'children'),
    Output('live-alert', 'children'),
    Output('live-grid-summary', 'children'),
    Output('live-tile-grid', 'children'),
    Output('live-summary', 'children'),
    Output('live-area-chips', 'children'),
    Input('live-refresh', 'n_intervals'),
    Input('live-area-store', 'data'),
    Input('live-status-filter', 'value'),
)
def update_board(n_intervals, selected_areas, status_filter):
    status_filter = list(status_filter) if status_filter else []
    # ── Data sources ──────────────────────────────────────────────────────────
    machines_df = pd.DataFrame()
    open_df = pd.DataFrame()
    areas = []

    try:
        from api_client import USE_API
        if USE_API:
            from api_client import (fetch_inventory_machines, fetch_open_jobs,
                                     fetch_areas)
            machines_df = fetch_inventory_machines()
            open_df = fetch_open_jobs(selected_areas, 'ALL')
            areas_data = fetch_areas()
            # Sort by MACHINE_AREAS (process-flow order) not alphabetical —
            # matches the Overview page toggle ordering.
            from config import MACHINE_AREAS as _MA
            _area_set = {a['area'] for a in areas_data if a.get('area')}
            _order = {a: i for i, a in enumerate(_MA)}
            areas = sorted(_area_set, key=lambda a: _order.get(a, 999))
    except Exception as e:
        import logging
        logging.warning(f"LPB API fetch failed: {e}")

    # Fallback to direct DB if API unavailable
    if machines_df.empty:
        try:
            from db import query_df
            from utils.queries import inventory_all_machines
            machines_df = query_df(inventory_all_machines())
            # SQL Server bit columns come back as string/object — normalize to
            # int so downstream `== 1` comparisons match (same pattern as
            # inventory.py:_load_machines).
            if 'flag_key' in machines_df.columns:
                machines_df['flag_key'] = (pd.to_numeric(machines_df['flag_key'],
                                                        errors='coerce')
                                           .fillna(0).astype(int))
                machines_df = machines_df[machines_df['flag_key'] == 1]
        except Exception as e:
            import logging
            logging.warning(f"LPB machines fallback failed: {e}")

    # Fallback for open jobs when API is unavailable. Without this, all tiles
    # would render as 'Running' because open_by_machine stays empty.
    if open_df.empty:
        try:
            from db import query_df
            from utils.queries import overview_open_jobs
            open_df = query_df(overview_open_jobs())
            if selected_areas:
                open_df = open_df[open_df['area'].isin(selected_areas)]
            # Merge Oracle ISO/FS open jobs so ISO/FS tiles show correct status
            from config import ORA_ENABLED
            if ORA_ENABLED:
                from oracle_db import fetch_oracle_live_status
                ora_live = fetch_oracle_live_status(selected_areas)
                if ora_live is not None:
                    ora_open = ora_live[ora_live['status'] != 'Closed'].copy()
                    if not ora_open.empty:
                        open_df = pd.concat([open_df, ora_open],
                                            ignore_index=True)
        except Exception as e:
            import logging
            logging.warning(f"LPB open-jobs fallback failed: {e}")

    if machines_df.empty:
        err = html.Div("Unable to load machine data", style={
            'padding': '40px', 'textAlign': 'center',
            'color': RED, 'fontSize': '18px'})
        return ('', '', '', '', err, '', [])

    # Only key machines + non-deleted
    machines_df = machines_df[machines_df.get('flag_key', 0) == 1].copy()
    machines_df['code_machine'] = machines_df['code_machine'].astype(str).str.strip()

    # ── Replace inventory rows for Oracle-only areas with Oracle-named rows.
    # dbo.machine names FS/ISO machines (e.g. "F/S# 01") differently from
    # Oracle live status (e.g. "SIN#019"), so open-jobs lookups would never
    # match and the alert banner could disagree with the tile grid. For
    # ISO/FS tiles, use the unique machine_ids seen in the Oracle background
    # store instead.
    ORACLE_ONLY = {'ISO', 'FS'}
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import _ensure_loaded, _store, _lock
            _ensure_loaded()
            with _lock:
                ora_df = _store.get('df')
            if ora_df is not None and not ora_df.empty:
                ora_sub = ora_df[ora_df['area'].isin(ORACLE_ONLY)]
                ora_keys = (ora_sub.groupby('area')['machine_id']
                            .unique().to_dict())
                rows = []
                for a, mids in ora_keys.items():
                    for m in mids:
                        if m is None or not str(m).strip():
                            continue
                        rows.append({'code_machine': str(m).strip(),
                                     'id_operation': a, 'flag_key': 1})
                if rows:
                    # Drop inventory-based rows for those Oracle-only areas
                    machines_df = machines_df[
                        ~machines_df['id_operation'].isin(ORACLE_ONLY)]
                    machines_df = pd.concat(
                        [machines_df, pd.DataFrame(rows)], ignore_index=True)
    except Exception as e:
        import logging
        logging.warning(f"LPB Oracle machine master load failed: {e}")

    # Populate `areas` chip list from machines_df when the API path didn't
    # fill it (DB-fallback path). Preserves MACHINE_AREAS process-flow order.
    if not areas and not machines_df.empty:
        from config import MACHINE_AREAS as _MA
        _order = {a: i for i, a in enumerate(_MA)}
        _area_set = set(
            machines_df['id_operation'].dropna().astype(str).str.strip().unique()
        )
        _area_set.discard('')
        areas = sorted(_area_set, key=lambda a: _order.get(a, 999))

    # ── Build tile data ───────────────────────────────────────────────────────
    # Group open_df by machine_id to find the most-severe active job per machine
    open_by_machine = {}
    if not open_df.empty:
        for _, r in open_df.iterrows():
            m = str(r.get('code_machine') or '').strip()
            if not m:
                continue
            sev_key = _classify_job(r.get('job_type'), r.get('status'))
            # Severity ranking: Down > Waiting > Setup > PM > Running
            sev_rank = {'M/C DOWN': 4, 'Waiting': 3, 'Setup': 2, 'PM': 1,
                        'Unknown': 0, 'Running': -1}.get(sev_key, 0)
            prev = open_by_machine.get(m)
            if prev is None or sev_rank > prev['_rank']:
                open_by_machine[m] = {'_rank': sev_rank, 'row': r, 'status_key': sev_key}

    # Apply area filter first
    if selected_areas:
        machines_df = machines_df[machines_df['id_operation'].isin(selected_areas)]

    tiles = []
    counters = {'Running': 0, 'M/C DOWN': 0, 'Setup': 0, 'PM': 0,
                'Waiting': 0, 'Unknown': 0}

    for _, m in machines_df.iterrows():
        mid = m['code_machine']
        if not mid:
            continue
        entry = open_by_machine.get(mid)
        if entry is None:
            status_key = 'Running'
            sub_lines = []
        else:
            r = entry['row']
            status_key = entry['status_key']
            tech = r.get('tech')
            sub_lines = []
            symptom = r.get('des_job') or ''
            if symptom:
                sub_lines.append(str(symptom)[:26])
            if tech:
                sub_lines.append(f"Tech: {tech}")
            # Show wait time for Waiting tiles (still queued for tech),
            # repair time for On-Process tiles (tech is actively repairing).
            if status_key == 'Waiting':
                t_val = r.get('wait_min')
                t_icon = '⏳'       # hourglass
            else:
                t_val = r.get('repair_min')
                t_icon = '\U0001f527'   # wrench
            if t_val is not None:
                try:
                    sub_lines.append(f"{t_icon} {int(t_val)}m")
                except (ValueError, TypeError):
                    pass

        counters[status_key] = counters.get(status_key, 0) + 1

        # Status filter — checklist of statuses to show
        if status_key not in status_filter:
            continue

        tiles.append(_make_tile(mid, status_key, sub_lines))

    # Grid layout + small empty state when no status is selected at all.
    if not status_filter:
        grid = html.Div(
            "Select at least one status to view",
            style={'textAlign': 'center', 'color': MED_GRAY,
                   'padding': '60px', 'fontSize': '18px'})
    elif not tiles:
        grid = html.Div(
            "No machines match current filters",
            style={'textAlign': 'center', 'color': MED_GRAY,
                   'padding': '40px', 'fontSize': '16px'})
    else:
        grid = html.Div(tiles, style={
            'display': 'grid',
            'gridTemplateColumns': 'repeat(auto-fill, minmax(170px, 1fr))',
            'gap': '10px',
        })

    # Summary line above the grid — visible count + which statuses are hidden
    hidden = [s for s in ALL_STATUSES if s not in status_filter]
    if not status_filter:
        grid_summary = ''
    else:
        grid_summary = (
            f"Showing {len(tiles)} machines"
            + (f"  —  {', '.join(hidden)} hidden" if hidden else "")
        )

    # ── Alert banner ──────────────────────────────────────────────────────────
    alert = []
    down_by_area = {}
    for m, e in open_by_machine.items():
        if e['status_key'] == 'M/C DOWN':
            area = str(e['row'].get('area') or '')
            down_by_area[area] = down_by_area.get(area, 0) + 1

    critical_areas = [a for a, c in down_by_area.items()
                      if c >= ALERT_DOWN_THRESHOLD]
    if critical_areas:
        for a in critical_areas:
            alert.append(html.Div([
                html.Span("ALERT: ", style={'fontWeight': '800'}),
                f"{down_by_area[a]} machines M/C DOWN in {a} area",
            ], style={
                'background': RED, 'color': WHITE, 'padding': '10px 16px',
                'fontSize': '16px', 'fontWeight': '700',
                'borderRadius': '4px', 'marginTop': '8px',
                'letterSpacing': '0.5px'}))

    long_wait = 0
    for e in open_by_machine.values():
        if e['status_key'] != 'Waiting':
            continue
        w = e['row'].get('wait_min')
        try:
            if w is not None and int(w) > ALERT_WAIT_MIN_THRESHOLD:
                long_wait += 1
        except (ValueError, TypeError):
            pass
    if long_wait >= ALERT_WAIT_COUNT_THRESHOLD:
        alert.append(html.Div([
            html.Span("WARNING: ", style={'fontWeight': '800'}),
            f"{long_wait} machines waiting > {ALERT_WAIT_MIN_THRESHOLD} min for tech",
        ], style={
            'background': ORANGE, 'color': WHITE, 'padding': '10px 16px',
            'fontSize': '15px', 'fontWeight': '700',
            'borderRadius': '4px', 'marginTop': '8px',
            'letterSpacing': '0.5px'}))

    # ── Header pieces ─────────────────────────────────────────────────────────
    now = datetime.now()
    clock = now.strftime('%H:%M:%S')
    shift_name, mins_left = _current_shift()
    hrs, mins = divmod(mins_left, 60)
    subheader = (f"Shift: {shift_name}  ·  {hrs}h {mins}m left  "
                 f"·  {now.strftime('%Y-%m-%d')}  ·  Auto-refresh 60s")

    # Summary bar
    total = sum(counters.values())
    summary_parts = [
        f"{total} machines",
        f"{counters.get('Running', 0)} Running",
        f"{counters.get('M/C DOWN', 0)} Down",
        f"{counters.get('Setup', 0)} Setup",
        f"{counters.get('PM', 0)} PM",
        f"{counters.get('Waiting', 0)} Waiting",
    ]
    summary = "  |  ".join(summary_parts)

    # Area chips
    area_chips = _make_area_chips(areas, selected_areas or [])

    return clock, subheader, alert, grid_summary, grid, summary, area_chips


# ── Chip click → update area store ────────────────────────────────────────────
@callback(
    Output('live-area-store', 'data'),
    Input({'type': 'live-area-chip', 'area': dash.dependencies.ALL}, 'n_clicks'),
    State('live-area-store', 'data'),
    prevent_initial_call=True,
)
def on_chip_click(n_clicks_list, current_selected):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update

    trig = ctx.triggered[0]
    # auto-refresh rebuilds the chip buttons, which fires this callback with
    # n_clicks=None/0 for each new element. Only react to a real user click
    # (n_clicks >= 1) — otherwise we'd wipe the store on every refresh.
    if not trig.get('value'):
        return no_update

    try:
        triggered_id = trig['prop_id'].split('.')[0]
        import json as _json
        triggered = _json.loads(triggered_id)
        area = triggered.get('area')
    except Exception:
        return no_update

    current = list(current_selected or [])
    if area == '__ALL__':
        return []
    if area in current:
        current.remove(area)
    else:
        current.append(area)
    return current
