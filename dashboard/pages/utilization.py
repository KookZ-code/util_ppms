"""Utilization page - KPI gauges, monthly composition, area comparison,
top causes, and machine breakdown table.
Two callbacks: primary (KPIs + charts) loads first; secondary (machine table) loads after.
"""
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime

from components.header import make_page_header, make_chart_title
from components.filters import make_filter_bar
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    WHITE, MED_GRAY, CHART_COLORS,
)

dash.register_page(__name__, path='/utilization', name='Utilization')

# ── Job type groupings ────────────────────────────────────────────────────────
DOWN_TYPES = ('M/C DOWN',)
PM_TYPES   = ('PM',)
LOST_TYPES = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD',
              'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN')

# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    make_page_header("Machine Utilization Analysis"),

    # Unified filter panel
    html.Div([
        # Row 1: Date + Shift + Apply
        dbc.Row([
            dbc.Col([
                html.Label("Date Range", className='filter-label'),
                dcc.DatePickerRange(
                    id='filter-date-range',
                    start_date=(datetime.now() - __import__('datetime').timedelta(days=365)).strftime('%Y-%m-%d'),
                    end_date=datetime.now().strftime('%Y-%m-%d'),
                    display_format='YYYY-MM-DD',
                    style={'width': '100%'},
                ),
            ], lg=4, md=6, sm=12),
            dbc.Col([
                html.Label("Shift", className='filter-label'),
                dcc.Dropdown(
                    id='util-filter-shift',
                    options=[
                        {'label': 'Day (07:00–19:00)',   'value': 'DAY'},
                        {'label': 'Night (19:00–07:00)', 'value': 'NIGHT'},
                    ],
                    value=None, placeholder='All Shifts',
                    style={'fontSize': '13px'},
                ),
            ], lg=2, md=3, sm=12),
        ], className='g-2 align-items-end'),

        # Divider
        html.Hr(style={'margin': '10px 0 8px', 'opacity': '0.15'}),

        # Row 2: Area toggles
        html.Div([
            html.Span("AREA", style={
                'fontSize': '11px', 'fontWeight': '700', 'color': '#0E3689',
                'letterSpacing': '0.5px', 'marginRight': '14px',
                'verticalAlign': 'middle',
            }),
            dbc.Checklist(
                id='util-area-toggle',
                options=[],
                value=[],
                inline=True,
                style={'fontSize': '13px', 'fontWeight': '500', 'display': 'inline-flex',
                       'gap': '4px', 'flexWrap': 'wrap', 'verticalAlign': 'middle'},
            ),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], className='filter-bar'),

    # Month click state
    dcc.Store(id='util-month-click', data=None),

    # Month filter indicator
    html.Div(id='util-month-indicator'),

    # Row 1: 4 KPI Gauges
    dbc.Row(id='util-gauge-row', className='g-3 mb-4'),

    # Row 2: Monthly composition + Area comparison
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Time Composition by Month", "Click bar to filter"),
                dcc.Graph(id='util-monthly', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=7, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Utilization by Area", "Current Period"),
                dcc.Graph(id='util-area', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=5, md=12),
    ], className='mb-0'),

    # Row 3: Top causes
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Top 5 Downtime Symptoms", "M/C DOWN", '#C0392B'),
                dcc.Graph(id='util-top-down', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=6, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Top 5 Lost Time Causes", "Setup · Wait", '#702076'),
                dcc.Graph(id='util-top-lost', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=6, md=12),
    ], className='mb-0'),

    # Row 4: Top 10 Attention List + Frequency vs Duration Scatter
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Top 10 Machines Needing Attention", "Action List", RED),
                dcc.Loading(type='dot', color=PRIMARY_BLUE,
                            children=html.Div(id='util-attention-list')),
            ], className='chart-card'),
        ], lg=5, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Downtime: Frequency vs Duration", "Per Machine",
                                 PRIMARY_BLUE),
                dcc.Graph(id='util-scatter', config={'displayModeBar': True,
                                                     'scrollZoom': True}),
            ], className='chart-card'),
        ], lg=7, md=12),
    ], className='mb-0'),

    # Row 5: Machine breakdown table (secondary callback)
    html.Div([
        html.Div([
            html.Div([
                html.Span("Machine Breakdown", style={
                    'fontSize': '14px', 'fontWeight': '600', 'color': 'var(--text)',
                }),
                html.Span(" — Sorted by Utilization (Lowest First)", style={
                    'fontSize': '12px', 'color': 'var(--text-light)', 'marginLeft': '4px',
                }),
            ]),
            html.Div([
                html.Span("Top 100", style={
                    'fontSize': '10px', 'fontWeight': '600',
                    'color': 'var(--text-light)', 'background': 'var(--badge-bg)',
                    'padding': '2px 9px', 'borderRadius': '10px',
                    'textTransform': 'uppercase', 'letterSpacing': '0.4px',
                    'marginRight': '10px',
                }),
                html.Button([
                    html.Span("⬇", style={'marginRight': '5px'}),
                    "Export CSV",
                ], id='btn-export-csv', style={
                    'background': PRIMARY_BLUE,
                    'color': '#FFFFFF',
                    'border': 'none',
                    'borderRadius': '6px',
                    'padding': '5px 14px',
                    'fontSize': '12px',
                    'fontWeight': '600',
                    'cursor': 'pointer',
                    'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                    'boxShadow': '0 2px 4px rgba(14,54,137,0.25)',
                }),
            ], style={'display': 'flex', 'alignItems': 'center'}),
        ], style={
            'display': 'flex', 'justifyContent': 'space-between',
            'alignItems': 'center', 'marginBottom': '12px',
            'paddingBottom': '10px', 'borderBottom': '1px solid var(--divider)',
        }),
        dcc.Download(id='download-machine-csv'),
        dcc.Loading(
            id='util-table-loading',
            type='dot',
            color=PRIMARY_BLUE,
            children=html.Div(id='util-machine-table'),
        ),
    ], className='chart-card'),

    html.Div(id='util-refresh-time', className='refresh-info'),

], className='page-container')


# ── Helpers ───────────────────────────────────────────────────────────────────
def _empty_fig():
    fig = go.Figure()
    fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Calibri, Segoe UI, sans-serif'))
    return fig


