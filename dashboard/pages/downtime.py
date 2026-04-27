"""Downtime & Setup Analysis page.
Two parallel callback sections: M/C DOWN (Downtime) and SETUP.
"""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from components.header import make_page_header, make_chart_title
from components.filters import make_filter_bar
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    MED_GRAY, WHITE, CHART_COLORS,
)

dash.register_page(__name__, path='/downtime', name='Downtime & Setup')

# ── Shared helpers ────────────────────────────────────────────────────────────
def _build_where(otc, ec, sc, ac, mid, start_date, end_date, areas, machines,
                 shift, job_types):
    """Build WHERE clause + params for the given job_types list."""
    from utils.queries import ORACLE_ONLY_AREAS
    # Strip Oracle-only areas from SQL Server query
    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else areas
    if areas and not sql_areas:
        return "WHERE 1=0", {}

    phs_jt = ', '.join(f"'{j}'" for j in job_types)
    clauses = [f"[{sc}] IN ({phs_jt})"]
    params = {}
    if start_date:
        clauses.append(f"[{otc}] >= :start_date"); params['start_date'] = start_date
    if end_date:
        clauses.append(f"[{otc}] < DATEADD(DAY, 1, CAST(:end_date AS DATE))"); params['end_date'] = end_date
    if sql_areas:
        phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
        clauses.append(f"[{ac}] IN ({phs})")
        for i, a in enumerate(sql_areas): params[f'area_{i}'] = a
    if machines:
        mphs = ', '.join(f":machine_{i}" for i in range(len(machines)))
        clauses.append(f"[{mid}] IN ({mphs})")
        for i, m in enumerate(machines): params[f'machine_{i}'] = m
    if shift == 'DAY':
        clauses.append(f"DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18")
    elif shift == 'NIGHT':
        clauses.append(f"DATEPART(HOUR, [{otc}]) NOT BETWEEN 7 AND 18")
    return "WHERE " + " AND ".join(clauses), params


def _make_pareto(reason_df, bar_color, y_label='Hours'):
    fig = go.Figure()
    if not reason_df.empty:
        top15 = reason_df.head(15)
        cum = top15['total_hrs'].cumsum() / top15['total_hrs'].sum() * 100
        fig.add_trace(go.Bar(
            x=top15['reason'], y=top15['total_hrs'],
            marker_color=bar_color, name=y_label,
            hovertemplate='%{x}: %{y:.1f} hrs<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=top15['reason'], y=cum,
            mode='lines+markers',
            marker=dict(color=PRIMARY_BLUE, size=6),
            line=dict(color=PRIMARY_BLUE, width=2),
            name='Cumulative %', yaxis='y2',
            hovertemplate='%{y:.1f}%<extra></extra>',
        ))
    fig.update_layout(
        template='plotly_white', height=350,
        margin=dict(t=10, b=80, l=50, r=50),
        xaxis=dict(tickangle=-45),
        yaxis=dict(title=y_label, showgrid=True,
                   gridcolor='rgba(128,128,128,0.15)'),
        yaxis2=dict(title='Cumulative %', overlaying='y', side='right',
                    range=[0, 105], showgrid=False,
                    ticksuffix='%', tickfont=dict(color=PRIMARY_BLUE)),
        showlegend=True, legend=dict(orientation='h', y=-0.35),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Sans, Calibri, sans-serif'),
    )
    return fig


