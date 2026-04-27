"""Machine Detail page — drill-down with machine profile from dbo.machine."""
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from components.header import make_page_header, make_chart_title
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    MED_GRAY, WHITE, STATUS_COLORS,
)

dash.register_page(__name__, path='/machine-detail', name='Machine Detail')

layout = html.Div([
    make_page_header("Machine Detail"),

    # Selector bar
    html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Area", className='filter-label'),
                dcc.Dropdown(
                    id='detail-area-select',
                    options=[], value=None,
                    placeholder='All Areas',
                    style={'fontSize': '13px'},
                ),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("\u00a0", className='filter-label'),
                dbc.Checklist(
                    id='detail-key-toggle',
                    options=[{'label': '  KEY Machines Only', 'value': 'KEY'}],
                    value=['KEY'],
                    inline=True,
                    style={'fontSize': '13px', 'fontWeight': '600',
                           'color': PRIMARY_BLUE, 'paddingTop': '6px'},
                ),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Machine", className='filter-label'),
                dcc.Dropdown(
                    id='detail-machine-select',
                    options=[], value=None,
                    placeholder='Search machine...',
                    searchable=True, clearable=True,
                    style={'fontSize': '13px'},
                ),
            ], lg=6, md=6, sm=12),
        ], className='g-2 align-items-end'),
    ], className='filter-bar'),

    # Machine profile card (from dbo.machine)
    html.Div(id='detail-profile'),

    # KPI row
    dbc.Row(id='detail-status-banner', className='g-3 mb-3'),

    # Timeline chart
    html.Div([
        make_chart_title("Status Timeline", "Recent 200"),
        dcc.Graph(id='detail-timeline', config={'displayModeBar': False}),
    ], className='chart-card'),

    # Events table
    html.Div([
        make_chart_title("Recent Records"),
        html.Div(id='detail-table'),
    ], className='chart-card'),

], className='page-container')


# ── Area dropdown — from machine master table ─────────────────────────────────
@callback(
    Output('detail-area-select', 'options'),
    Input('detail-key-toggle', 'value'),
    Input('auto-refresh', 'n_intervals'),
)
def load_areas(key_toggle, n):
    from config import MACHINE_AREAS, MACHINE_TABLE
    key_only = bool(key_toggle and 'KEY' in key_toggle)

    # Try API first (Phase 3)
    try:
        from api_client import USE_API, fetch_areas
        if USE_API:
            rows = fetch_areas()
            # /areas already returns area + short_name + machine_count; filter key_only is approximate
            order = {a: i for i, a in enumerate(MACHINE_AREAS)}
            rows = sorted(rows, key=lambda r: order.get(r.get('area', ''), 999))
            return [{'label': f"{r.get('short_name') or r['area']} ({r['area']})",
                     'value': r['area']} for r in rows]
    except Exception as _api_err:
        import logging
        logging.warning(f"load_areas API failed ({_api_err}), fallback to DB")

    # Fallback: direct DB
    from db import query_df
    try:
        where = "WHERE [id_operation] IS NOT NULL AND [id_operation] != ''"
        if key_only:
            where += " AND [flag_key] = 1"
        df = query_df(f"""
            SELECT DISTINCT [id_operation] AS area, [short_name]
            FROM {MACHINE_TABLE}
            {where}
            ORDER BY [id_operation]
        """)
        order = {a: i for i, a in enumerate(MACHINE_AREAS)}
        rows = sorted(df.to_dict('records'),
                      key=lambda r: order.get(r['area'], 999))
        return [{'label': f"{r['short_name']} ({r['area']})",
                 'value': r['area']} for r in rows]
    except Exception:
        return []


