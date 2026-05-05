"""Overview page — Factory Pulse. Live status from dbo.job_list."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from components.header import make_page_header, make_chart_title
from components.kpi_card import make_kpi_card
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    MED_GRAY, WHITE,
)

dash.register_page(__name__, path='/', name='Overview')

layout = html.Div([
    make_page_header("Machine Status Overview"),

    # Area filter (checkbox row like ASO)
    html.Div([
        dbc.Checklist(
            id='overview-area-filter',
            options=[],  # populated by callback
            value=[],    # empty = all areas
            inline=True,
            style={'fontSize': '13px', 'fontWeight': '500'},
            className='g-2',
        ),
    ], className='filter-bar', style={'padding': '10px 20px'}),

    # KPI cards
    dbc.Row(id='overview-kpi-row', className='g-3 mb-3'),

    # Status matrix + Donut
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Status Matrix", "Live"),
                html.Div(id='overview-matrix'),
            ], className='chart-card'),
        ], lg=7, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Current Status", "Live"),
                dcc.Graph(id='overview-donut', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=5, md=12),
    ]),

    # Open jobs list
    html.Div([
        html.Div([
            html.Span("Open Jobs — Waiting & On Process", style={
                'fontSize': '14px', 'fontWeight': '600', 'color': 'var(--text)'}),
            html.Div([
                dcc.Dropdown(
                    id='overview-jobtype-filter',
                options=[
                    {'label': 'All Types',           'value': 'ALL'},
                    {'label': 'M/C DOWN',            'value': 'M/C DOWN'},
                    {'label': 'SETUP',               'value': 'SETUP'},
                    {'label': 'SETUP BY OPERATOR',   'value': 'SETUP BY OPERATOR'},
                    {'label': 'PM',                  'value': 'PM'},
                    {'label': 'CONVERT',             'value': 'CONVERT'},
                ],
                    value='ALL', clearable=False,
                    style={'fontSize': '13px', 'width': '220px'},
                ),
                html.Button([
                    html.Span("⬇", style={'marginRight': '5px'}), "CSV",
                ], id='btn-overview-export', style={
                    'background': PRIMARY_BLUE, 'color': '#fff', 'border': 'none',
                    'borderRadius': '6px', 'padding': '5px 12px', 'fontSize': '12px',
                    'fontWeight': '600', 'cursor': 'pointer', 'marginLeft': '10px',
                    'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                }),
            ], style={'display': 'flex', 'alignItems': 'center'}),
        ], style={'display': 'flex', 'justifyContent': 'space-between',
                  'alignItems': 'center', 'marginBottom': '12px',
                  'paddingBottom': '10px', 'borderBottom': '1px solid var(--divider)'}),
        dcc.Download(id='overview-download-csv'),
        html.Div(id='overview-open-jobs'),
    ], className='chart-card'),

    # Refresh info
    html.Div(id='overview-refresh-time', className='refresh-info'),

], className='page-container')


def _empty():
    fig = go.Figure()
    fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Calibri, Segoe UI, sans-serif'))
    return fig


def _format_elapsed(minutes):
    """Convert minutes to human-readable Xh Ym."""
    if pd.isna(minutes) or minutes <= 0:
        return '0m'
    h = int(minutes) // 60
    m = int(minutes) % 60
    if h > 0:
        return f'{h}h {m}m'
    return f'{m}m'


# Load area options for checkbox filter
@callback(
    Output('overview-area-filter', 'options'),
    Input('auto-refresh', 'n_intervals'),
)
def load_area_options(n):
    from db import query_df
    from config import MACHINE_AREAS, ORA_ENABLED
    try:
        df = query_df("""
            SELECT DISTINCT id_operation AS area
            FROM [dbo].[job_list]
            WHERE id_operation IS NOT NULL AND id_operation != ''
        """)
        areas = df['area'].tolist()
        if ORA_ENABLED:
            for a in ('ISO', 'FS'):
                if a not in areas:
                    areas.append(a)
        order = {a: i for i, a in enumerate(MACHINE_AREAS)}
        areas = sorted(areas, key=lambda a: order.get(a, 999))
        return [{'label': f'  {a}', 'value': a} for a in areas]
    except Exception:
        return []


@callback(
    Output('overview-kpi-row',     'children'),
    Output('overview-matrix',      'children'),
    Output('overview-donut',       'figure'),
    Output('overview-open-jobs',   'children'),
    Output('overview-refresh-time','children'),
    Input('auto-refresh', 'n_intervals'),
    Input('overview-area-filter', 'value'),
    Input('overview-jobtype-filter', 'value'),
)
def update_overview(n_intervals, selected_areas, jobtype_filter):
    from db import query_df
    from utils.queries import overview_status_matrix, overview_open_jobs, overview_kpi_summary

    # ── Phase 3: try middleware API first (fallback to direct DB on failure) ──
    api_used = False
    try:
        from api_client import USE_API, fetch_overview, fetch_open_jobs, overview_to_dataframes
        if USE_API:
            data = fetch_overview(selected_areas)
            matrix_df, kpi_dict = overview_to_dataframes(data)
            kpi_df = pd.DataFrame([kpi_dict])
            open_df = fetch_open_jobs(selected_areas, jobtype_filter)
            ora_kpi_extra = {'waiting': 0, 'on_process': 0, 'down': 0,
                             'closed_shift': 0, 'machines': 0}
            api_used = True
    except Exception as api_err:
        import logging
        logging.warning(f"API overview failed ({api_err}), falling back to direct DB")
        api_used = False

    try:
        if not api_used:
            matrix_df = query_df(overview_status_matrix())
            open_df   = query_df(overview_open_jobs())
            kpi_df    = query_df(overview_kpi_summary())

            ora_kpi_extra = {'waiting': 0, 'on_process': 0, 'down': 0,
                             'closed_shift': 0, 'machines': 0}

        # Apply area filter (SQL Server only — Oracle merged after)
        # Skip when api_used: API already applied the filter + merged Oracle.
        if not api_used and selected_areas:
            # Strip Oracle-only areas from SQL Server query
            from utils.queries import ORACLE_ONLY_AREAS
            sql_areas = [a for a in selected_areas if a not in ORACLE_ONLY_AREAS]
            open_df = open_df[open_df['area'].isin(selected_areas)]

            if sql_areas:
                area_in = ', '.join(f"'{a}'" for a in sql_areas)
                matrix_df = query_df(f"""
                SELECT job_type,
                       SUM(CASE WHEN date_ack IS NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS waiting,
                       SUM(CASE WHEN date_ack IS NOT NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS on_process,
                       SUM(CASE WHEN date_close IS NOT NULL THEN 1 ELSE 0 END) AS closed,
                       COUNT(*) AS total
                FROM [dbo].[job_list]
                WHERE code_machine IS NOT NULL AND code_machine != ''
                  AND id_operation IN ({area_in})
                GROUP BY job_type ORDER BY total DESC
                """)
                kpi_df = query_df(f"""
                SELECT
                    (SELECT
                        (SELECT COUNT(*) FROM dbo.machine
                         WHERE id_operation IN ({area_in}) AND id_operation != 'WB'
                         AND flag_key = 1 AND ISNULL(flag_delete,0) != 1)
                        +
                        CASE WHEN 'WB' IN ({area_in}) THEN
                        (SELECT COUNT(*) FROM dbo.machine a
                         WHERE a.id_operation = 'WB' AND a.flag_key = 1
                         AND ISNULL(a.flag_delete,0) != 1
                         AND a.code_machine NOT LIKE '%[LR]'
                         AND NOT EXISTS (SELECT 1 FROM dbo.machine b
                             WHERE b.id_operation = 'WB'
                             AND (b.code_machine = a.code_machine + 'L'
                                  OR b.code_machine = a.code_machine + 'R')))
                        +
                        (SELECT COUNT(*) FROM dbo.machine a
                         WHERE a.id_operation = 'WB'
                         AND ISNULL(a.flag_delete,0) != 1
                         AND a.code_machine LIKE '%[LR]'
                         AND EXISTS (SELECT 1 FROM dbo.machine b
                             WHERE b.id_operation = 'WB' AND b.flag_key = 1
                             AND b.code_machine = LEFT(a.code_machine, LEN(a.code_machine)-1)))
                        ELSE 0 END
                    ) AS total_key_machines,
                    (SELECT COUNT(*) FROM [dbo].[job_list]
                     WHERE date_close IS NULL AND code_machine != ''
                     AND date_ack IS NULL AND id_operation IN ({area_in})) AS waiting_count,
                    (SELECT COUNT(*) FROM [dbo].[job_list]
                     WHERE date_close IS NULL AND code_machine != ''
                     AND date_ack IS NOT NULL AND id_operation IN ({area_in})) AS on_process_count,
                    (SELECT COUNT(*) FROM [dbo].[job_list]
                     WHERE date_close IS NULL AND code_machine != ''
                     AND job_type = 'M/C DOWN' AND id_operation IN ({area_in})) AS down_count,
                    (SELECT COUNT(*) FROM [dbo].[job_list]
                     WHERE date_close IS NOT NULL AND code_machine != ''
                     AND LEN(code_machine) > 3
                     AND id_operation IN ({area_in})
                     AND date_close >= CASE
                         WHEN DATEPART(HOUR, GETDATE()) BETWEEN 7 AND 18
                         THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '07:00'
                         WHEN DATEPART(HOUR, GETDATE()) >= 19
                         THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '19:00'
                         ELSE CAST(DATEADD(DAY, -1, CAST(GETDATE() AS DATE)) AS DATETIME) + '19:00'
                     END) AS closed_this_shift
                """)
            else:
                # Only Oracle areas selected — empty SQL Server results
                matrix_df = pd.DataFrame(columns=['job_type', 'waiting', 'on_process', 'closed', 'total'])
                kpi_df = pd.DataFrame([{
                    'total_key_machines': 0, 'waiting_count': 0,
                    'on_process_count': 0, 'down_count': 0, 'closed_this_shift': 0
                }])

        # ── Merge Oracle ISO/FS live data (AFTER area filter) ─────────────────
        # Skip when api_used: API has already merged Oracle.
        try:
            from config import ORA_ENABLED
            if not api_used and ORA_ENABLED:
                # KEY Machines count comes from dbo.machine master (same source
                # as Inventory page) — runs regardless of whether there are
                # live events today. Honours the user's area filter.
                try:
                    from utils.queries import oracle_key_machine_count
                    _ora_key = query_df(oracle_key_machine_count(selected_areas))
                    ora_kpi_extra['machines'] = (int(_ora_key['key_machines'].iloc[0])
                                                 if not _ora_key.empty else 0)
                except Exception as _mc_err:
                    import logging
                    logging.warning(f"Oracle KEY machine count failed: {_mc_err}")
                    ora_kpi_extra['machines'] = 0

                from oracle_db import fetch_oracle_live_status
                ora_live = fetch_oracle_live_status(selected_areas)
                if ora_live is not None:
                    # Matrix
                    ora_matrix = ora_live.groupby('job_type').agg(
                        waiting=('status', lambda x: (x == 'Waiting').sum()),
                        on_process=('status', lambda x: (x == 'On Process').sum()),
                        closed=('status', lambda x: (x == 'Closed').sum()),
                    ).reset_index()
                    ora_matrix['total'] = (ora_matrix['waiting']
                                           + ora_matrix['on_process']
                                           + ora_matrix['closed'])
                    matrix_df = pd.concat([matrix_df, ora_matrix], ignore_index=True)
                    matrix_df = (matrix_df.groupby('job_type')
                                 .agg({'waiting': 'sum', 'on_process': 'sum',
                                       'closed': 'sum', 'total': 'sum'})
                                 .reset_index()
                                 .sort_values('total', ascending=False))

                    # Open jobs
                    ora_open = ora_live[ora_live['status'] != 'Closed'].copy()
                    if not ora_open.empty:
                        open_df = pd.concat([open_df, ora_open], ignore_index=True)

                    # KPI extra counts from live events (status-based)
                    ora_kpi_extra['waiting'] = int((ora_live['status'] == 'Waiting').sum())
                    ora_kpi_extra['on_process'] = int((ora_live['status'] == 'On Process').sum())
                    ora_kpi_extra['down'] = int(
                        ((ora_live['status'] == 'On Process')
                         & (ora_live['job_type'] == 'M/C DOWN')).sum())
                    from datetime import datetime as _dt
                    now = _dt.now()
                    if now.hour >= 7 and now.hour <= 18:
                        shift_start = now.replace(hour=7, minute=0, second=0)
                    elif now.hour >= 19:
                        shift_start = now.replace(hour=19, minute=0, second=0)
                    else:
                        from datetime import timedelta
                        shift_start = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0)
                    closed_ora = ora_live[
                        (ora_live['status'] == 'Closed')
                        & (ora_live['date_close'] >= shift_start)]
                    ora_kpi_extra['closed_shift'] = len(closed_ora)
        except Exception as ora_err:
            import logging
            logging.warning(f"Oracle Overview merge failed: {ora_err}")

    except Exception as e:
        err = html.Div(f"Error: {e}", style={'color': RED, 'padding': '16px'})
        return [err], err, _empty(), err, f"Error at {datetime.now():%H:%M:%S}"

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    kpi = kpi_df.iloc[0] if not kpi_df.empty else {}
    total_machines = int(kpi.get('total_key_machines', 0)) + ora_kpi_extra['machines']
    waiting        = int(kpi.get('waiting_count', 0))      + ora_kpi_extra['waiting']
    on_process     = int(kpi.get('on_process_count', 0))   + ora_kpi_extra['on_process']
    down           = int(kpi.get('down_count', 0))         + ora_kpi_extra['down']
    closed_today   = int(kpi.get('closed_this_shift', 0))  + ora_kpi_extra['closed_shift']
    running        = max(0, total_machines - waiting - on_process)

    kpis = [
        dbc.Col(make_kpi_card(total_machines, "KEY Machines", PRIMARY_BLUE, icon="⚙"),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(running, "Running", GREEN, icon="✅",
                              subtitle=f"{running/max(total_machines,1)*100:.0f}% of fleet"),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(down, "M/C Down", RED, icon="🔴",
                              subtitle="Waiting + On Process"),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(waiting, "Waiting for Tech", ORANGE, icon="⏳",
                              subtitle="No tech assigned"),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(on_process, "On Process", LIGHT_BLUE, icon="🔧",
                              subtitle="Tech repairing"),
                lg=2, md=4, sm=6),
        dbc.Col(make_kpi_card(closed_today, "Closed This Shift", '#2E9E4F', icon="✓"),
                lg=2, md=4, sm=6),
    ]

    # ── Status Matrix Table ───────────────────────────────────────────────────
    if not matrix_df.empty:
        matrix_df = matrix_df.fillna('')
        # Add totals row
        totals = pd.DataFrame([{
            'job_type': 'TOTAL',
            'waiting': matrix_df['waiting'].sum(),
            'on_process': matrix_df['on_process'].sum(),
            'closed': matrix_df['closed'].sum(),
            'total': matrix_df['total'].sum(),
        }])
        matrix_display = pd.concat([matrix_df, totals], ignore_index=True)
        matrix_display.columns = ['Job Type', 'Waiting', 'On Process', 'Closed', 'Total']

        matrix_table = dash_table.DataTable(
            columns=[{'name': c, 'id': c} for c in matrix_display.columns],
            data=matrix_display.to_dict('records'),
            style_header={
                'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
                'fontWeight': '600', 'fontSize': '12px', 'padding': '10px 14px',
                'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            },
            style_cell={
                'fontSize': '13px', 'padding': '8px 14px',
                'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                'textAlign': 'center', 'border': 'none',
                'borderBottom': '1px solid #EEF0F4',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'Job Type'}, 'textAlign': 'left', 'fontWeight': '600'},
            ],
            style_data={'color': '#1A1F2E'},
            style_data_conditional=[
                {'if': {'row_index': len(matrix_display) - 1},
                 'fontWeight': '700', 'backgroundColor': '#F0F2F5',
                 'borderTop': '2px solid ' + PRIMARY_BLUE},
                {'if': {'column_id': 'Waiting', 'filter_query': '{Waiting} > 0'},
                 'color': ORANGE, 'fontWeight': '700'},
                {'if': {'column_id': 'On Process', 'filter_query': '{On Process} > 0'},
                 'color': LIGHT_BLUE, 'fontWeight': '600'},
            ],
            style_table={'borderRadius': '6px'},
            style_as_list_view=True,
        )
    else:
        matrix_table = html.Div("No data", style={'color': MED_GRAY, 'padding': '16px'})

    # ── Status Donut ──────────────────────────────────────────────────────────
    donut = go.Figure()
    labels = ['Running', 'M/C Down', 'Lost Time', 'PM', 'Other']
    # Lost time = SETUP variants + CONVERT + CLEAN MOLD + CHANGE CAP +
    # FACILITY DOWN + ENGINEERING DOWN (matches LOST_TYPES in utilization page).
    LOST_JOB_TYPES = ['SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD',
                      'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN']
    lost_open = len(open_df[open_df['job_type'].isin(LOST_JOB_TYPES)])
    pm_open   = len(open_df[open_df['job_type'] == 'PM'])
    other_open = len(open_df) - down - lost_open - pm_open
    values = [running, down, lost_open, pm_open, max(0, other_open)]
    colors = [GREEN, RED, ORANGE, PURPLE, MED_GRAY]

    donut.add_trace(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker_colors=colors,
        textinfo='label+value',
        textfont_size=12,
        hovertemplate='%{label}: %{value} machines<extra></extra>',
    ))
    donut.update_layout(
        template='plotly_white', height=320,
        margin=dict(t=10, b=40, l=10, r=10),
        showlegend=True,
        legend=dict(orientation='h', y=-0.1, font=dict(size=11)),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
        annotations=[dict(text=f"<b>{total_machines}</b><br>machines",
                          x=0.5, y=0.5, showarrow=False,
                          font=dict(size=16, color=PRIMARY_BLUE))],
    )

    # ── Open Jobs List ────────────────────────────────────────────────────────
    if not open_df.empty:
        # Apply job type filter
        if jobtype_filter and jobtype_filter != 'ALL':
            open_df = open_df[open_df['job_type'] == jobtype_filter]

        display_df = open_df.copy()
        display_df['wait_display']   = display_df['wait_min'].apply(_format_elapsed)
        display_df['repair_display'] = display_df['repair_min'].apply(_format_elapsed)
        display_df['time'] = pd.to_datetime(display_df['datex']).dt.strftime('%H:%M')
        display_df = display_df.fillna('—')
        display_df = display_df[['code_machine', 'area', 'job_type', 'des_job',
                                  'die_mask', 'package_type', 'wire_type',
                                  'time', 'wait_display', 'repair_display',
                                  'tech', 'status']]
        display_df.columns = ['Machine', 'Area', 'Type', 'Description',
                               'Die Mask', 'Package', 'Wire Type',
                               'Opened', 'Wait', 'Repair', 'Tech', 'Status']

        # Status color styling
        status_colors = {
            'Waiting':    {'color': ORANGE, 'fontWeight': '700'},
            'On Process': {'color': LIGHT_BLUE, 'fontWeight': '600'},
        }

        style_cond = [
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            # Status text color
            {'if': {'filter_query': '{Status} = "Waiting"', 'column_id': 'Status'},
             'color': ORANGE, 'fontWeight': '700'},
            {'if': {'filter_query': '{Status} = "On Process"', 'column_id': 'Status'},
             'color': LIGHT_BLUE, 'fontWeight': '700'},
            # M/C DOWN left border indicator only (no row background)
            {'if': {'filter_query': '{Type} = "M/C DOWN" && {Status} = "Waiting"'},
             'borderLeft': f'3px solid {RED}'},
            {'if': {'filter_query': '{Type} = "M/C DOWN" && {Status} = "On Process"'},
             'borderLeft': f'3px solid {LIGHT_BLUE}'},
            # Type column color
            {'if': {'filter_query': '{Type} = "M/C DOWN"', 'column_id': 'Type'},
             'color': RED, 'fontWeight': '700'},
            {'if': {'filter_query': '{Type} = "SETUP"', 'column_id': 'Type'},
             'color': LIGHT_BLUE, 'fontWeight': '600'},
            {'if': {'filter_query': '{Type} = "CONVERT"', 'column_id': 'Type'},
             'color': PURPLE, 'fontWeight': '600'},
            {'if': {'filter_query': '{Type} = "PM"', 'column_id': 'Type'},
             'color': PURPLE, 'fontWeight': '600'},
            # Time columns
            {'if': {'column_id': 'Wait'}, 'color': ORANGE, 'fontWeight': '700',
             'textAlign': 'center'},
            {'if': {'column_id': 'Repair'}, 'color': LIGHT_BLUE, 'fontWeight': '600',
             'textAlign': 'center'},
            {'if': {'column_id': 'Opened'}, 'textAlign': 'center'},
            # Tech
            {'if': {'column_id': 'Tech'}, 'color': PURPLE, 'fontWeight': '500',
             'textAlign': 'center'},
            # Machine bold
            {'if': {'column_id': 'Machine'}, 'fontWeight': '600'},
        ]

        jobs_table = dash_table.DataTable(
            columns=[{'name': c, 'id': c} for c in display_df.columns],
            data=display_df.to_dict('records'),
            sort_action='native', sort_mode='multi',
            page_action='native', page_size=20,
            style_header={
                'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
                'fontWeight': '600', 'fontSize': '11px', 'padding': '10px 12px',
                'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                'textAlign': 'center', 'whiteSpace': 'nowrap',
            },
            style_header_conditional=[
                {'if': {'column_id': 'Machine'}, 'textAlign': 'left'},
                {'if': {'column_id': 'Description'}, 'textAlign': 'left'},
                {'if': {'column_id': 'Type'}, 'textAlign': 'left'},
            ],
            style_cell={
                'fontSize': '12px', 'padding': '7px 10px',
                'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                'textAlign': 'left', 'border': 'none',
                'borderBottom': '1px solid #EEF0F4',
                'whiteSpace': 'nowrap', 'overflow': 'hidden',
                'textOverflow': 'ellipsis',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'Machine'},     'width': '100px', 'minWidth': '90px'},
                {'if': {'column_id': 'Area'},        'width': '55px',  'textAlign': 'center'},
                {'if': {'column_id': 'Type'},        'width': '90px'},
                {'if': {'column_id': 'Description'}, 'width': '180px', 'maxWidth': '200px'},
                {'if': {'column_id': 'Die Mask'},    'width': '65px',  'textAlign': 'center'},
                {'if': {'column_id': 'Package'},     'width': '110px', 'textAlign': 'center'},
                {'if': {'column_id': 'Wire Type'},   'width': '70px',  'textAlign': 'center'},
                {'if': {'column_id': 'Opened'},      'width': '60px'},
                {'if': {'column_id': 'Wait'},        'width': '70px'},
                {'if': {'column_id': 'Repair'},      'width': '70px'},
                {'if': {'column_id': 'Tech'},        'width': '65px'},
                {'if': {'column_id': 'Status'},      'width': '85px',  'textAlign': 'center'},
            ],
            style_data={'color': '#1A1F2E'},
            style_data_conditional=style_cond,
            style_table={'overflowX': 'auto', 'borderRadius': '6px'},
            style_as_list_view=True,
        )
        jobs_section = html.Div([
            html.Div(f"{len(open_df)} open jobs — {waiting} waiting, {on_process} on process",
                     style={'fontSize': '12px', 'color': MED_GRAY, 'marginBottom': '8px'}),
            jobs_table,
        ])
    else:
        jobs_section = html.Div("No open jobs — all machines running!",
                                style={'color': GREEN, 'padding': '20px',
                                       'fontWeight': '600', 'fontSize': '14px'})

    refresh = f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}"
    return kpis, matrix_table, donut, jobs_section, refresh


@callback(
    Output('overview-download-csv', 'data'),
    Input('btn-overview-export', 'n_clicks'),
    State('overview-area-filter', 'value'),
    State('overview-jobtype-filter', 'value'),
    prevent_initial_call=True,
)
def export_open_jobs(n_clicks, selected_areas, jobtype_filter):
    if not n_clicks:
        return None
    from db import query_df
    from utils.queries import overview_open_jobs
    df = query_df(overview_open_jobs())
    if selected_areas:
        df = df[df['area'].isin(selected_areas)]
    if jobtype_filter and jobtype_filter != 'ALL':
        df = df[df['job_type'] == jobtype_filter]
    df = df.fillna('')
    export = df[['code_machine', 'area', 'job_type', 'des_job',
                  'die_mask', 'package_type', 'wire_type',
                  'wait_min', 'repair_min', 'tech', 'status']].copy()
    export.columns = ['Machine', 'Area', 'Type', 'Description',
                       'Die Mask', 'Package', 'Wire Type',
                       'Wait (min)', 'Repair (min)', 'Tech', 'Status']
    return dcc.send_data_frame(export.to_csv, 'open_jobs.csv', index=False)