@callback(
    Output('util-area-toggle', 'options'),
    Input('auto-refresh', 'n_intervals'),
)
def load_util_area_options(n):
    from db import query_df
    from utils.queries import distinct_areas
    from config import MACHINE_AREAS, ORA_ENABLED
    try:
        df = query_df(distinct_areas())
        db_areas = df['area'].tolist()
        if ORA_ENABLED:
            for a in ('ISO', 'FS'):
                if a not in db_areas:
                    db_areas.append(a)
        order = {a: i for i, a in enumerate(MACHINE_AREAS)}
        sorted_areas = sorted(db_areas, key=lambda a: order.get(a, 999))
        return [{'label': f'  {a}', 'value': a} for a in sorted_areas]
    except Exception:
        return []


# ── Month click → store ──────────────────────────────────────────────────────
@callback(
    Output('util-month-click', 'data'),
    Input('util-monthly', 'clickData'),
    prevent_initial_call=True,
)
def on_month_click(click_data):
    if click_data and click_data.get('points'):
        raw = click_data['points'][0].get('x', '')
        # Normalize to 'YYYY-MM' regardless of input format
        return str(raw)[:7]  # '2025-09-01' → '2025-09', '2025-09' → '2025-09'
    return None


@callback(
    Output('util-month-indicator', 'children'),
    Input('util-month-click', 'data'),
)
def show_month_indicator(month):
    if not month:
        return None
    # Format 'YYYY-MM' as readable month name
    try:
        from datetime import datetime as _dt
        label = _dt.strptime(month[:7], '%Y-%m').strftime('%B %Y')
    except Exception:
        label = month
    return html.Div([
        html.Span(f"Filtered: {label}", style={
            'fontSize': '13px', 'fontWeight': '600', 'color': PRIMARY_BLUE,
        }),
        html.Span("  "),
        html.A("Clear", id='util-month-clear', href='#', n_clicks=0,
               style={'fontSize': '12px', 'color': RED, 'cursor': 'pointer',
                      'textDecoration': 'underline'}),
    ], style={'padding': '6px 16px', 'background': '#EEF4FF',
              'borderRadius': '6px', 'marginBottom': '10px',
              'display': 'inline-block'})


@callback(
    Output('util-month-click', 'data', allow_duplicate=True),
    Input('util-month-clear', 'n_clicks'),
    prevent_initial_call=True,
)
def clear_month_filter(n):
    if n:
        return None
    return dash.no_update


def _calc_available_min(start_date, end_date, shift, machine_count):
    """Calendar-based available minutes.
    Waiting_time confirmed as sub-component of DATEDIFF (n_exceeds=0) — not added.
    available = machine_count × days × hours_per_day × 60
    """
    if not start_date or not end_date or machine_count <= 0:
        return 1
    try:
        d0 = datetime.strptime(str(start_date)[:10], '%Y-%m-%d')
        d1 = datetime.strptime(str(end_date)[:10], '%Y-%m-%d')
    except ValueError:
        return 1
    n_days = (d1 - d0).days + 1
    if n_days <= 0:
        return 1
    hours = 12 if shift in ('DAY', 'NIGHT') else 24
    return machine_count * n_days * hours * 60


def _compute_pcts(kpi_df, available_min):
    """Compute utilization % using calendar-based available time.

    Downtime = repair time only   = DATEDIFF(tech_start, end) for DOWN_TYPES
    Lost     = LOST_TYPES repair  + ALL Waiting_time (waiting for tech)
    util     = available - down - pm - lost
    """
    available_min = max(available_min, 1)

    def _repair(types):
        return kpi_df[kpi_df['job_type'].isin(types)]['total_min'].sum()

    total_wait = kpi_df['wait_min'].sum()   # waiting time across all jobs → Lost

    down_min = _repair(DOWN_TYPES)
    pm_min   = _repair(PM_TYPES)
    lost_min = _repair(LOST_TYPES) + total_wait

    down_pct = round(down_min / available_min * 100, 2)
    pm_pct   = round(pm_min   / available_min * 100, 2)
    lost_pct = round(lost_min / available_min * 100, 2)
    util_pct = round(max(0.0, 100 - down_pct - pm_pct - lost_pct), 2)
    return util_pct, down_pct, pm_pct, lost_pct