# ── Machine dropdown — from machine master table ─────────────────────────────
@callback(
    Output('detail-machine-select', 'options'),
    Input('detail-area-select', 'value'),
    Input('detail-key-toggle', 'value'),
    Input('auto-refresh', 'n_intervals'),
)
def load_machines(area, key_toggle, n):
    key_only = bool(key_toggle and 'KEY' in key_toggle)

    # Try API first
    try:
        from api_client import USE_API, fetch_machine_list
        if USE_API:
            df = fetch_machine_list(area=area, key_only=key_only)
            return [{'label': f"{r['machine_id']} — {r['des_machine']}" if r.get('des_machine') else str(r['machine_id']),
                     'value': r['machine_id']} for _, r in df.iterrows()]
    except Exception as _api_err:
        import logging
        logging.warning(f"load_machines API failed ({_api_err}), fallback to DB")

    # Fallback: direct DB
    from db import query_df
    from utils.queries import distinct_machines_from_master
    try:
        params = {'area': area} if area else None
        df = query_df(distinct_machines_from_master(area_filter=area, key_only=key_only), params)
        return [{'label': f"{r['machine_id']} — {r['des_machine']}" if r.get('des_machine') else str(r['machine_id']),
                 'value': r['machine_id']} for _, r in df.iterrows()]
    except Exception:
        return []


# ── Machine profile card ──────────────────────────────────────────────────────
@callback(
    Output('detail-profile', 'children'),
    Input('detail-machine-select', 'value'),
)
def update_profile(machine_id):
    if not machine_id:
        return ""
    from components.machine_profile import make_machine_profile

    # Try API first — /machines/detail returns info + flags in data.info + data.flags
    try:
        from api_client import USE_API, fetch_machine_detail
        if USE_API:
            data = fetch_machine_detail(machine_id, recent_limit=1)
            info = data.get('info', {}) or {}
            if not info.get('machine_id'):
                return html.Div(f"Machine {machine_id} not found in master table.",
                                style={'color': MED_GRAY, 'padding': '12px'})
            # make_machine_profile expects dict w/ code_machine, des_machine, mfg, model,
            # sn, id_operation, short_name, date_install, flag_* columns
            flags = data.get('flags', {}) or {}
            profile = {
                'code_machine': info.get('machine_id'),
                'des_machine': info.get('des_machine'),
                'mfg': info.get('mfg'),
                'model': info.get('model'),
                'sn': info.get('sn'),
                'id_operation': info.get('area'),
                'short_name': info.get('short_name'),
                'date_install': data.get('date_install'),
                'flag_key': flags.get('key', 0),
                'flag_automotive': flags.get('automotive', 0),
                'flag_gold': flags.get('gold', 0),
                'flag_pm': flags.get('pm', 0),
                'flag_downtime': flags.get('downtime', 0),
            }
            return make_machine_profile(profile)
    except Exception as _api_err:
        import logging
        logging.warning(f"update_profile API failed ({_api_err}), fallback to DB")

    # Fallback: direct DB
    from db import query_df
    from utils.queries import machine_master_info
    try:
        df = query_df(machine_master_info(), {'machine_id': machine_id})
        if df.empty:
            return html.Div(f"Machine {machine_id} not found in master table.",
                            style={'color': MED_GRAY, 'padding': '12px'})
        return make_machine_profile(df.iloc[0].to_dict())
    except Exception:
        return ""