def _make_machine_bar(machine_df, visible_top=10):
    """Stacked bar by machine. Shows top N visible, rest scrollable."""
    fig = go.Figure()
    if not machine_df.empty and 'reason' in machine_df.columns:
        # Full data with reason breakdown → stacked bar
        top_reasons = machine_df.groupby('reason')['total_hours'].sum().nlargest(8).index.tolist()
        filtered = machine_df[machine_df['reason'].isin(top_reasons)]
        pivot = filtered.pivot_table(index='machine_id', columns='reason',
                                     values='total_hours', fill_value=0)
        pivot['_total'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('_total', ascending=True).drop(columns='_total')
        for i, reason in enumerate(pivot.columns):
            fig.add_trace(go.Bar(
                y=pivot.index.astype(str), x=pivot[reason],
                name=str(reason), orientation='h',
                marker_color=CHART_COLORS[i % len(CHART_COLORS)],
            ))
    elif not machine_df.empty and 'total_hours' in machine_df.columns:
        # Simplified data (e.g., from machine_daily) → single color bar
        agg = machine_df.groupby('machine_id')['total_hours'].sum().sort_values(ascending=True)
        fig.add_trace(go.Bar(
            y=agg.index.astype(str), x=agg.values,
            orientation='h', marker_color=CHART_COLORS[0],
            name='Hours',
            hovertemplate='<b>%{y}</b>: %{x:.1f}h<extra></extra>',
        ))

    n_machines = len(machine_df['machine_id'].unique()) if not machine_df.empty else 0
    # Fixed visible height for top N, full height for scroll
    visible_h = max(300, visible_top * 28 + 60)
    full_h    = max(300, n_machines * 28 + 60)

    fig.update_layout(
        barmode='stack', template='plotly_white',
        height=full_h,
        margin=dict(t=10, b=30, l=80, r=10),
        xaxis=dict(title='Hours'),
        yaxis_title=None, showlegend=True,
        legend=dict(orientation='h', y=-0.15, font=dict(size=10)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )
    return fig, visible_h


def _make_detail_table(tbl_df, table_id, repair_color=RED):
    """Reusable detail DataTable with repair/wait breakdown."""
    tbl_df = tbl_df.copy()
    tbl_df['repair_hrs']     = tbl_df['repair_hrs'].round(1)
    tbl_df['wait_hrs']       = tbl_df['wait_hrs'].round(1)
    tbl_df['total_hrs']      = tbl_df['total_hrs'].round(1)
    tbl_df['avg_repair_min'] = tbl_df['avg_repair_min'].round(0).astype(int)
    tbl_df['avg_wait_min']   = tbl_df['avg_wait_min'].round(0).astype(int)

    col_map = [
        {'name': 'Reason',           'id': 'reason'},
        {'name': 'Events',           'id': 'events'},
        {'name': 'Repair Hrs',       'id': 'repair_hrs'},
        {'name': 'Wait Hrs',         'id': 'wait_hrs'},
        {'name': 'Total Hrs',        'id': 'total_hrs'},
        {'name': 'Avg Repair (min)', 'id': 'avg_repair_min'},
        {'name': 'Avg Wait (min)',   'id': 'avg_wait_min'},
    ]
    return dash_table.DataTable(
        id=table_id,
        columns=col_map,
        data=tbl_df.to_dict('records'),
        sort_action='native', sort_mode='multi',
        page_action='native', page_size=15,
        style_header={
            'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
            'fontWeight': '600', 'fontSize': '12px', 'padding': '11px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
        style_cell={
            'fontSize': '13px', 'padding': '9px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'textAlign': 'left', 'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
        },
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            {'if': {'column_id': 'repair_hrs'},     'color': repair_color, 'fontWeight': '600'},
            {'if': {'column_id': 'wait_hrs'},       'color': ORANGE,       'fontWeight': '600'},
            {'if': {'column_id': 'total_hrs'},      'color': PRIMARY_BLUE, 'fontWeight': '700'},
            {'if': {'column_id': 'avg_repair_min'}, 'color': repair_color, 'fontWeight': '500'},
            {'if': {'column_id': 'avg_wait_min'},   'color': ORANGE,       'fontWeight': '500'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )


def _make_events_table(ev_df, table_id):
    """Event-level detail table — one row per event, with counter."""
    ev = ev_df.copy()
    n_events = len(ev)
    if 'event_time' in ev.columns:
        ev['event_time'] = pd.to_datetime(ev['event_time'], errors='coerce')
        ev['event_time'] = ev['event_time'].dt.strftime('%Y-%m-%d %H:%M')
    ev['wait_min'] = pd.to_numeric(ev['wait_min'], errors='coerce').fillna(0).astype(int)
    ev['repair_min'] = pd.to_numeric(ev['repair_min'], errors='coerce').fillna(0).astype(int)

    col_map = [
        {'name': 'Date/Time',    'id': 'event_time'},
        {'name': 'Machine',      'id': 'machine_id'},
        {'name': 'Area',         'id': 'area'},
        {'name': 'Type',         'id': 'job_type'},
        {'name': 'Symptom',      'id': 'symptom'},
        {'name': 'Cause',        'id': 'cause'},
        {'name': 'Action',       'id': 'action'},
        {'name': 'Tech',         'id': 'tech'},
        {'name': 'Wait (min)',   'id': 'wait_min'},
        {'name': 'Repair (min)', 'id': 'repair_min'},
        {'name': 'Package',      'id': 'package_type'},
        {'name': 'Lot No.',      'id': 'lot_no'},
        {'name': 'Die Mask',     'id': 'die_mask'},
    ]

    counter = html.Div(
        f"Showing {n_events} events",
        style={'fontSize': '12px', 'color': MED_GRAY, 'padding': '6px 0 8px',
               'fontFamily': 'IBM Plex Sans, sans-serif'},
    )

    table = dash_table.DataTable(
        id=table_id,
        columns=col_map,
        data=ev.to_dict('records'),
        sort_action='native', sort_mode='multi',
        filter_action='native',
        page_action='native', page_size=20,
        style_header={
            'backgroundColor': '#EDF2FF', 'color': PRIMARY_BLUE,
            'fontWeight': '600', 'fontSize': '11px', 'padding': '10px 12px',
            'fontFamily': 'DM Sans, Calibri, sans-serif',
            'borderBottom': f'2px solid {PRIMARY_BLUE}',
        },
        style_cell={
            'fontSize': '12px', 'padding': '7px 10px',
            'fontFamily': 'IBM Plex Sans, Calibri, sans-serif',
            'textAlign': 'left', 'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
            'overflow': 'hidden', 'textOverflow': 'ellipsis',
        },
        style_cell_conditional=[
            {'if': {'column_id': 'event_time'}, 'width': '130px'},
            {'if': {'column_id': 'machine_id'}, 'width': '100px'},
            {'if': {'column_id': 'area'},       'width': '55px'},
            {'if': {'column_id': 'job_type'},   'width': '90px'},
            {'if': {'column_id': 'symptom'},    'minWidth': '160px', 'maxWidth': '250px'},
            {'if': {'column_id': 'cause'},      'minWidth': '130px', 'maxWidth': '200px'},
            {'if': {'column_id': 'action'},     'minWidth': '130px', 'maxWidth': '200px'},
            {'if': {'column_id': 'tech'},       'width': '80px'},
            {'if': {'column_id': 'wait_min'},   'width': '75px', 'textAlign': 'right'},
            {'if': {'column_id': 'repair_min'}, 'width': '85px', 'textAlign': 'right'},
            {'if': {'column_id': 'package_type'}, 'width': '90px'},
            {'if': {'column_id': 'lot_no'},       'width': '110px'},
            {'if': {'column_id': 'die_mask'},     'width': '100px'},
        ],
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            {'if': {'filter_query': '{job_type} = "M/C DOWN"', 'column_id': 'job_type'},
             'color': RED, 'fontWeight': '600'},
            {'if': {'filter_query': '{job_type} contains "SETUP"', 'column_id': 'job_type'},
             'color': LIGHT_BLUE, 'fontWeight': '600'},
            {'if': {'column_id': 'machine_id'}, 'fontWeight': '600'},
            {'if': {'column_id': 'action'}, 'color': '#6B3FA0', 'fontWeight': '500'},
            {'if': {'column_id': 'wait_min'}, 'color': ORANGE, 'fontWeight': '500'},
            {'if': {'column_id': 'repair_min'}, 'color': RED, 'fontWeight': '500'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )
    return html.Div([counter, table])


def _make_symptom_cause_table(sc_df, table_id, repair_color=RED):
    """Detail table with Symptom + Root Cause columns (for M/C DOWN)."""
    sc_df = sc_df.copy()
    sc_df['repair_hrs']     = sc_df['repair_hrs'].round(1)
    sc_df['wait_hrs']       = sc_df['wait_hrs'].round(1)
    sc_df['total_hrs']      = sc_df['total_hrs'].round(1)
    sc_df['avg_repair_min'] = sc_df['avg_repair_min'].round(0).astype(int)
    sc_df['avg_wait_min']   = sc_df['avg_wait_min'].round(0).astype(int)

    col_map = [
        {'name': 'Symptom',          'id': 'symptom'},
        {'name': 'Root Cause',       'id': 'root_cause'},
        {'name': 'Events',           'id': 'events'},
        {'name': 'Repair Hrs',       'id': 'repair_hrs'},
        {'name': 'Wait Hrs',         'id': 'wait_hrs'},
        {'name': 'Total Hrs',        'id': 'total_hrs'},
        {'name': 'Avg Repair (min)', 'id': 'avg_repair_min'},
        {'name': 'Avg Wait (min)',   'id': 'avg_wait_min'},
    ]
    return dash_table.DataTable(
        id=table_id,
        columns=col_map,
        data=sc_df.to_dict('records'),
        sort_action='native', sort_mode='multi',
        page_action='native', page_size=15,
        style_header={
            'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
            'fontWeight': '600', 'fontSize': '12px', 'padding': '11px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
        style_cell={
            'fontSize': '13px', 'padding': '9px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'textAlign': 'left', 'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
        },
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            {'if': {'column_id': 'symptom'},        'fontWeight': '600'},
            {'if': {'column_id': 'root_cause'},     'color': '#6B3FA0', 'fontWeight': '500'},
            {'if': {'column_id': 'repair_hrs'},     'color': repair_color, 'fontWeight': '600'},
            {'if': {'column_id': 'wait_hrs'},       'color': ORANGE,       'fontWeight': '600'},
            {'if': {'column_id': 'total_hrs'},      'color': PRIMARY_BLUE, 'fontWeight': '700'},
            {'if': {'column_id': 'avg_repair_min'}, 'color': repair_color, 'fontWeight': '500'},
            {'if': {'column_id': 'avg_wait_min'},   'color': ORANGE,       'fontWeight': '500'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )


def _make_kpi_row(reason_df, daily_shift_df, accent_color, top_machine_name='—',
                  top_machine_hrs=0, mtba_hrs=None):
    """Build 5 KPI cards from aggregated data."""
    from components.kpi_card import make_kpi_card

    total_hrs  = reason_df['total_hrs'].sum()   if not reason_df.empty else 0
    total_evts = int(reason_df['events'].sum())  if not reason_df.empty else 0
    avg_repair = int(reason_df['avg_repair_min'].mean()) if not reason_df.empty else 0
    avg_wait   = int(reason_df['avg_wait_min'].mean())   if not reason_df.empty else 0

    # MTBA display
    if mtba_hrs is not None and mtba_hrs > 0:
        mtba_val = f"{mtba_hrs:.1f}"
        mtba_unit = "hrs"
    else:
        mtba_val = "N/A"
        mtba_unit = ""

    return [
        dbc.Col(make_kpi_card(f"{total_hrs:,.0f}", "Total Hours",
                              accent_color, unit="h",
                              subtitle=f"{total_evts:,} events"),
                lg=6, md=6, sm=6),
        dbc.Col(make_kpi_card(f"{avg_repair}", "MTTR",
                              RED, unit="min",
                              subtitle="Avg repair time"), lg=6, md=6, sm=6),
        dbc.Col(make_kpi_card(f"{avg_wait}", "MTTW",
                              ORANGE, unit="min",
                              subtitle="Avg response time"), lg=6, md=6, sm=6),
        dbc.Col(make_kpi_card(mtba_val, "MTBA",
                              GREEN, unit=mtba_unit,
                              subtitle="Avg time between assists"),
                lg=6, md=6, sm=6),
    ]


def _make_shift_chart(daily_shift_df, bar_color, y_label='Hours'):
    """Daily trend with Day/Night shift breakdown per day."""
    fig = go.Figure()
    if not daily_shift_df.empty:
        df = daily_shift_df.copy()
        df['day'] = pd.to_datetime(df['day'])
        df['total_hrs'] = df['repair_hrs'] + df['wait_hrs']
        df['day_label'] = df['day'].dt.strftime('%b %d')
        sorted_days = df.sort_values('day')['day_label'].unique().tolist()

        shift_order = ['Night', 'Day']  # Night starts first (19:00 prev day)
        for shift_name in shift_order:
            grp = df[df['shift_name'] == shift_name]
            if grp.empty:
                continue
            grp = grp.sort_values('day')
            color = '#6B3FA0' if shift_name == 'Night' else bar_color
            fig.add_trace(go.Bar(
                x=grp['day_label'], y=grp['total_hrs'],
                name=shift_name,
                marker_color=color,
                text=[f"{v:.1f}" for v in grp['total_hrs']],
                textposition='outside', textfont=dict(size=8),
                hovertemplate=(
                    '<b>' + shift_name + '</b><br>'
                    '%{x}<br>'
                    'Total: %{y:.1f}h<br>'
                    'Repair: %{customdata[0]:.1f}h<br>'
                    'Wait: %{customdata[1]:.1f}h<br>'
                    'Events: %{customdata[2]}'
                    '<extra></extra>'
                ),
                customdata=list(zip(grp['repair_hrs'], grp['wait_hrs'], grp['events'],
                                    [shift_name] * len(grp))),
            ))

    fig.update_layout(
        barmode='group', template='plotly_white', height=300,
        margin=dict(t=10, b=60, l=50, r=10),
        xaxis=dict(showgrid=False, tickangle=-40,
                   categoryorder='array',
                   categoryarray=sorted_days if not daily_shift_df.empty else []),
        yaxis=dict(title=y_label, showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
        legend=dict(orientation='h', y=-0.22, font=dict(size=11)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
        bargap=0.25,
    )
    return fig


def _table_header(title, subtitle, badge_text, badge_color, btn_id):
    """Reusable table header row with title, badge, and export button."""
    return html.Div([
        html.Div([
            html.Span(title, style={
                'fontSize': '14px', 'fontWeight': '600', 'color': 'var(--text)'}),
            html.Span(f" — {subtitle}", style={
                'fontSize': '12px', 'color': 'var(--text-light)', 'marginLeft': '4px'}),
        ]),
        html.Div([
            html.Span(badge_text, style={
                'fontSize': '10px', 'fontWeight': '600',
                'color': badge_color, 'background': badge_color + '18',
                'padding': '2px 9px', 'borderRadius': '10px',
                'textTransform': 'uppercase', 'letterSpacing': '0.4px',
                'marginRight': '10px',
            }),
            html.Button([
                html.Span("⬇", style={'marginRight': '5px'}), "Export CSV",
            ], id=btn_id, style={
                'background': PRIMARY_BLUE, 'color': '#fff', 'border': 'none',
                'borderRadius': '6px', 'padding': '5px 14px', 'fontSize': '12px',
                'fontWeight': '600', 'cursor': 'pointer',
                'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
                'boxShadow': '0 2px 4px rgba(14,54,137,0.25)',
            }),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], style={
        'display': 'flex', 'justifyContent': 'space-between',
        'alignItems': 'center', 'marginBottom': '12px',
        'paddingBottom': '10px', 'borderBottom': '1px solid var(--divider)',
    })


def _click_indicator(indicator_id, clear_btn_id):
    """Filter indicator bar — shows what's clicked, with clear button."""
    return html.Div([
        html.Span(id=indicator_id),
        html.Button("✕ Clear", id=clear_btn_id, n_clicks=0,
                    style={'display': 'none'}),
    ], style={'marginBottom': '8px'})


def _section_layout(prefix, accent_color, section_label, shift_label,
                    pareto_label, machine_label, table_title, badge_text,
                    export_btn_id, download_id, compact=False):
    """Build a full section: stores + indicator + KPI + charts + table."""
    items = [
        # Data stores
        dcc.Store(id=f'{prefix}-data-store', storage_type='memory'),
        dcc.Store(id=f'{prefix}-click-filter', storage_type='memory'),

        # Click indicator
        _click_indicator(f'{prefix}-click-indicator', f'{prefix}-clear-click'),

        # KPI cards
        dbc.Row(id=f'{prefix}-kpi-row', className='g-3 mb-3'),
    ]

    if compact:
        # Compact: KPI + Pareto only, shift/machine/table in accordion
        items += [
            dbc.Row([
                dbc.Col([html.Div([
                    make_chart_title(pareto_label, badge_text, accent_color),
                    dcc.Graph(id=f'{prefix}-pareto', config={'displayModeBar': False}),
                ], className='chart-card')], lg=7, md=12),
                dbc.Col([html.Div([
                    make_chart_title(machine_label, "Top 10"),
                    html.Div(
                        dcc.Graph(id=f'{prefix}-by-machine', config={'displayModeBar': False}),
                        id=f'{prefix}-machine-scroll',
                        style={'maxHeight': '340px', 'overflowY': 'auto'},
                    ),
                ], className='chart-card')], lg=5, md=12),
            ]),
            dbc.Accordion([
                dbc.AccordionItem([
                    html.Div([
                        make_chart_title(shift_label, "Day vs Night", accent_color),
                        dcc.Graph(id=f'{prefix}-trend', config={'displayModeBar': False}),
                    ], className='chart-card'),
                    html.Div([
                        _table_header(table_title, "Repair Time + Waiting Time Breakdown",
                                      badge_text, accent_color, export_btn_id),
                        dcc.Download(id=download_id),
                        html.Div(id=f'{prefix}-table'),
                    ], className='chart-card'),
                ], title="Show Shift Trend & Detail Table"),
            ], start_collapsed=True, className='mb-3'),
        ]
    else:
        # Full: shift chart + pareto + machine + detail table
        items += [
            html.Div([
                make_chart_title(shift_label, "Day vs Night", accent_color),
                dcc.Loading(type='dot', color=accent_color,
                    children=dcc.Graph(id=f'{prefix}-trend',
                                       config={'displayModeBar': False})),
            ], className='chart-card'),

            dbc.Row([
                dbc.Col([html.Div([
                    make_chart_title(pareto_label, badge_text, accent_color),
                    dcc.Graph(id=f'{prefix}-pareto', config={'displayModeBar': False}),
                ], className='chart-card')], lg=7, md=12),
                dbc.Col([html.Div([
                    make_chart_title(machine_label, "Top 10 · Scroll for more"),
                    html.Div(
                        dcc.Graph(id=f'{prefix}-by-machine', config={'displayModeBar': False}),
                        id=f'{prefix}-machine-scroll',
                        style={'maxHeight': '340px', 'overflowY': 'auto'},
                    ),
                ], className='chart-card')], lg=5, md=12),
            ]),

            html.Div([
                _table_header(table_title, "Event-Level Records",
                              badge_text, accent_color, export_btn_id),
                dcc.Download(id=download_id),
                html.Div(id=f'{prefix}-table'),
            ], className='chart-card'),
        ]

    return items


# ── Layout ────────────────────────────────────────────────────────────────────
def _section_badge(label, color):
    return html.Span(label, style={
        'fontSize': '13px', 'fontWeight': '700', 'color': '#fff',
        'background': color, 'padding': '4px 12px', 'borderRadius': '6px',
        'fontFamily': 'DM Sans, sans-serif', 'display': 'inline-block',
        'marginBottom': '8px',
    })


layout = html.Div([
    make_page_header("Downtime & Setup Analysis"),
    make_filter_bar(show_machine=True, show_shift=True, default_days=7),

    # Setup type toggle (inline with filters)
    html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Setup Type", className='filter-label'),
                dcc.Dropdown(
                    id='setup-type-toggle',
                    options=[
                        {'label': 'All Setup',              'value': 'ALL'},
                        {'label': 'SETUP (Technician)',      'value': 'SETUP'},
                        {'label': 'SETUP BY OPERATOR',       'value': 'SETUP BY OPERATOR'},
                    ],
                    value='ALL', clearable=False,
                    style={'fontSize': '13px', 'width': '250px'},
                ),
            ], md='auto'),
        ], className='g-2'),
    ], style={'marginBottom': '14px'}),

    # Hidden stores + click states (both sections)
    dcc.Store(id='dt-data-store', storage_type='memory'),
    dcc.Store(id='dt-click-filter', storage_type='memory'),
    dcc.Store(id='setup-data-store', storage_type='memory'),
    dcc.Store(id='setup-click-filter', storage_type='memory'),

    # ── Row 1: KPIs side by side ──────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            _section_badge("M/C DOWN", RED),
            _click_indicator('dt-click-indicator', 'dt-clear-click'),
            dbc.Row(id='dt-kpi-row', className='g-2'),
        ], lg=6, md=12),
        dbc.Col([
            _section_badge("SETUP", LIGHT_BLUE),
            _click_indicator('setup-click-indicator', 'setup-clear-click'),
            dbc.Row(id='setup-kpi-row', className='g-2'),
        ], lg=6, md=12),
    ], className='mb-3'),

    # ── Row 2: Shift charts side by side ──────────────────────────────────────
    dbc.Row([
        dbc.Col([html.Div([
            make_chart_title("Downtime by Shift", "Day vs Night", RED),
            dcc.Loading(type='dot', color=RED,
                children=dcc.Graph(id='dt-trend', config={'displayModeBar': False})),
        ], className='chart-card')], lg=6, md=12),
        dbc.Col([html.Div([
            make_chart_title("Setup by Shift", "Day vs Night", LIGHT_BLUE),
            dcc.Graph(id='setup-trend', config={'displayModeBar': False}),
        ], className='chart-card')], lg=6, md=12),
    ]),

    # ── Row 3: Pareto side by side ────────────────────────────────────────────
    dbc.Row([
        dbc.Col([html.Div([
            make_chart_title("Top Downtime Reasons", "M/C DOWN", RED),
            dcc.Graph(id='dt-pareto', config={'displayModeBar': False}),
        ], className='chart-card')], lg=6, md=12),
        dbc.Col([html.Div([
            make_chart_title("Top Setup Causes", "SETUP", LIGHT_BLUE),
            dcc.Graph(id='setup-pareto', config={'displayModeBar': False}),
        ], className='chart-card')], lg=6, md=12),
    ]),

    # ── Row 4: Machine bars side by side ──────────────────────────────────────
    dbc.Row([
        dbc.Col([html.Div([
            make_chart_title("Top Downtime Machines", "M/C DOWN"),
            html.Div(dcc.Graph(id='dt-by-machine', config={'displayModeBar': False}),
                     id='dt-machine-scroll',
                     style={'maxHeight': '340px', 'overflowY': 'auto'}),
        ], className='chart-card')], lg=6, md=12),
        dbc.Col([html.Div([
            make_chart_title("Top Setup Machines", "SETUP"),
            html.Div(dcc.Graph(id='setup-by-machine', config={'displayModeBar': False}),
                     id='setup-machine-scroll',
                     style={'maxHeight': '340px', 'overflowY': 'auto'}),
        ], className='chart-card')], lg=6, md=12),
    ]),

    # ── Row 5: Combined Event Detail Table with filters ─────────────────────
    html.Div([
        _table_header("Event Detail", "All Events",
                       "M/C DOWN + SETUP", PRIMARY_BLUE, 'btn-dt-export-csv'),

        # Filter row (like old ASO system)
        dbc.Row([
            dbc.Col([
                html.Label("Job Type", className='filter-label'),
                dbc.Checklist(
                    id='evt-filter-type',
                    options=[
                        {'label': ' M/C DOWN',          'value': 'M/C DOWN'},
                        {'label': ' SETUP',             'value': 'SETUP'},
                        {'label': ' SETUP BY OPERATOR', 'value': 'SETUP BY OPERATOR'},
                        {'label': ' PM',                'value': 'PM'},
                        {'label': ' CONVERT',           'value': 'CONVERT'},
                        {'label': ' FACILITY DOWN',     'value': 'FACILITY DOWN'},
                        {'label': ' ENGINEERING DOWN',  'value': 'ENGINEERING DOWN'},
                    ],
                    value=['M/C DOWN', 'SETUP', 'SETUP BY OPERATOR'],
                    inline=True,
                    style={'fontSize': '12px'},
                ),
            ], lg=12, className='mb-2'),
        ], className='g-2'),
        dbc.Row([
            dbc.Col([
                html.Label("Machine", className='filter-label'),
                dcc.Dropdown(id='evt-filter-machine', placeholder='All Machines',
                             multi=True, style={'fontSize': '12px'}),
            ], lg=2, md=4, sm=6),
            dbc.Col([
                html.Label("Symptom", className='filter-label'),
                dcc.Dropdown(id='evt-filter-symptom', placeholder='All Symptoms',
                             multi=True, style={'fontSize': '12px'}),
            ], lg=3, md=4, sm=6),
            dbc.Col([
                html.Label("Cause", className='filter-label'),
                dcc.Dropdown(id='evt-filter-cause', placeholder='All Causes',
                             multi=True, style={'fontSize': '12px'}),
            ], lg=3, md=4, sm=6),
            dbc.Col([
                html.Label("Tech", className='filter-label'),
                dcc.Dropdown(id='evt-filter-tech', placeholder='All Techs',
                             multi=True, style={'fontSize': '12px'}),
            ], lg=2, md=4, sm=6),
            dbc.Col([
                html.Label("\u00a0", className='filter-label'),
                dbc.Button("Search", id='evt-search-btn', size='sm',
                           color='primary', style={'width': '100%'}),
            ], lg=2, md=4, sm=6),
        ], className='g-2 mb-2'),

        # Events data store + table output
        dcc.Store(id='dt-events-raw', storage_type='memory'),
        dcc.Download(id='dt-download-csv'),
        html.Div(id='dt-table'),
    ], className='chart-card'),

    # Hidden: setup table + download (callback needs these IDs)
    html.Div([
        dcc.Download(id='setup-download-csv'),
        html.Div(id='setup-table'),
    ], style={'display': 'none'}),

], className='page-container')


# ── Machine filter (includes both M/C DOWN + SETUP machines) ─────────────────
@callback(
    Output('filter-machine', 'options'),
    Input('filter-area', 'value'),
    Input('auto-refresh', 'n_intervals'),
)
def load_machines(areas, n):
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    mid = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'
    ac  = COLUMN_MAP.get('machine_area', 'id_operation') or 'id_operation'
    sc  = COLUMN_MAP.get('status', 'job_type') or 'job_type'
    try:
        where = f"WHERE [{sc}] IN ('M/C DOWN','SETUP','SETUP BY OPERATOR')"
        params = {}
        if areas:
            phs = ', '.join(f":area_{i}" for i in range(len(areas)))
            where += f" AND [{ac}] IN ({phs})"
            for i, a in enumerate(areas): params[f'area_{i}'] = a
        df = query_df(f"SELECT DISTINCT [{mid}] AS m FROM {VIEW_NAME} {where} ORDER BY [{mid}]",
                      params)
        return [{'label': r['m'], 'value': r['m']} for _, r in df.iterrows()]
    except Exception:
        return []


# ── Query runner (shared by both callbacks) ───────────────────────────────────
def _run_queries(job_types, start_date, end_date, areas, machines, shift,
                 reason_col=None):
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP

    rc  = COLUMN_MAP.get('downtime_reason', 'cause')        or 'cause'
    sym = COLUMN_MAP.get('symptom',         'des_job')      or 'des_job'
    otc = COLUMN_MAP.get('opr_start_time',  'datex')        or 'datex'
    ttc = COLUMN_MAP.get('tech_start_time', 'date_ack')     or 'date_ack'
    ec  = COLUMN_MAP.get('end_time',        'date_close')   or 'date_close'
    mid = COLUMN_MAP.get('machine_id',      'code_machine') or 'code_machine'
    ac  = COLUMN_MAP.get('machine_area',    'id_operation')  or 'id_operation'
    sc  = COLUMN_MAP.get('status',          'job_type')      or 'job_type'

    grp = reason_col or rc  # Pareto groups by this column

    where, params = _build_where(otc, ec, sc, ac, mid,
                                  start_date, end_date, areas, machines, shift,
                                  job_types)

    # Pareto + KPI — grouped by symptom (des_job) or cause depending on section
    reason_df = query_df(f"""
        SELECT [{grp}] AS reason,
               COUNT(*) AS events,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
               SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0
                   + SUM(ISNULL(Waiting_time, 0)) / 60.0      AS total_hrs,
               AVG(DATEDIFF(MINUTE, [{ttc}], [{ec}]))          AS avg_repair_min,
               AVG(ISNULL(Waiting_time, 0))                    AS avg_wait_min,
               MAX(ISNULL(Waiting_time, 0))                    AS max_wait_min
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{grp}]
        ORDER BY total_hrs DESC
    """, params)

    # By machine — grouped by symptom/cause
    machine_df = query_df(f"""
        SELECT [{mid}] AS machine_id,
               [{grp}] AS reason,
               COUNT(*) AS event_count,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS total_hours
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{mid}], [{grp}]
        ORDER BY total_hours DESC
    """, params)

    # Symptom→Root Cause detail (only when grouping by symptom, i.e., M/C DOWN)
    symptom_cause_df = pd.DataFrame()
    if reason_col and reason_col != rc:
        symptom_cause_df = query_df(f"""
            SELECT [{sym}] AS symptom,
                   [{rc}] AS root_cause,
                   COUNT(*) AS events,
                   SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
                   SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs,
                   SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0
                       + SUM(ISNULL(Waiting_time, 0)) / 60.0      AS total_hrs,
                   AVG(DATEDIFF(MINUTE, [{ttc}], [{ec}]))          AS avg_repair_min,
                   AVG(ISNULL(Waiting_time, 0))                    AS avg_wait_min
            FROM {VIEW_NAME} {where}
            AND [{rc}] IS NOT NULL AND [{rc}] != ''
            AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
            GROUP BY [{sym}], [{rc}]
            ORDER BY total_hrs DESC
        """, params)

    # Per-machine per-day per-shift per-reason for drill-down
    machine_daily_df = query_df(f"""
        SELECT [{mid}] AS machine_id,
               [{grp}] AS reason,
               CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                    THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                    ELSE CAST([{otc}] AS DATE) END AS day,
               CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                    THEN 'Day' ELSE 'Night' END AS shift_name,
               COUNT(*) AS events,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS total_hours,
               SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{mid}], [{grp}],
                 CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                      THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                      ELSE CAST([{otc}] AS DATE) END,
                 CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                      THEN 'Day' ELSE 'Night' END
    """, params)

    # Shift date logic:
    #   Night shift of Apr 16 = Apr 15 19:00 → Apr 16 06:59
    #   Day shift of Apr 16   = Apr 16 07:00 → Apr 16 18:59
    #   Hour >= 19 (evening) → shift_date = next day
    #   Hour < 7   (early morning) → shift_date = same day
    #   Hour 7-18  (daytime) → shift_date = same day
    daily_shift_df = query_df(f"""
        SELECT
            CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                 THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                 ELSE CAST([{otc}] AS DATE)
            END AS day,
            CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                 THEN 'Day' ELSE 'Night' END AS shift_name,
            COUNT(*) AS events,
            SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
            SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs
        FROM {VIEW_NAME} {where}
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY
            CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                 THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                 ELSE CAST([{otc}] AS DATE) END,
            CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                 THEN 'Day' ELSE 'Night' END
        ORDER BY day, shift_name
    """, params)

    # Event-level raw data (for combined detail table — ALL job types, not just this section's)
    all_types = ['M/C DOWN', 'SETUP', 'SETUP BY OPERATOR', 'PM', 'CONVERT',
                 'FACILITY DOWN', 'ENGINEERING DOWN', 'CLEAN MOLD', 'CHANGE CAP']
    evt_where, evt_params = _build_where(otc, ec, sc, ac, mid,
                                          start_date, end_date, areas, machines,
                                          shift, all_types)
    events_df = query_df(f"""
        SELECT TOP 500 [{mid}] AS machine_id, [{ac}] AS area,
               [{sc}] AS job_type, [{sym}] AS symptom, [{rc}] AS cause, [action],
               [{otc}] AS event_time,
               ISNULL(by_perform, by_ack) AS tech,
               ISNULL(Waiting_time, 0) AS wait_min,
               DATEDIFF(MINUTE, [{ttc}], [{ec}]) AS repair_min,
               [Package Type] AS package_type, [lot_no], [mpc] AS die_mask
        FROM {VIEW_NAME} {evt_where}
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        ORDER BY [{otc}] DESC
    """, evt_params)

    # ── Merge Oracle ISO/FS data ────────────────────────────────────────────
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import (ora_dt_reason, ora_dt_machine,
                                          ora_dt_daily_shift, ora_dt_machine_daily,
                                          ora_dt_symptom_cause)
            if not areas or any(a in ('ISO', 'FS') for a in areas):
                ora = fetch_oracle_data(start_date, end_date, areas, shift)
                if ora is not None:
                    r_col = 'symptom' if reason_col else 'cause'
                    reason_df = pd.concat([reason_df, ora_dt_reason(ora, job_types, r_col)], ignore_index=True)
                    reason_df = (reason_df.groupby('reason')
                                 .agg({c: 'sum' for c in reason_df.columns if c != 'reason'})
                                 .reset_index()
                                 .sort_values('total_hrs', ascending=False)
                                 .reset_index(drop=True))
                    machine_df = pd.concat([machine_df, ora_dt_machine(ora, job_types, r_col)], ignore_index=True)
                    daily_shift_df = pd.concat([daily_shift_df, ora_dt_daily_shift(ora, job_types)], ignore_index=True)
                    daily_shift_df = (daily_shift_df.groupby(['day', 'shift_name'])
                                      .agg({c: 'sum' for c in daily_shift_df.columns if c not in ('day', 'shift_name')})
                                      .reset_index()
                                      .sort_values(['day', 'shift_name']))
                    machine_daily_df = pd.concat([machine_daily_df, ora_dt_machine_daily(ora, job_types, r_col)], ignore_index=True)
                    if reason_col and reason_col != rc:
                        ora_sc = ora_dt_symptom_cause(ora, job_types)
                        if not ora_sc.empty:
                            symptom_cause_df = pd.concat([symptom_cause_df, ora_sc], ignore_index=True)
                    # Oracle events for detail table
                    ora_events = ora[['machine_id', 'area', 'job_type', 'symptom',
                                      'cause', 'datex', 'badge', 'wait_min', 'repair_min']].copy()
                    ora_events = ora_events.rename(columns={'datex': 'event_time', 'badge': 'tech'})
                    ora_events['wait_min'] = ora_events['wait_min'].round(0).astype(int)
                    ora_events['repair_min'] = ora_events['repair_min'].round(0).astype(int)
                    events_df = pd.concat([events_df, ora_events], ignore_index=True)
                    events_df = events_df.sort_values('event_time', ascending=False).head(200)
    except Exception:
        pass  # Oracle failure doesn't break SQL Server data

    return reason_df, machine_df, daily_shift_df, machine_daily_df, symptom_cause_df, events_df


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC CALLBACK FACTORY — creates all 4 callbacks per section
# ══════════════════════════════════════════════════════════════════════════════
_FILTER_INPUTS = [
    Input('auto-refresh',      'n_intervals'),
    Input('filter-date-range', 'start_date'),
    Input('filter-date-range', 'end_date'),
    Input('filter-area',       'value'),
    Input('filter-machine',    'value'),
    Input('util-filter-shift', 'value'),
]

def _empty():
    fig = go.Figure()
    fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Calibri, Segoe UI, sans-serif'))
    return fig


def _register_section(prefix, job_types, accent_color, bar_label, table_id,
                      reason_col=None, type_toggle_id=None):
    """Register all callbacks for one section (Downtime or Setup)."""
    import json as _json

    # ── 1. Data callback — query DB, store data, render trend only ───────────
    extra_inputs = [Input(type_toggle_id, 'value')] if type_toggle_id else []

    @callback(
        Output(f'{prefix}-data-store',  'data'),
        Output(f'{prefix}-click-filter','data'),   # clear on filter change
        Output(f'{prefix}-trend',       'figure'),
        *_FILTER_INPUTS,
        *extra_inputs,
    )
    def update_charts(*args):
        # Parse args: 6 filter inputs + optional toggle
        n_intervals, start_date, end_date, areas, machines, shift = args[:6]
        type_filter = args[6] if len(args) > 6 else None

        # Resolve job types based on toggle
        active_types = job_types
        if type_filter and type_filter != 'ALL':
            active_types = [type_filter]

        ef = _empty()
        try:
            reason_df, machine_df, daily_shift_df, machine_daily_df, symptom_cause_df, events_df = \
                _run_queries(active_types, start_date, end_date, areas, machines, shift,
                             reason_col=reason_col)
        except Exception as e:
            return None, None, ef

        trend = _make_shift_chart(daily_shift_df, accent_color, bar_label)

        # Add day_label for click matching
        if not daily_shift_df.empty:
            daily_shift_df['day_label'] = pd.to_datetime(daily_shift_df['day']).dt.strftime('%b %d')
        if not machine_daily_df.empty:
            machine_daily_df['day_label'] = pd.to_datetime(machine_daily_df['day']).dt.strftime('%b %d')

        # Machine count for MTBA calculation (SQL Server + Oracle)
        _machine_count = 0
        try:
            from db import query_df as _qdf
            from config import VIEW_NAME as _VN, COLUMN_MAP as _CM
            from utils.queries import util_total_machine_count as _utmc
            _mid = _CM.get('machine_id', 'code_machine') or 'code_machine'
            _otc = _CM.get('opr_start_time', 'datex') or 'datex'
            _ec  = _CM.get('end_time', 'date_close') or 'date_close'
            _sc  = _CM.get('status', 'job_type') or 'job_type'
            _ac  = _CM.get('machine_area', 'id_operation') or 'id_operation'
            _w, _p = _build_where(_otc, _ec, _sc, _ac, _mid,
                                   start_date, end_date, areas, machines,
                                   shift, active_types)
            if _w != 'WHERE 1=0':
                _cnt = _qdf(_utmc(_VN, _mid, _w), _p)
                _machine_count = int(_cnt['machine_count'].iloc[0]) if not _cnt.empty else 0
            # Add Oracle machine count
            from config import ORA_ENABLED as _OE2
            if _OE2:
                from oracle_db import fetch_oracle_data as _ofd2
                if not areas or any(a in ('ISO', 'FS') for a in areas):
                    _ora2 = _ofd2(start_date, end_date, areas, shift)
                    if _ora2 is not None:
                        _ora_mc = _ora2['machine_id'].nunique()
                        _machine_count += _ora_mc
        except Exception:
            pass

        store = {
            'reason':         reason_df.to_json(orient='split', date_format='iso'),
            'daily_shift':    daily_shift_df.to_json(orient='split', date_format='iso'),
            'machine':        machine_df.to_json(orient='split', date_format='iso'),
            'machine_daily':  machine_daily_df.to_json(orient='split', date_format='iso'),
            'symptom_cause':  symptom_cause_df.to_json(orient='split', date_format='iso')
                              if not symptom_cause_df.empty else '',
            'events':         events_df.to_json(orient='split', date_format='iso')
                              if not events_df.empty else '',
            'start_date':     str(start_date)[:10] if start_date else '',
            'end_date':       str(end_date)[:10] if end_date else '',
            'shift':          shift or '',
            'machine_count':  _machine_count,
        }
        return store, None, trend

    # ── 2. Click-state callback ───────────────────────────────────────────────
    @callback(
        Output(f'{prefix}-click-filter', 'data', allow_duplicate=True),
        Input(f'{prefix}-trend',      'clickData'),
        Input(f'{prefix}-pareto',     'clickData'),
        Input(f'{prefix}-by-machine', 'clickData'),
        Input(f'{prefix}-clear-click','n_clicks'),
        prevent_initial_call=True,
    )
    def handle_click(trend_click, pareto_click, machine_click, clear_clicks):
        triggered = dash.ctx.triggered_id
        if triggered == f'{prefix}-clear-click':
            return None
        if triggered == f'{prefix}-trend' and trend_click:
            pt = trend_click['points'][0]
            cd = pt.get('customdata', [])
            shift_name = cd[3] if len(cd) > 3 else ''
            return {'source': 'trend', 'key': 'day_shift',
                    'day': pt['x'], 'shift': shift_name}
        if triggered == f'{prefix}-pareto' and pareto_click:
            pt = pareto_click['points'][0]
            return {'source': 'pareto', 'key': 'reason', 'value': pt['x']}
        if triggered == f'{prefix}-by-machine' and machine_click:
            pt = machine_click['points'][0]
            return {'source': 'machine', 'key': 'machine_id', 'value': pt['y']}
        return dash.no_update

    # ── 3. KPI + Charts + Table + Indicator (all respond to click) ───────────
    extra_outputs = [Output('dt-events-raw', 'data')] if prefix == 'dt' else []

    @callback(
        Output(f'{prefix}-kpi-row',         'children'),
        Output(f'{prefix}-pareto',          'figure'),
        Output(f'{prefix}-by-machine',      'figure'),
        Output(f'{prefix}-table',           'children'),
        Output(f'{prefix}-click-indicator', 'children'),
        Output(f'{prefix}-clear-click',     'style'),
        *extra_outputs,
        Input(f'{prefix}-data-store',  'data'),
        Input(f'{prefix}-click-filter','data'),
    )
    def update_kpi_table(store_data, click_filter):
        hide_btn = {'display': 'none'}
        show_btn = {
            'display': 'inline', 'background': 'none', 'border': 'none',
            'color': 'var(--text-light)', 'fontSize': '11px',
            'cursor': 'pointer', 'marginLeft': '10px',
            'textDecoration': 'underline',
        }

        ef = _empty()
        _empty_ret = ([], ef, ef, html.Div("Loading...",
                    style={'color': MED_GRAY, 'padding': '20px'}), "", hide_btn)
        if prefix == 'dt':
            _empty_ret = (*_empty_ret, None)
        if not store_data:
            return _empty_ret

        reason_df        = pd.read_json(store_data['reason'],        orient='split')
        daily_shift_df   = pd.read_json(store_data['daily_shift'],   orient='split')
        machine_df       = pd.read_json(store_data.get('machine', '{}'),       orient='split') \
                           if 'machine' in store_data else pd.DataFrame()
        machine_daily_df = pd.read_json(store_data.get('machine_daily', '{}'), orient='split') \
                           if 'machine_daily' in store_data else pd.DataFrame()

        filtered_reason  = reason_df.copy()
        filtered_machine = machine_df.copy()
        indicator = ""
        btn_style = hide_btn

        if click_filter:
            src   = click_filter.get('source')
            key   = click_filter.get('key')
            value = click_filter.get('value')

            if src == 'pareto' and key == 'reason':
                filtered_reason = reason_df[reason_df['reason'] == value]
                # Filter machines to this cause
                if not machine_df.empty:
                    filtered_machine = machine_df[machine_df['reason'] == value]
            elif src == 'machine' and key == 'machine_id':
                # Filter machines to clicked machine
                if not machine_df.empty:
                    filtered_machine = machine_df[machine_df['machine_id'] == value]
                # Also filter reason_df to reasons for this machine
                if not filtered_machine.empty:
                    machine_reasons = filtered_machine['reason'].unique().tolist()
                    filtered_reason = reason_df[reason_df['reason'].isin(machine_reasons)]
            elif src == 'trend' and key == 'day_shift':
                day_val   = click_filter.get('day', '')
                shift_val = click_filter.get('shift', '')

                # Filter machine_daily by day + shift
                if not machine_daily_df.empty:
                    md = machine_daily_df[machine_daily_df['day_label'] == str(day_val)]
                    if shift_val:
                        md = md[md['shift_name'] == shift_val]
                    if not md.empty:
                        filtered_machine = md

                        # Derive reason breakdown from filtered machine_daily
                        label = f"{day_val} ({shift_val})" if shift_val else day_val
                        reason_agg = md.groupby('reason').agg(
                            events=('events', 'sum'),
                            repair_hrs=('total_hours', 'sum'),
                            wait_hrs=('wait_hrs', 'sum'),
                        ).reset_index()
                        reason_agg['total_hrs'] = reason_agg['repair_hrs'] + reason_agg['wait_hrs']
                        reason_agg['avg_repair_min'] = reason_agg['repair_hrs'] / reason_agg['events'].clip(lower=1) * 60
                        reason_agg['avg_wait_min']   = reason_agg['wait_hrs']   / reason_agg['events'].clip(lower=1) * 60
                        reason_agg = reason_agg.sort_values('total_hrs', ascending=False)
                        filtered_reason = reason_agg

            display_val = value
            if src == 'trend':
                day_v   = click_filter.get('day', '')
                shift_v = click_filter.get('shift', '')
                display_val = f"{day_v} ({shift_v})" if shift_v else day_v

            if display_val:
                indicator = html.Span([
                    html.Span("Filtered by: ", style={
                        'fontSize': '12px', 'color': 'var(--text-light)'}),
                    html.Span(str(display_val), style={
                        'fontSize': '12px', 'fontWeight': '600',
                        'color': accent_color,
                        'background': accent_color + '18',
                        'padding': '2px 10px', 'borderRadius': '12px',
                        'marginLeft': '4px',
                    }),
                ])
                btn_style = show_btn

        # Find top machine from filtered data
        if not filtered_machine.empty:
            top_agg = filtered_machine.groupby('machine_id')['total_hours'].sum() \
                          .sort_values(ascending=False)
            top_m_name = str(top_agg.index[0])
            top_m_hrs  = float(top_agg.iloc[0])
        else:
            top_m_name = '—'
            top_m_hrs  = 0

        # MTBA = Available Time / Total Events
        mtba_hrs = None
        try:
            _sd = store_data.get('start_date', '')
            _ed = store_data.get('end_date', '')
            _sh = store_data.get('shift', '') or None
            _mc = store_data.get('machine_count', 0)
            total_evts_for_mtba = int(filtered_reason['events'].sum()) if not filtered_reason.empty else 0
            if _sd and _ed and _mc > 0 and total_evts_for_mtba > 0:
                from pages.utilization import _calc_available_min
                avail = _calc_available_min(_sd, _ed, _sh, _mc)
                mtba_hrs = round(avail / 60.0 / total_evts_for_mtba, 1)
        except Exception:
            mtba_hrs = None

        kpis = _make_kpi_row(filtered_reason, daily_shift_df, accent_color,
                             top_machine_name=top_m_name,
                             top_machine_hrs=top_m_hrs,
                             mtba_hrs=mtba_hrs)

        # Use symptom_cause table for M/C DOWN, regular reason table for SETUP
        sc_raw = store_data.get('symptom_cause', '')
        has_sc = bool(sc_raw)
        sc_df  = pd.read_json(sc_raw, orient='split') if has_sc else pd.DataFrame()

        click_src = click_filter.get('source') if click_filter else None

        # Events table (event-level for Downtime, aggregated for Setup)
        ev_raw = store_data.get('events', '')
        ev_df = pd.read_json(ev_raw, orient='split') if ev_raw else pd.DataFrame()

        if ev_df is not None and not ev_df.empty and prefix == 'dt':
            # Event-level table for Downtime section
            filtered_ev = ev_df.copy()
            if click_filter:
                src = click_filter.get('source')
                val = click_filter.get('value', '')
                if src == 'pareto' and val:
                    filtered_ev = ev_df[ev_df['symptom'] == val]
                elif src == 'machine' and val:
                    filtered_ev = ev_df[ev_df['machine_id'] == val]
                elif src == 'trend':
                    day_v = click_filter.get('day', '')
                    if day_v and 'event_time' in ev_df.columns:
                        ev_df['_day'] = pd.to_datetime(ev_df['event_time'], errors='coerce').dt.strftime('%b %d')
                        filtered_ev = ev_df[ev_df['_day'] == day_v]
                        filtered_ev = filtered_ev.drop(columns=['_day'], errors='ignore')
                if filtered_ev.empty:
                    filtered_ev = ev_df
            table = _make_events_table(filtered_ev, table_id)
        elif filtered_reason.empty:
            table = html.Div("No data for selection.",
                             style={'color': MED_GRAY, 'padding': '20px'})
        elif has_sc and not sc_df.empty and click_src in (None, 'pareto'):
            filtered_sc = sc_df.copy()
            if click_src == 'pareto':
                clicked_val = click_filter.get('value', '')
                filtered_sc = sc_df[sc_df['symptom'] == clicked_val]
                if filtered_sc.empty:
                    filtered_sc = sc_df
            table = _make_symptom_cause_table(filtered_sc, table_id,
                                              repair_color=accent_color)
        else:
            table = _make_detail_table(filtered_reason, table_id,
                                       repair_color=accent_color)

        # Build Pareto + Machine bar from filtered data
        pareto_fig  = _make_pareto(filtered_reason, accent_color, bar_label)
        machine_fig, _ = _make_machine_bar(filtered_machine)

        if prefix == 'dt':
            # For dt: pass events data to store, let filter callback render table
            ev_raw = store_data.get('events', '')
            return kpis, pareto_fig, machine_fig, table, indicator, btn_style, ev_raw
        return kpis, pareto_fig, machine_fig, table, indicator, btn_style


# ── Register both sections ────────────────────────────────────────────────────
from config import COLUMN_MAP as _CM
_sym_col = _CM.get('symptom', 'des_job') or 'des_job'

_register_section('dt',    ['M/C DOWN'],
                  RED, 'Downtime Hours', 'dt-detail-table',
                  reason_col=_sym_col)
_register_section('setup', ['SETUP', 'SETUP BY OPERATOR'],
                  LIGHT_BLUE, 'Setup Hours', 'setup-detail-table',
                  type_toggle_id='setup-type-toggle')


# ── Event Detail filter dropdowns + table ─────────────────────────────────────
@callback(
    Output('evt-filter-machine', 'options'),
    Output('evt-filter-symptom', 'options'),
    Output('evt-filter-cause',   'options'),
    Output('evt-filter-tech',    'options'),
    Input('dt-events-raw', 'data'),
)
def populate_event_filters(ev_raw):
    """Populate dropdown options from events data."""
    empty = []
    if not ev_raw:
        return empty, empty, empty, empty
    ev = pd.read_json(ev_raw, orient='split')
    if ev.empty:
        return empty, empty, empty, empty

    def _opts(col):
        vals = ev[col].dropna().unique()
        return sorted([{'label': str(v), 'value': str(v)} for v in vals if str(v).strip()],
                      key=lambda x: x['label'])

    return (_opts('machine_id'), _opts('symptom'), _opts('cause'),
            _opts('tech') if 'tech' in ev.columns else empty)


@callback(
    Output('dt-table', 'children', allow_duplicate=True),
    Input('evt-search-btn',    'n_clicks'),
    Input('evt-filter-type',   'value'),
    State('evt-filter-machine', 'value'),
    State('evt-filter-symptom', 'value'),
    State('evt-filter-cause',   'value'),
    State('evt-filter-tech',    'value'),
    State('dt-events-raw',      'data'),
    prevent_initial_call=True,
)
def filter_event_table(n_clicks, type_filter, machines, symptoms, causes,
                       techs, ev_raw):
    """Filter events table by dropdown selections."""
    if not ev_raw:
        return html.Div("No events data.", style={'color': MED_GRAY, 'padding': '20px'})

    ev = pd.read_json(ev_raw, orient='split')
    if ev.empty:
        return html.Div("No events.", style={'color': MED_GRAY, 'padding': '20px'})

    # Apply filters
    if type_filter:
        ev = ev[ev['job_type'].isin(type_filter)]
    if machines:
        ev = ev[ev['machine_id'].isin(machines)]
    if symptoms:
        ev = ev[ev['symptom'].isin(symptoms)]
    if causes:
        ev = ev[ev['cause'].isin(causes)]
    if techs and 'tech' in ev.columns:
        ev = ev[ev['tech'].isin(techs)]

    if ev.empty:
        return html.Div("No matching events.", style={'color': MED_GRAY, 'padding': '20px'})

    return _make_events_table(ev, 'dt-detail-table')



# ── CSV exports ───────────────────────────────────────────────────────────────
def _export_csv(table_data, filename):
    if not table_data:
        return None
    df = pd.DataFrame(table_data)
    col_rename = {
        'reason': 'Reason', 'events': 'Events',
        'repair_hrs': 'Repair Hours', 'wait_hrs': 'Wait Hours',
        'total_hrs': 'Total Hours',
        'avg_repair_min': 'Avg Repair (min)', 'avg_wait_min': 'Avg Wait (min)',
    }
    df = df.rename(columns=col_rename)
    return dcc.send_data_frame(df.to_csv, filename, index=False)


@callback(
    Output('dt-download-csv', 'data'),
    Input('btn-dt-export-csv', 'n_clicks'),
    State('dt-detail-table', 'data'),
    prevent_initial_call=True,
)
def export_dt_csv(n, data):
    return _export_csv(data, 'downtime_detail.csv')


@callback(
    Output('setup-download-csv', 'data'),
    Input('btn-setup-export-csv', 'n_clicks'),
    State('setup-detail-table', 'data'),
    prevent_initial_call=True,
)
def export_setup_csv(n, data):
    return _export_csv(data, 'setup_detail.csv')