# ── Primary callback: KPIs + charts ──────────────────────────────────────────
@callback(
    Output('util-gauge-row',    'children'),
    Output('util-scatter',      'figure'),
    Output('util-monthly',      'figure'),
    Output('util-area',         'figure'),
    Output('util-top-down',     'figure'),
    Output('util-top-lost',     'figure'),
    Output('util-refresh-time', 'children'),
    Input('auto-refresh',       'n_intervals'),
    Input('filter-date-range',  'start_date'),
    Input('filter-date-range',  'end_date'),
    Input('util-area-toggle',   'value'),
    Input('util-filter-shift',  'value'),
    Input('util-month-click',   'data'),
)
def update_primary(n_intervals, start_date, end_date, areas, shift,
                   selected_month):  # noqa: C901
    import pandas as pd
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import (build_util_where, util_kpi_totals,
                                util_monthly_composition, util_by_area,
                                util_total_machine_count, util_machine_count,
                                util_kpi_prev_period, util_freq_vs_duration,
                                util_top_machines_per_cause)
    from components.kpi_card import make_kpi_card

    sc      = COLUMN_MAP.get('status',          'job_type')   or 'job_type'
    opr_tc  = COLUMN_MAP.get('opr_start_time', 'datex') or 'datex'   # Operator open
    tech_tc = COLUMN_MAP.get('tech_start_time', 'datex')      or 'datex'      # Tech repair start
    ec      = COLUMN_MAP.get('end_time',        'date_close') or 'date_close'
    ac      = COLUMN_MAP.get('machine_area',    'id_operation') or 'id_operation'
    rc      = COLUMN_MAP.get('downtime_reason', 'cause')      or 'cause'
    mid     = COLUMN_MAP.get('machine_id',      'code_machine') or 'code_machine'

    # Full date range WHERE (for monthly chart + KPI totals + machine count)
    where, params = build_util_where(opr_tc, ec, ac, start_date, end_date, areas, shift)

    # Month-filtered WHERE (for top causes, area, scatter when a month is selected)
    if selected_month:
        from calendar import monthrange as _mr
        _yr, _mo = int(selected_month[:4]), int(selected_month[5:7])
        _ms = f"{_yr}-{_mo:02d}-01"
        _me = f"{_yr}-{_mo:02d}-{_mr(_yr, _mo)[1]}"
        where_m, params_m = build_util_where(opr_tc, ec, ac, _ms, _me, areas, shift)
    else:
        where_m, params_m = where, params

    ef = _empty_fig()

    # ── Phase 3: try API path first; fallback to direct DB on failure ─────────
    api_used = False
    try:
        from api_client import USE_API, fetch_utilization_detail, utilization_detail_to_frames
        if USE_API:
            _data = fetch_utilization_detail(
                start_date, end_date, areas, shift, selected_month)
            frames = utilization_detail_to_frames(_data)
            kpi_df      = frames['kpi_df']
            trend_df    = frames['trend_df']
            area_df     = frames['area_df']
            cnt_df      = frames['cnt_df']
            area_cnt_df = frames['area_cnt_df']
            scatter_df  = frames['scatter_df']
            top_down_df = frames['top_down_df']
            top_lost_df = frames['top_lost_df']
            mach_per_cause_df = frames['mach_per_cause_df']
            prev_df     = frames['prev_df']
            prev_mc     = frames['prev_mc']
            api_used    = True
    except Exception as _api_err:
        import logging
        logging.warning(f"Utilization API failed ({_api_err}), fallback to DB")
        api_used = False

    try:
        # ── Load Oracle data (ISO/FS) — single query, fail-safe ───────────────
        ora_df = None
        if not api_used:
            try:
                from config import ORA_ENABLED
                if ORA_ENABLED:
                    from oracle_db import fetch_oracle_data
                    if not areas or any(a in ('ISO', 'FS') for a in areas):
                        ora_df = fetch_oracle_data(start_date, end_date, areas, shift)
            except Exception:
                ora_df = None

        # ── SQL Server queries (skipped when API supplied data) ───────────────
        if not api_used:
            kpi_df      = query_df(util_kpi_totals(VIEW_NAME, tech_tc, ec, sc, where), params)
            trend_df    = query_df(util_monthly_composition(VIEW_NAME, opr_tc, tech_tc, ec, sc, where), params)
            area_df     = query_df(util_by_area(VIEW_NAME, tech_tc, ec, sc, ac, where_m), params_m)
            cnt_df      = query_df(util_total_machine_count(VIEW_NAME, mid, where), params)
            area_cnt_df = query_df(util_machine_count(VIEW_NAME, ac, mid, where), params)

        # ── Merge Oracle aggregations (skipped when API already merged) ───────
        if not api_used and ora_df is not None:
            from utils.oracle_agg import (ora_kpi_totals, ora_monthly,
                                          ora_by_area, ora_machine_count,
                                          ora_total_machine_count,
                                          ora_freq_vs_duration,
                                          ora_top_symptoms, ora_top_lost_causes,
                                          ora_machines_per_cause)
            # Month-filter Oracle data for queries that use where_m
            _ora_m = ora_df
            if selected_month and ora_df is not None:
                _ora_m = ora_df[ora_df['datex'].dt.strftime('%Y-%m') == selected_month]
                if _ora_m.empty:
                    _ora_m = None

            kpi_df      = pd.concat([kpi_df, ora_kpi_totals(ora_df)], ignore_index=True)
            trend_df    = pd.concat([trend_df, ora_monthly(ora_df)], ignore_index=True)
            _ora_area = _ora_m if _ora_m is not None else ora_df
            area_df     = pd.concat([area_df, ora_by_area(_ora_area)], ignore_index=True)
            area_cnt_df = pd.concat([area_cnt_df, ora_machine_count(_ora_area)], ignore_index=True)
            ora_cnt     = ora_total_machine_count(ora_df)
            if not ora_cnt.empty and not cnt_df.empty:
                cnt_df['machine_count'] = (cnt_df['machine_count'].iloc[0]
                                           + ora_cnt['machine_count'].iloc[0])
            elif not ora_cnt.empty:
                cnt_df = ora_cnt

        # Previous period — when month clicked: prev month; otherwise: same duration shifted back
        # When api_used, prev_df was already populated above; we still compute prev_avail_min here.
        if not api_used:
            prev_df    = None
        prev_avail_min = None
        try:
            from datetime import datetime as _dt, timedelta as _td
            if selected_month and selected_month in month_data:
                from calendar import monthrange as _mr3
                _yr3, _mo3 = int(selected_month[:4]), int(selected_month[5:7])
                # Previous month
                if _mo3 == 1:
                    p_yr, p_mo = _yr3 - 1, 12
                else:
                    p_yr, p_mo = _yr3, _mo3 - 1
                prev_start = f"{p_yr}-{p_mo:02d}-01"
                prev_end = f"{p_yr}-{p_mo:02d}-{_mr3(p_yr, p_mo)[1]}"
            else:
                d0 = _dt.strptime(str(start_date)[:10], '%Y-%m-%d')
                d1 = _dt.strptime(str(end_date)[:10],   '%Y-%m-%d')
                n_days = (d1 - d0).days + 1
                prev_start = (d0 - _td(days=n_days)).strftime('%Y-%m-%d')
                prev_end   = (d0 - _td(days=1)).strftime('%Y-%m-%d')

            if not api_used:
                prev_where, prev_params_q = build_util_where(
                    opr_tc, ec, ac, prev_start, prev_end, areas, shift)
                prev_df    = query_df(
                    util_kpi_totals(VIEW_NAME, tech_tc, ec, sc, prev_where),
                    prev_params_q)
                prev_cnt   = query_df(
                    util_total_machine_count(VIEW_NAME, mid, prev_where),
                    prev_params_q)
                # Merge Oracle previous period
                prev_ora = None
                try:
                    from config import ORA_ENABLED as _OE
                    if _OE:
                        from oracle_db import fetch_oracle_data as _ofd
                        if not areas or any(a in ('ISO', 'FS') for a in areas):
                            prev_ora = _ofd(prev_start, prev_end, areas, shift)
                except Exception:
                    prev_ora = None
                if prev_ora is not None:
                    prev_df = pd.concat([prev_df, ora_kpi_totals(prev_ora)], ignore_index=True)
                    p_ora_cnt = ora_total_machine_count(prev_ora)
                    if not p_ora_cnt.empty and not prev_cnt.empty:
                        prev_cnt['machine_count'] = (prev_cnt['machine_count'].iloc[0]
                                                     + p_ora_cnt['machine_count'].iloc[0])
                prev_mc    = int(prev_cnt['machine_count'].iloc[0]) if not prev_cnt.empty else 0
            # prev_mc is already set when api_used (from API response)
            prev_avail_min = _calc_available_min(prev_start, prev_end, shift, prev_mc)
        except Exception:
            prev_df = None

        # Oracle month-filtered data for non-monthly queries
        ora_m = None
        if ora_df is not None:
            if selected_month:
                _tmp = ora_df[ora_df['datex'].dt.strftime('%Y-%m') == selected_month]
                ora_m = _tmp if not _tmp.empty else None
            else:
                ora_m = ora_df

        # Scatter: frequency vs duration (API already fetched when api_used)
        if not api_used:
            scatter_df = query_df(
                util_freq_vs_duration(VIEW_NAME, tech_tc, ec, sc, ac, mid, where_m),
                params_m
            )
            if ora_m is not None:
                scatter_df = pd.concat([scatter_df, ora_freq_vs_duration(ora_m)],
                                       ignore_index=True)

        machine_count = int(cnt_df['machine_count'].iloc[0]) if not cnt_df.empty else 0
        available_min = _calc_available_min(start_date, end_date, shift, machine_count)

        down_in = ', '.join(f"'{t}'" for t in DOWN_TYPES)
        lost_in = ', '.join(f"'{t}'" for t in LOST_TYPES)
        sym = COLUMN_MAP.get('symptom', 'des_job') or 'des_job'
        if not api_used:
            top_down_df = query_df(f"""
                SELECT TOP 5 [{sym}] AS cause,
                       SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0 AS hours
                FROM {VIEW_NAME} {where_m}
                AND [{sc}] IN ({down_in})
                AND [{sym}] IS NOT NULL AND [{sym}] != ''
                GROUP BY [{sym}] ORDER BY hours DESC
            """, params_m)
            top_lost_df = query_df(f"""
                SELECT TOP 5 [{rc}] AS cause,
                       SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0
                       + SUM(ISNULL(Waiting_time, 0)) / 60.0 AS hours
                FROM {VIEW_NAME} {where_m}
                AND [{sc}] IN ({lost_in})
                AND [{rc}] IS NOT NULL AND [{rc}] != ''
                GROUP BY [{rc}] ORDER BY hours DESC
            """, params_m)

            # Merge Oracle top causes (month-filtered)
            if ora_m is not None:
                ora_td = ora_top_symptoms(ora_m)
                if not ora_td.empty:
                    top_down_df = pd.concat([top_down_df, ora_td], ignore_index=True)
                    top_down_df = (top_down_df.groupby('cause')['hours'].sum()
                                   .reset_index().nlargest(5, 'hours'))
                ora_tl = ora_top_lost_causes(ora_m, list(LOST_TYPES))
                if not ora_tl.empty:
                    top_lost_df = pd.concat([top_lost_df, ora_tl], ignore_index=True)
                    top_lost_df = (top_lost_df.groupby('cause')['hours'].sum()
                                   .reset_index().nlargest(5, 'hours'))

            # Top 3 machines per downtime symptom (for hover tooltip)
            mach_per_cause_df = query_df(
                util_top_machines_per_cause(
                    VIEW_NAME, tech_tc, ec, sc, sym, mid, where_m, down_in),
                params_m
            )
            if ora_m is not None:
                ora_mpc = ora_machines_per_cause(ora_m)
                if not ora_mpc.empty:
                    mach_per_cause_df = pd.concat([mach_per_cause_df, ora_mpc],
                                                  ignore_index=True)
        cause_machines = {}
        for cause, grp in mach_per_cause_df.groupby('cause'):
            parts = [f"{r['machine_id']} ({r['hrs']:.1f}h)" for _, r in grp.iterrows()]
            cause_machines[cause] = '<br>'.join(parts)

        # ── KPI cards ─────────────────────────────────────────────────────────
        # Full-period values (always computed)
        util_pct, down_pct, pm_pct, lost_pct = _compute_pcts(kpi_df, available_min)

        # Monthly stacked 100% bar — compute BEFORE KPI override
        monthly_fig = go.Figure()
        month_data = {}  # {ym: (util, down, pm, lost)} for click-to-filter
        if not trend_df.empty:
            months   = sorted(trend_df['ym'].dropna().unique())
            seg_util, seg_down, seg_pm, seg_lost = [], [], [], []
            n_days_total = max((_calc_available_min(start_date, end_date, shift, 1)
                                // (60 * (12 if shift in ('DAY','NIGHT') else 24))), 1)
            for ym in months:
                sub = trend_df[trend_df['ym'] == ym]
                hours = 12 if shift in ('DAY', 'NIGHT') else 24
                try:
                    from calendar import monthrange
                    _yr, _mo = int(ym[:4]), int(ym[5:7])
                    days_in_month = monthrange(_yr, _mo)[1]
                except Exception:
                    days_in_month = 30
                avail_m = machine_count * days_in_month * hours * 60
                avail_m = max(avail_m, 1)
                wait_m = sub['wait_min'].sum()
                d = round(sub[sub['job_type'].isin(DOWN_TYPES)]['total_min'].sum() / avail_m * 100, 2)
                p = round(sub[sub['job_type'].isin(PM_TYPES)]  ['total_min'].sum() / avail_m * 100, 2)
                l = round((sub[sub['job_type'].isin(LOST_TYPES)]['total_min'].sum() + wait_m) / avail_m * 100, 2)
                u = round(max(0.0, 100 - d - p - l), 2)
                seg_util.append(u); seg_down.append(d)
                seg_pm.append(p);   seg_lost.append(l)
                month_data[ym] = (u, d, p, l)

            for name, values, color in [
                ('Utilization', seg_util, GREEN),
                ('Downtime',    seg_down, RED),
                ('PM',          seg_pm,   PURPLE),
                ('Lost Time',   seg_lost, ORANGE),
            ]:
                labels = [f"{v:.2f}%" if v >= 5 else "" for v in values]
                monthly_fig.add_trace(go.Bar(
                    name=name, x=months, y=values, marker_color=color,
                    text=labels,
                    textposition='inside',
                    insidetextanchor='middle',
                    textfont=dict(size=13, color='white', family='Inter, Calibri, sans-serif'),
                    hovertemplate=f'<b>{name}</b><br>%{{x}}: %{{y:.2f}}%<extra></extra>',
                ))
        monthly_fig.update_layout(
            barmode='stack', template='plotly_white', height=320,
            margin=dict(t=10, b=65, l=40, r=10),
            yaxis=dict(title='%', range=[0, 108], showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
            xaxis=dict(tickangle=-40, showgrid=False),
            legend=dict(orientation='h', y=-0.22, font=dict(size=11)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri, Segoe UI, sans-serif'), bargap=0.25,
        )

        # If month clicked → override KPI values from the bar chart data
        if selected_month and selected_month in month_data:
            util_pct, down_pct, pm_pct, lost_pct = month_data[selected_month]

        util_color = GREEN if util_pct >= 80 else ORANGE if util_pct >= 60 else RED

        # Trend arrows vs previous period
        def _trend(current, prev, higher_is_better=True):
            if prev is None:
                return None
            delta = round(current - prev, 1)
            if abs(delta) < 0.1:
                return {'delta': delta, 'direction': 'flat', 'improved': None}
            improving = (delta > 0) == higher_is_better
            return {
                'delta':    delta,
                'direction': 'up' if delta > 0 else 'down',
                'improved':  improving,
            }

        prev_util = prev_down = prev_pm = prev_lost = None
        t_label = 'vs prev period'

        if selected_month and selected_month in month_data:
            # Compare with previous month from bar chart data
            _yr_s, _mo_s = int(selected_month[:4]), int(selected_month[5:7])
            if _mo_s == 1:
                prev_ym = f"{_yr_s-1}-12"
            else:
                prev_ym = f"{_yr_s}-{_mo_s-1:02d}"
            if prev_ym in month_data:
                prev_util, prev_down, prev_pm, prev_lost = month_data[prev_ym]
            t_label = f'vs {prev_ym}'
        elif prev_df is not None and not prev_df.empty and prev_avail_min:
            prev_util, prev_down, prev_pm, prev_lost = _compute_pcts(prev_df, prev_avail_min)

        gauges = [
            dbc.Col(make_kpi_card(
                f"{util_pct:.2f}", "Percent Utilization", util_color,
                subtitle="100% − Down − PM − Lost", icon="⚙", unit="%",
                trend=_trend(util_pct, prev_util, higher_is_better=True),
                trend_label=t_label,
            ), lg=3, md=6, sm=12),
            dbc.Col(make_kpi_card(
                f"{down_pct:.2f}", "Percent Downtime", RED,
                subtitle="M/C DOWN only", icon="⛔", unit="%",
                trend=_trend(down_pct, prev_down, higher_is_better=False),
                trend_label=t_label,
            ), lg=3, md=6, sm=12),
            dbc.Col(make_kpi_card(
                f"{pm_pct:.2f}", "Percent Downtime PM", PURPLE,
                subtitle="Planned maintenance", icon="🔧", unit="%",
                trend=_trend(pm_pct, prev_pm, higher_is_better=False),
                trend_label=t_label,
            ), lg=3, md=6, sm=12),
            dbc.Col(make_kpi_card(
                f"{lost_pct:.2f}", "Percent Lost Time", ORANGE,
                subtitle="Setup · Wait · Convert", icon="⏱", unit="%",
                trend=_trend(lost_pct, prev_lost, higher_is_better=False),
                trend_label=t_label,
            ), lg=3, md=6, sm=12),
        ]

        # (monthly chart already computed above)

        # ── Area comparison bar ────────────────────────────────────────────────
        from config import AREA_TARGETS
        DEFAULT_TARGET = 85

        area_fig = go.Figure()
        if not area_df.empty:
            hours = 12 if shift in ('DAY', 'NIGHT') else 24
            # Use month days when filtered, full range otherwise
            if selected_month:
                from calendar import monthrange as _mr2
                _yr2, _mo2 = int(selected_month[:4]), int(selected_month[5:7])
                area_n_days = _mr2(_yr2, _mo2)[1]
            else:
                area_n_days = n_days_total
            area_avail = {
                row['area']: max(int(row['machine_count']) * area_n_days * hours * 60, 1)
                for _, row in area_cnt_df.iterrows()
            } if not area_cnt_df.empty else {}

            area_total = area_df.groupby('area').apply(
                lambda g: pd.Series({
                    'down_min': g[g['job_type'].isin(DOWN_TYPES)]['total_min'].sum(),
                    'pm_min':   g[g['job_type'].isin(PM_TYPES)]['total_min'].sum(),
                    'lost_min': g[g['job_type'].isin(LOST_TYPES)]['total_min'].sum()
                              + g['wait_min'].sum(),
                }), include_groups=False
            ).reset_index()

            def _area_util(row):
                av = area_avail.get(row['area'], available_min)
                return round(max(0.0, 100 - (row['down_min']+row['pm_min']+row['lost_min']) / av * 100), 2)

            area_total['util_pct'] = area_total.apply(_area_util, axis=1)
            area_total['target']   = area_total['area'].map(
                lambda a: AREA_TARGETS.get(a, DEFAULT_TARGET))
            area_total = area_total.sort_values('util_pct')

            # Color by per-area target
            a_colors = [
                GREEN if row['util_pct'] >= row['target']
                else ORANGE if row['util_pct'] >= row['target'] - 10
                else RED
                for _, row in area_total.iterrows()
            ]
            area_fig.add_trace(go.Bar(
                name='Utilization',
                y=area_total['area'], x=area_total['util_pct'],
                orientation='h', marker=dict(color=a_colors, line=dict(width=0)),
                text=[f"{row['util_pct']:.2f}%" for _, row in area_total.iterrows()],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=11, color='white'),
                width=0.55,
                customdata=area_total['target'].values,
                hovertemplate=(
                    '<b>%{y}</b><br>'
                    'Utilization: %{x:.2f}%<br>'
                    'Target: %{customdata}%'
                    '<extra></extra>'
                ),
            ))

            # Target diamond markers (outside bars, no overlap)
            area_fig.add_trace(go.Scatter(
                y=area_total['area'],
                x=area_total['target'],
                mode='markers+text',
                marker=dict(symbol='diamond', size=10,
                            color=PRIMARY_BLUE, line=dict(width=1, color='white')),
                text=[f"{t}%" for t in area_total['target']],
                textposition='middle right',
                textfont=dict(size=9, color=PRIMARY_BLUE),
                name='Target',
                hovertemplate='<b>%{y}</b> target: %{x}%<extra></extra>',
            ))
        area_fig.update_layout(
            template='plotly_white',
            height=max(320, len(area_df['area'].unique()) * 36 + 100) if not area_df.empty else 320,
            margin=dict(t=10, b=40, l=10, r=20),
            xaxis=dict(title=None, range=[0, 120], showgrid=True,
                       gridcolor='rgba(128,128,128,0.15)', ticksuffix='%'),
            yaxis=dict(title=None, automargin=True),
            showlegend=True,
            legend=dict(orientation='h', y=-0.12, font=dict(size=10)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri, Segoe UI, sans-serif'),
        )

        # ── Top cause bar helper ───────────────────────────────────────────────
        def _cause_bar(df, color, machine_lookup=None):
            fig = go.Figure()
            if not df.empty:
                df = df.sort_values('hours')
                total = df['hours'].sum()
                pcts = (df['hours'] / total * 100).round(2) if total > 0 else df['hours'] * 0

                if machine_lookup:
                    top3 = [machine_lookup.get(c, '—') for c in df['cause']]
                    hover = (
                        '<b>%{y}</b><br>'
                        '%{x:.2f}% of total<br>'
                        '<b>Top machines:</b><br>'
                        '%{customdata}'
                        '<extra></extra>'
                    )
                else:
                    top3 = None
                    hover = '<b>%{y}</b><br>%{x:.2f}%<extra></extra>'

                fig.add_trace(go.Bar(
                    y=df['cause'], x=pcts, orientation='h',
                    marker=dict(color=color, line=dict(width=0)),
                    text=[f"  {v:.2f}%" for v in pcts],
                    textposition='outside', textfont=dict(size=10), width=0.5,
                    customdata=top3,
                    hovertemplate=hover,
                ))
            fig.update_layout(
                template='plotly_white',
                height=max(240, len(df) * 28 + 60),
                margin=dict(t=5, b=30, l=10, r=80),
                xaxis=dict(title=None, showgrid=True, gridcolor='rgba(128,128,128,0.15)',
                           ticksuffix='%', rangemode='tozero',
                           range=[0, max(pcts.max() * 1.25, 10) if not df.empty else 50]),
                yaxis=dict(title=None, automargin=True),
                showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Calibri, Segoe UI, sans-serif'),
            )
            return fig

        # ── Scatter: Frequency vs Duration ────────────────────────────────────
        scatter_fig = go.Figure()
        if not scatter_df.empty:
            areas_in_data = scatter_df['area'].unique().tolist()
            area_color_map = {a: CHART_COLORS[i % len(CHART_COLORS)]
                              for i, a in enumerate(areas_in_data)}

            # Median lines for quadrant reference
            med_freq = scatter_df['freq'].median()
            med_dur  = scatter_df['avg_dur_min'].median()

            for area_val, grp in scatter_df.groupby('area'):
                color = area_color_map.get(area_val, MED_GRAY)
                sizes = (grp['total_hours'].clip(upper=200) * 0.4 + 6).tolist()
                scatter_fig.add_trace(go.Scatter(
                    x=grp['freq'], y=grp['avg_dur_min'],
                    mode='markers',
                    name=str(area_val),
                    marker=dict(size=sizes, color=color, opacity=0.7,
                                line=dict(width=0.5, color='white')),
                    text=grp['machine_id'],
                    customdata=grp[['machine_id', 'total_hours', 'freq', 'avg_dur_min']].values,
                    hovertemplate=(
                        '<b>%{customdata[0]}</b><br>'
                        'Events: %{customdata[2]}<br>'
                        'Avg Duration: %{customdata[3]:.0f} min<br>'
                        'Total Hours: %{customdata[1]:.1f} hrs'
                        '<extra>%{fullData.name}</extra>'
                    ),
                ))

            # Quadrant lines
            scatter_fig.add_vline(x=med_freq, line=dict(dash='dot', color=MED_GRAY, width=1))
            scatter_fig.add_hline(y=med_dur,  line=dict(dash='dot', color=MED_GRAY, width=1))

            # Quadrant labels
            x_max = scatter_df['freq'].max() * 1.05
            y_max = scatter_df['avg_dur_min'].max() * 1.05
            for text, x, y in [
                ('Chronic', x_max * 0.95, y_max * 0.95),
                ('Severe',  med_freq * 0.1, y_max * 0.95),
                ('Nuisance', x_max * 0.95, med_dur * 0.1),
                ('Healthy', med_freq * 0.1, med_dur * 0.1),
            ]:
                scatter_fig.add_annotation(
                    x=x, y=y, text=text, showarrow=False,
                    font=dict(size=10, color=MED_GRAY), opacity=0.6,
                )

        scatter_fig.update_layout(
            template='plotly_white', height=380,
            margin=dict(t=10, b=50, l=60, r=10),
            xaxis=dict(title='Number of M/C DOWN Events (Frequency)',
                       showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
            yaxis=dict(title='Avg Repair Duration (min)',
                       showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
            legend=dict(orientation='h', y=-0.18, font=dict(size=11)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri, Segoe UI, sans-serif'),
        )

        refresh_time = f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}"
        return (gauges, scatter_fig, monthly_fig, area_fig,
                _cause_bar(top_down_df, ORANGE, machine_lookup=cause_machines),
                _cause_bar(top_lost_df, PURPLE),
                refresh_time)

    except Exception as e:
        err = html.Div([
            html.B("Callback error: "),
            html.Pre(str(e), style={'fontSize': '11px', 'whiteSpace': 'pre-wrap',
                                    'marginTop': '8px'}),
        ], style={'color': RED, 'padding': '16px', 'background': '#fff0f0',
                  'borderRadius': '6px', 'border': f'1px solid {RED}'})
        return [err], ef, ef, ef, ef, ef, f"Error at {datetime.now():%H:%M:%S}"


# ── Secondary callback: machine breakdown table ───────────────────────────────
@callback(
    Output('util-machine-table', 'children'),
    Input('auto-refresh',      'n_intervals'),
    Input('filter-date-range', 'start_date'),
    Input('filter-date-range', 'end_date'),
    Input('util-area-toggle',  'value'),
    Input('util-filter-shift', 'value'),
    Input('util-month-click',  'data'),
)
def update_machine_table(n_intervals, start_date, end_date, areas, shift,
                         selected_month):
    import pandas as pd
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import build_util_where, util_by_machine
    from components.data_table import make_data_table

    sc      = COLUMN_MAP.get('status',          'job_type')   or 'job_type'
    opr_tc  = COLUMN_MAP.get('opr_start_time', 'datex') or 'datex'
    tech_tc = COLUMN_MAP.get('tech_start_time', 'datex')      or 'datex'
    ec      = COLUMN_MAP.get('end_time',        'date_close') or 'date_close'
    ac      = COLUMN_MAP.get('machine_area',    'id_operation') or 'id_operation'
    mid     = COLUMN_MAP.get('machine_id',      'code_machine') or 'code_machine'

    if selected_month:
        from calendar import monthrange
        yr, mo = int(selected_month[:4]), int(selected_month[5:7])
        start_date = f"{yr}-{mo:02d}-01"
        end_date = f"{yr}-{mo:02d}-{monthrange(yr, mo)[1]}"
    where, params = build_util_where(opr_tc, ec, ac, start_date, end_date, areas, shift)

    # ── Phase 3: try API first, fallback to DB ────────────────────────────────
    api_used = False
    try:
        from api_client import USE_API, fetch_utilization_by_machine
        if USE_API:
            df = fetch_utilization_by_machine(start_date, end_date, areas, shift)
            api_used = True
    except Exception as _api_err:
        import logging
        logging.warning(f"by-machine API failed ({_api_err}), fallback to DB")
        api_used = False

    try:
        if not api_used:
            df = query_df(util_by_machine(VIEW_NAME, tech_tc, ec, sc, ac, mid, where), params)
        # Merge Oracle (skip if API already did)
        try:
            from config import ORA_ENABLED
            if not api_used and ORA_ENABLED:
                from oracle_db import fetch_oracle_data
                from utils.oracle_agg import ora_by_machine
                if not areas or any(a in ('ISO', 'FS') for a in areas):
                    ora_df = fetch_oracle_data(start_date, end_date, areas, shift)
                    if ora_df is not None:
                        df = pd.concat([df, ora_by_machine(ora_df)], ignore_index=True)
        except Exception:
            pass
    except Exception as e:
        return html.Div(f"Database error: {e}", style={'color': RED, 'padding': '20px'})

    if df.empty:
        return html.Div("No data for selected filters.",
                        style={'color': MED_GRAY, 'padding': '20px'})

    # ── Calendar-based available time per machine ─────────────────────────────
    mach_avail = _calc_available_min(start_date, end_date, shift, 1)  # 1 machine

    # ── Pivot to one row per machine ──────────────────────────────────────────
    pivot = df.groupby(['machine_id', 'area']).apply(
        lambda g: pd.Series({
            'down_min': g[g['job_type'].isin(DOWN_TYPES)]['total_min'].sum(),
            'pm_min':   g[g['job_type'].isin(PM_TYPES)]['total_min'].sum(),
            'lost_min': g[g['job_type'].isin(LOST_TYPES)]['total_min'].sum()
                       + g['wait_min'].sum(),
        }), include_groups=False
    ).reset_index()

    av = max(mach_avail, 1)
    pivot['util']  = (100 - (pivot['down_min'] + pivot['pm_min'] + pivot['lost_min']) / av * 100).clip(lower=0).round(2)
    pivot['down']  = (pivot['down_min'] / av * 100).round(2)
    pivot['pm']    = (pivot['pm_min']   / av * 100).round(2)
    pivot['lost']  = (pivot['lost_min'] / av * 100).round(2)

    from dash import dash_table

    result = (pivot[['machine_id', 'area', 'util', 'down', 'pm', 'lost']]
              .sort_values('util')
              .head(100)
              .reset_index(drop=True))

    col_map = [
        {'name': 'Machine',       'id': 'machine_id'},
        {'name': 'Area',          'id': 'area'},
        {'name': 'Utilization %', 'id': 'util'},
        {'name': 'Downtime %',    'id': 'down'},
        {'name': 'PM %',          'id': 'pm'},
        {'name': 'Lost Time %',   'id': 'lost'},
    ]

    tbl = dash_table.DataTable(
        id='util-machine-datatable',
        columns=col_map,
        data=result.to_dict('records'),
        sort_action='native',
        sort_mode='multi',
        page_action='native',
        page_size=20,
        page_current=0,
        style_header={
            'backgroundColor': PRIMARY_BLUE,
            'color': '#FFFFFF',
            'fontWeight': '600',
            'fontSize': '12px',
            'padding': '11px 14px',
            'letterSpacing': '0.3px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
        style_cell={
            'fontSize': '13px',
            'padding': '9px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'textAlign': 'left',
            'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
        },
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            # Utilization green/orange/red
            {'if': {'filter_query': '{util} >= 80', 'column_id': 'util'},
             'color': GREEN, 'fontWeight': '700'},
            {'if': {'filter_query': '{util} >= 65 && {util} < 80', 'column_id': 'util'},
             'color': ORANGE, 'fontWeight': '700'},
            {'if': {'filter_query': '{util} < 65', 'column_id': 'util'},
             'color': RED, 'fontWeight': '700'},
            # Downtime red
            {'if': {'column_id': 'down'}, 'color': RED, 'fontWeight': '600'},
            # PM purple
            {'if': {'column_id': 'pm'}, 'color': PURPLE, 'fontWeight': '500'},
            # Lost Time orange
            {'if': {'column_id': 'lost'}, 'color': ORANGE, 'fontWeight': '500'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )
    footer = html.Div(
        f"{len(result)} machines · sortable · {len(result) // 20 + 1} pages",
        style={'fontSize': '11px', 'color': '#8A96A8',
               'marginTop': '8px', 'textAlign': 'right'},
    )
    return html.Div([tbl, footer])


# ── Export CSV callback ───────────────────────────────────────────────────────
@callback(
    Output('download-machine-csv', 'data'),
    Input('btn-export-csv', 'n_clicks'),
    State('util-machine-datatable', 'data'),
    prevent_initial_call=True,
)
def export_csv(n_clicks, table_data):
    if not table_data:
        return None
    import pandas as pd
    df = pd.DataFrame(table_data)
    col_rename = {
        'machine_id': 'Machine', 'area': 'Area',
        'util': 'Utilization %', 'down': 'Downtime %',
        'pm': 'PM %', 'lost': 'Lost Time %',
    }
    df = df.rename(columns=col_rename)
    return dcc.send_data_frame(df.to_csv, 'machine_breakdown.csv', index=False)


# ── Tertiary callback: Top 10 Attention List ─────────────────────────────────
@callback(
    Output('util-attention-list', 'children'),
    Input('auto-refresh',      'n_intervals'),
    Input('filter-date-range', 'start_date'),
    Input('filter-date-range', 'end_date'),
    Input('util-area-toggle',  'value'),
    Input('util-filter-shift', 'value'),
    Input('util-month-click',  'data'),
)
def update_attention_list(n_intervals, start_date, end_date, areas, shift,
                          selected_month):
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import build_util_where, util_attention_machines

    sc      = COLUMN_MAP.get('status',          'job_type')     or 'job_type'
    opr_tc  = COLUMN_MAP.get('opr_start_time',  'datex')        or 'datex'
    tech_tc = COLUMN_MAP.get('tech_start_time', 'date_ack')     or 'date_ack'
    ec      = COLUMN_MAP.get('end_time',        'date_close')   or 'date_close'
    ac      = COLUMN_MAP.get('machine_area',    'id_operation') or 'id_operation'
    mid     = COLUMN_MAP.get('machine_id',      'code_machine') or 'code_machine'

    if selected_month:
        from calendar import monthrange
        yr, mo = int(selected_month[:4]), int(selected_month[5:7])
        start_date = f"{yr}-{mo:02d}-01"
        end_date = f"{yr}-{mo:02d}-{monthrange(yr, mo)[1]}"

    where, params = build_util_where(opr_tc, ec, ac, start_date, end_date, areas, shift)

    # ── Phase 3: try API first, fallback to DB ────────────────────────────────
    api_used = False
    try:
        from api_client import USE_API, fetch_utilization_attention
        if USE_API:
            df = fetch_utilization_attention(start_date, end_date, areas, shift)
            api_used = True
    except Exception as _api_err:
        import logging
        logging.warning(f"attention API failed ({_api_err}), fallback to DB")
        api_used = False

    try:
        if not api_used:
            df = query_df(util_attention_machines(
                VIEW_NAME, opr_tc, tech_tc, ec, sc, ac, mid, where), params)
            # Merge Oracle (skip when API already did)
            try:
                from config import ORA_ENABLED
                if ORA_ENABLED:
                    from oracle_db import fetch_oracle_data
                    from utils.oracle_agg import ora_attention_machines
                    if not areas or any(a in ('ISO', 'FS') for a in areas):
                        import pandas as pd
                        ora_df = fetch_oracle_data(start_date, end_date, areas, shift)
                        if ora_df is not None:
                            df = pd.concat([df, ora_attention_machines(ora_df)],
                                           ignore_index=True)
                            df = df.nlargest(10, 'score').reset_index(drop=True)
            except Exception:
                pass
    except Exception as e:
        return html.Div(f"Error: {e}", style={'color': RED, 'padding': '16px'})

    if df.empty:
        return html.Div("No M/C DOWN events in selected period.",
                        style={'color': MED_GRAY, 'padding': '20px'})

    def rank_badge(rank):
        if rank <= 3:   bg = RED
        elif rank <= 7: bg = ORANGE
        else:           bg = '#E0A800'
        return html.Span(f"#{rank}", style={
            'background': bg, 'color': '#fff',
            'padding': '2px 8px', 'borderRadius': '10px',
            'fontSize': '11px', 'fontWeight': '700',
        })

    TH = {'padding': '9px 12px', 'textAlign': 'left', 'fontSize': '11px',
          'fontWeight': '600', 'color': '#fff', 'letterSpacing': '0.3px',
          'backgroundColor': PRIMARY_BLUE}
    TD = {'padding': '9px 12px', 'fontSize': '12px',
          'borderBottom': '1px solid #EEF0F4'}

    header = html.Tr([
        html.Th("Rank",        style=TH),
        html.Th("Machine",     style=TH),
        html.Th("Area",        style=TH),
        html.Th("Down Hrs",    style=TH),
        html.Th("Events",      style=TH),
        html.Th("Avg MTTR",    style=TH),
        html.Th("Score",       style=TH),
    ])

    rows = []
    for i, row in df.iterrows():
        rank = i + 1
        bg = '#FAFBFC' if rank % 2 == 0 else '#FFFFFF'
        rows.append(html.Tr([
            html.Td(rank_badge(rank), style={**TD, 'textAlign': 'center'}),
            html.Td(str(row['machine_id']), style={**TD, 'fontWeight': '500',
                                                    'color': '#1A1F2E'}),
            html.Td(str(row['area']),       style={**TD, 'color': '#8A96A8'}),
            html.Td(f"{row['down_hours']:.1f} h",  style={**TD, 'color': RED,    'fontWeight': '600'}),
            html.Td(str(int(row['event_count'])),   style={**TD, 'color': ORANGE, 'fontWeight': '500'}),
            html.Td(f"{row['avg_mttr_min']:.0f} m", style={**TD, 'color': PURPLE, 'fontWeight': '500'}),
            html.Td(f"{row['score']:.1f}",          style={**TD, 'color': '#1A1F2E', 'fontWeight': '600'}),
        ], style={'backgroundColor': bg, 'transition': 'background 0.15s'}))

    return html.Div(
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse',
                          'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif'}),
        style={'overflowX': 'auto', 'borderRadius': '6px',
               'border': '1px solid #E2E6ED'},
    )


# ── Fix missing import ────────────────────────────────────────────────────────
import pandas as pd