# ── KPI + Timeline + Table ────────────────────────────────────────────────────
@callback(
    Output('detail-status-banner', 'children'),
    Output('detail-timeline', 'figure'),
    Output('detail-table', 'children'),
    Input('detail-machine-select', 'value'),
    Input('auto-refresh', 'n_intervals'),
)
def update_detail(machine_id, n):
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from components.data_table import make_data_table
    from components.kpi_card import make_kpi_card
    from utils.queries import machine_downtime_kpis

    empty_fig = go.Figure()
    empty_fig.update_layout(template='plotly_white',
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            height=250, font=dict(family='Calibri, Segoe UI, sans-serif'),
                            xaxis=dict(visible=False), yaxis=dict(visible=False))
    empty_fig.add_annotation(text="Select a machine to view timeline",
                             showarrow=False, font=dict(size=14, color=MED_GRAY),
                             xref='paper', yref='paper', x=0.5, y=0.5)

    if not machine_id:
        msg = html.Div("Select a machine to view details.",
                        style={'color': MED_GRAY, 'padding': '20px'})
        return [], empty_fig, msg

    mid_col    = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'
    status_col = COLUMN_MAP.get('status',     'job_type')     or 'job_type'
    time_col   = COLUMN_MAP.get('opr_start_time', 'datex')    or 'datex'

    # Try API first
    api_used = False
    try:
        from api_client import USE_API, fetch_machine_records, fetch_machine_detail
        if USE_API:
            df = fetch_machine_records(machine_id, limit=200)
            detail = fetch_machine_detail(machine_id, recent_limit=1)
            k = detail.get('kpis', {}) or {}
            import pandas as _pd
            kpi_df = _pd.DataFrame([{
                'total_events': k.get('total_events') or 0,
                'down_events': k.get('down_events') or 0,
                'avg_mttr_min': k.get('avg_mttr_min') or 0,
                'total_down_hrs': k.get('total_down_hrs') or 0,
                'avg_wait_min': k.get('avg_wait_min') or 0,
            }])
            api_used = True
    except Exception as _api_err:
        import logging
        logging.warning(f"update_detail API failed ({_api_err}), fallback to DB")
        api_used = False

    if not api_used:
        try:
            # Recent records
            df = query_df(f"""
                SELECT TOP 200 *
                FROM {VIEW_NAME}
                WHERE [{mid_col}] = :machine_id
                ORDER BY [{time_col}] DESC
            """, {'machine_id': machine_id})

            # Downtime KPIs
            kpi_df = query_df(machine_downtime_kpis(), {'machine_id': machine_id})
        except Exception as e:
            err = html.Div(f"Error: {e}", style={'color': RED, 'padding': '20px'})
            return [err], empty_fig, err

    if df.empty:
        msg = html.Div(f"No operational records for {machine_id}.",
                        style={'color': MED_GRAY, 'padding': '20px'})
        return [], empty_fig, msg

    # ── KPI cards ─────────────────────────────────────────────────────────────
    total_records = len(df)
    latest_status = str(df.iloc[0].get(status_col, '—')).strip() if status_col in df.columns else '—'
    status_color  = STATUS_COLORS.get(latest_status, MED_GRAY)

    kpis = [
        dbc.Col(make_kpi_card(latest_status, "Latest Status", status_color),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(total_records, "Records (200)", PRIMARY_BLUE),
                lg=2, md=4, sm=6),
    ]

    if not kpi_df.empty:
        row = kpi_df.iloc[0]
        down_evts = int(row['down_events'] or 0)
        mttr      = int(row['avg_mttr_min'] or 0)
        down_hrs  = float(row['total_down_hrs'] or 0)
        avg_wait  = int(row['avg_wait_min'] or 0)
        kpis += [
            dbc.Col(make_kpi_card(down_evts, "Down Events", RED, icon="⛔"),
                    lg=2, md=4, sm=6),
            dbc.Col(make_kpi_card(mttr, "Avg MTTR", RED, unit="min",
                                  subtitle="Mean Time To Repair", icon="🔧"),
                    lg=2, md=4, sm=6),
            dbc.Col(make_kpi_card(f"{down_hrs:.1f}", "Total Downtime", ORANGE,
                                  unit="hrs", icon="⏱"),
                    lg=2, md=4, sm=6),
            dbc.Col(make_kpi_card(avg_wait, "Avg Wait", ORANGE, unit="min",
                                  subtitle="Response Time", icon="⏳"),
                    lg=2, md=4, sm=6),
        ]

    # ── Timeline chart ────────────────────────────────────────────────────────
    timeline_fig = go.Figure()
    if time_col in df.columns and status_col in df.columns:
        df_sorted = df.sort_values(time_col)
        for status_val in df_sorted[status_col].unique():
            mask = df_sorted[status_col] == status_val
            color = STATUS_COLORS.get(str(status_val).strip(), MED_GRAY)
            timeline_fig.add_trace(go.Scatter(
                x=df_sorted.loc[mask, time_col],
                y=[str(status_val)] * mask.sum(),
                mode='markers',
                marker=dict(color=color, size=8, symbol='square'),
                name=str(status_val),
                hovertemplate='%{x}<extra>%{fullData.name}</extra>',
            ))
    timeline_fig.update_layout(
        template='plotly_white', height=200,
        margin=dict(t=10, b=30, l=80, r=10),
        showlegend=True,
        legend=dict(orientation='h', y=-0.3),
        xaxis_title=None, yaxis_title=None,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Data table ────────────────────────────────────────────────────────────
    display_cols = [c for c in df.columns if not c.startswith('_')][:12]
    table = make_data_table(df[display_cols].head(50), 'detail-records-table',
                            page_size=15, status_col=status_col)

    return kpis, timeline_fig, table
