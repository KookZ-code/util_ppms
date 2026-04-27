"""Technician Performance Review — composite scoring with A/B/C/D grades."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from components.header import make_page_header, make_chart_title
from components.kpi_card import make_kpi_card
from components.filters import make_filter_bar
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    MED_GRAY, BG_GRAY, WHITE, CHART_COLORS,
)

dash.register_page(__name__, path='/timeline', name='Tech Performance')

# ── Scoring constants ─────────────────────────────────────────────────────────
WEIGHTS = {
    'mttr':        0.30,
    'response':    0.20,
    'ftfr':        0.25,
    'volume':      0.15,
    'versatility': 0.10,
}
# Normalisation thresholds: (floor_0pt, ceiling_100pt)
THRESHOLDS = {
    'mttr':        (480, 15),     # lower is better
    'response':    (120, 5),      # lower is better
    'ftfr':        (20, 80),      # higher is better
    'volume':      (0.3, 1.5),    # ratio to team avg; higher is better
    'versatility': (0, 3),        # area count; 1 area = 33pts (normal)
}
GRADE_MAP = [
    (85, 'A', GREEN),
    (70, 'B', PRIMARY_BLUE),
    (55, 'C', ORANGE),
    (0,  'D', RED),
]
METRIC_LABELS = {
    'mttr': 'MTTR',
    'response': 'Response',
    'ftfr': 'FTFR',
    'volume': 'Volume',
    'versatility': 'Versatility',
}


def _grade_badge(grade, range_text, color):
    """Small colored badge row for methodology panel."""
    return html.Div([
        html.Span(f" {grade} ", style={
            'display': 'inline-block', 'width': '28px', 'textAlign': 'center',
            'fontWeight': '700', 'fontSize': '13px', 'color': '#fff',
            'backgroundColor': color, 'borderRadius': '4px',
            'marginRight': '10px', 'padding': '2px 0',
        }),
        html.Span(range_text, style={'fontSize': '13px', 'color': '#4A4A4A'}),
    ], style={'marginBottom': '6px'})


def _norm(val, floor, ceil, lower_is_better=False):
    """Normalize a value to 0-100 scale, clamped."""
    if lower_is_better:
        score = (floor - val) / max(floor - ceil, 1) * 100
    else:
        score = (val - floor) / max(ceil - floor, 1) * 100
    return max(0, min(100, score))


def _grade(score):
    for threshold, label, color in GRADE_MAP:
        if score >= threshold:
            return label, color
    return 'D', RED


def compute_scores(df):
    """Add normalized metric columns + composite score + grade to df."""
    avg_jobs = df['job_count'].mean() if len(df) else 1

    df['n_mttr'] = df['avg_repair_min'].apply(
        lambda v: _norm(v, *THRESHOLDS['mttr'], lower_is_better=True))
    df['n_response'] = df['avg_response_min'].apply(
        lambda v: _norm(v, *THRESHOLDS['response'], lower_is_better=True))
    df['n_ftfr'] = df['ftfr_pct'].apply(
        lambda v: _norm(v, *THRESHOLDS['ftfr']))
    df['n_volume'] = (df['job_count'] / max(avg_jobs, 1)).apply(
        lambda v: _norm(v, *THRESHOLDS['volume']))
    df['n_versatility'] = df['area_count'].apply(
        lambda v: _norm(v, *THRESHOLDS['versatility']))

    df['score'] = (
        df['n_mttr']        * WEIGHTS['mttr'] +
        df['n_response']    * WEIGHTS['response'] +
        df['n_ftfr']        * WEIGHTS['ftfr'] +
        df['n_volume']      * WEIGHTS['volume'] +
        df['n_versatility'] * WEIGHTS['versatility']
    ).round(1)

    df['grade'] = df['score'].apply(lambda s: _grade(s)[0])
    df['grade_color'] = df['score'].apply(lambda s: _grade(s)[1])
    return df


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    make_page_header("Technician Performance Review"),
    make_filter_bar(show_machine=False, show_shift=True, show_job_type=True,
                    default_days=30),

    # Technician filters row
    html.Div(
        dbc.Row([
            dbc.Col([
                html.Label("Supervisor", className='filter-label'),
                dcc.Dropdown(
                    id='tp-filter-supv',
                    options=[],
                    value=None, multi=True, placeholder='All Supervisors',
                    style={'fontSize': '13px'},
                ),
            ], lg=3, md=4, sm=12),
            dbc.Col([
                html.Label("Job Desc", className='filter-label'),
                dcc.Dropdown(
                    id='tp-filter-role',
                    options=[
                        {'label': 'Technician', 'value': 'Technician'},
                        {'label': 'PM',         'value': 'PM'},
                    ],
                    value=None, multi=True, placeholder='All Roles',
                    style={'fontSize': '13px'},
                ),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Group", className='filter-label'),
                dcc.Dropdown(
                    id='tp-filter-group',
                    options=[
                        {'label': 'Day',     'value': 'Day'},
                        {'label': 'Shift-1', 'value': 'Shift-1'},
                        {'label': 'Shift-2', 'value': 'Shift-2'},
                    ],
                    value=None, multi=True, placeholder='All Groups',
                    style={'fontSize': '13px'},
                ),
            ], lg=2, md=3, sm=12),
        ], className='g-2 align-items-end'),
        className='filter-bar', style={'paddingTop': '8px', 'marginTop': '-12px',
                                       'borderTop': 'none', 'borderTopLeftRadius': '0',
                                       'borderTopRightRadius': '0'},
    ),

    # KPI cards
    dbc.Row(id='tp-kpi-row', className='g-3 mb-3'),

    # Leaderboard + Radar
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Performance Leaderboard", "Ranked"),
                html.Div(id='tp-leaderboard'),
            ], className='chart-card'),
        ], lg=7, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Skill Profile", "Radar"),
                dcc.Graph(id='tp-radar', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=5, md=12),
    ]),

    # Score Heatmap
    html.Div([
        make_chart_title("Score Breakdown", "All Technicians"),
        dcc.Graph(id='tp-heatmap', config={'displayModeBar': False}),
    ], className='chart-card'),

    # Grade distribution + Supervisor comparison
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Grade Distribution", "Count"),
                dcc.Graph(id='tp-grade-donut', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=5, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Average Score by Supervisor", "Comparison"),
                dcc.Graph(id='tp-supv-bar', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=7, md=12),
    ]),

    # Scoring Methodology (collapsible)
    html.Div([
        make_chart_title("Scoring Methodology", "How it works"),
        dbc.Accordion([
            dbc.AccordionItem([
                dbc.Row([
                    dbc.Col([
                        html.H6("Metrics & Weights",
                                style={'fontWeight': '700', 'marginBottom': '10px',
                                       'fontSize': '13px'}),
                        dash_table.DataTable(
                            columns=[
                                {'name': 'Metric',    'id': 'metric'},
                                {'name': 'Weight',    'id': 'weight'},
                                {'name': 'Best (100)', 'id': 'best'},
                                {'name': 'Worst (0)', 'id': 'worst'},
                                {'name': 'Direction', 'id': 'dir'},
                            ],
                            data=[
                                {'metric': 'MTTR (Repair Time)',
                                 'weight': '30%', 'best': '15 min',
                                 'worst': '480 min', 'dir': 'Lower = Better'},
                                {'metric': 'Response Time',
                                 'weight': '20%', 'best': '5 min',
                                 'worst': '120 min', 'dir': 'Lower = Better'},
                                {'metric': 'FTFR (First-Time Fix)',
                                 'weight': '25%', 'best': '80%',
                                 'worst': '20%', 'dir': 'Higher = Better'},
                                {'metric': 'Job Volume',
                                 'weight': '15%', 'best': '1.5x avg',
                                 'worst': '0.3x avg', 'dir': 'Higher = Better'},
                                {'metric': 'Versatility (Areas)',
                                 'weight': '10%', 'best': '3+ areas',
                                 'worst': '0 areas', 'dir': 'Higher = Better'},
                            ],
                            style_header={
                                'backgroundColor': '#EEF0F4', 'color': '#1A1F2E',
                                'fontWeight': '600', 'fontSize': '11px',
                                'padding': '8px 10px', 'border': 'none',
                                'fontFamily': 'Inter, Calibri, sans-serif',
                            },
                            style_cell={
                                'fontSize': '12px', 'padding': '6px 10px',
                                'fontFamily': 'Inter, Calibri, sans-serif',
                                'textAlign': 'left', 'border': 'none',
                                'borderBottom': '1px solid #EEF0F4',
                            },
                            style_as_list_view=True,
                        ),
                    ], lg=7, md=12),
                    dbc.Col([
                        html.H6("Grade System",
                                style={'fontWeight': '700', 'marginBottom': '10px',
                                       'fontSize': '13px'}),
                        html.Div([
                            _grade_badge('A', '85 - 100', GREEN),
                            _grade_badge('B', '70 - 84', PRIMARY_BLUE),
                            _grade_badge('C', '55 - 69', ORANGE),
                            _grade_badge('D', 'Below 55', RED),
                        ]),
                        html.Hr(style={'margin': '12px 0', 'opacity': '0.2'}),
                        html.H6("Definitions",
                                style={'fontWeight': '700', 'marginBottom': '8px',
                                       'fontSize': '13px'}),
                        html.Ul([
                            html.Li([html.B("MTTR"), " — Mean Time To Repair "
                                     "(date_ack to date_close)"]),
                            html.Li([html.B("Response"), " — Waiting time "
                                     "(operator call to tech acknowledge)"]),
                            html.Li([html.B("FTFR"), " — First-Time Fix Rate: "
                                     "same tech + same machine has no repeat "
                                     "M/C DOWN within 7 days"]),
                            html.Li([html.B("Volume"), " — Job count normalized "
                                     "to team average"]),
                            html.Li([html.B("Versatility"), " — Number of "
                                     "distinct machine areas covered"]),
                        ], style={'fontSize': '12px', 'lineHeight': '1.8',
                                  'paddingLeft': '18px', 'color': '#4A4A4A'}),
                    ], lg=5, md=12),
                ]),
            ], title="How is the Performance Score calculated?"),
        ], start_collapsed=True, className='mb-3'),
    ], className='chart-card'),

    # Hidden store for score data (used by radar click callback)
    dcc.Store(id='tp-score-store'),

], className='page-container')


def _empty():
    fig = go.Figure()
    fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Calibri, Segoe UI, sans-serif'))
    return fig


# ── Load supervisor options ────────────────────────────────────────────────────
@callback(
    Output('tp-filter-supv', 'options'),
    Input('auto-refresh', 'n_intervals'),
)
def load_supv_options(n):
    from db import query_df
    from utils.queries import tech_list_query
    try:
        tl = query_df(tech_list_query())
        supvs = sorted(tl['Supv'].dropna().unique())
        return [{'label': s, 'value': s} for s in supvs]
    except Exception:
        return []


# ── Main callback — compute scores + build all charts ─────────────────────────
@callback(
    Output('tp-kpi-row',       'children'),
    Output('tp-leaderboard',   'children'),
    Output('tp-heatmap',       'figure'),
    Output('tp-grade-donut',   'figure'),
    Output('tp-supv-bar',      'figure'),
    Output('tp-score-store',   'data'),
    Output('tp-radar',         'figure'),
    Input('auto-refresh',      'n_intervals'),
    Input('filter-date-range', 'start_date'),
    Input('filter-date-range', 'end_date'),
    Input('filter-area',       'value'),
    Input('util-filter-shift', 'value'),
    Input('filter-job-type',   'value'),
    Input('tp-filter-supv',    'value'),
    Input('tp-filter-role',    'value'),
    Input('tp-filter-group',   'value'),
)
def update_scores(n_intervals, start_date, end_date, areas, shift, job_type,
                  supv_filter, role_filter, group_filter):
    from db import query_df
    from config import VIEW_NAME
    from utils.queries import build_tech_where, tech_score_metrics, tech_list_query

    ef = _empty()
    where, params = build_tech_where(start_date, end_date, areas, shift, job_type)

    try:
        metrics = query_df(tech_score_metrics(VIEW_NAME, where), params)
        tech_list = query_df(tech_list_query())
        # Merge Oracle tech metrics
        try:
            from config import ORA_ENABLED
            if ORA_ENABLED:
                from oracle_db import fetch_oracle_data
                from utils.oracle_agg import ora_tech_score_metrics
                if not areas or any(a in ('ISO', 'FS') for a in areas):
                    ora = fetch_oracle_data(start_date, end_date, areas, shift)
                    if ora is not None:
                        ora_metrics = ora_tech_score_metrics(ora)
                        if not ora_metrics.empty:
                            metrics = pd.concat([metrics, ora_metrics], ignore_index=True)
                            # Re-aggregate if same tech appears in both sources
                            metrics = metrics.groupby('technician').agg(
                                job_count=('job_count', 'sum'),
                                avg_response_min=('avg_response_min', 'mean'),
                                avg_repair_min=('avg_repair_min', 'mean'),
                                area_count=('area_count', 'max'),
                                ftfr_pct=('ftfr_pct', 'mean'),
                            ).reset_index()
        except Exception:
            pass
    except Exception as e:
        err = html.Div(f"Error: {e}", style={'color': RED, 'padding': '16px'})
        return [err], err, ef, ef, ef, None, ef

    if metrics.empty:
        msg = html.Div("No data for selected filters.",
                        style={'color': MED_GRAY, 'padding': '20px'})
        return [], msg, ef, ef, ef, None, ef

    # Join with TechnicianList FIRST (inner join = only registered techs)
    tech_list.columns = [c.strip() for c in tech_list.columns]
    merged = metrics.merge(
        tech_list.rename(columns={'Badge': 'technician', 'NameTH': 'name_th',
                                  'Name': 'name_en', 'Supv': 'supv',
                                  'Group': 'shift_group', 'AERA': 'home_area',
                                  'Job Desc': 'role'}),
        on='technician', how='inner',
    )

    # Apply technician-list filters
    for col, fval in [('supv', supv_filter), ('role', role_filter),
                      ('shift_group', group_filter)]:
        if fval:
            if isinstance(fval, str):
                fval = [fval]
            merged = merged[merged[col].isin(fval)]

    if merged.empty:
        msg = html.Div("No matching technicians found.",
                        style={'color': MED_GRAY, 'padding': '20px'})
        return [], msg, ef, ef, ef, None, ef

    # Compute scores AFTER filtering to registered techs only
    scored = compute_scores(merged)
    scored['display_name'] = scored['name_en'].fillna(scored['technician'])
    scored = scored.sort_values('score', ascending=False).reset_index(drop=True)
    scored['rank'] = range(1, len(scored) + 1)

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    team_avg = scored['score'].mean()
    best = scored.iloc[0] if len(scored) else None
    avg_mttr = int(scored['avg_repair_min'].mean())
    avg_resp = int(scored['avg_response_min'].mean())

    team_grade, team_color = _grade(team_avg)
    kpis = [
        dbc.Col(make_kpi_card(f"{team_avg:.0f}", "Team Avg Score",
                              team_color, unit="pts",
                              subtitle=f"Grade {team_grade}", icon="📊"),
                lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(
            best['display_name'] if best is not None else '-',
            "Top Performer",
            GREEN, subtitle=f"Score {best['score']:.0f}" if best is not None else '',
            icon="🏆"), lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(avg_mttr, "Avg MTTR",
                              ORANGE, unit="min", icon="🔧"),
                lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(avg_resp, "Avg Response",
                              LIGHT_BLUE, unit="min", icon="⏱"),
                lg=3, md=6, sm=6),
    ]

    # ── Leaderboard Table ─────────────────────────────────────────────────────
    tbl = scored[['rank', 'technician', 'display_name', 'score', 'grade',
                  'avg_repair_min', 'avg_response_min', 'ftfr_pct',
                  'job_count', 'area_count']].copy()
    tbl['avg_repair_min'] = tbl['avg_repair_min'].astype(int)
    tbl['avg_response_min'] = tbl['avg_response_min'].astype(int)
    tbl['ftfr_pct'] = tbl['ftfr_pct'].round(1)

    leaderboard = dash_table.DataTable(
        id='tp-leader-table',
        columns=[
            {'name': '#',          'id': 'rank'},
            {'name': 'Badge',      'id': 'technician'},
            {'name': 'Technician', 'id': 'display_name'},
            {'name': 'Score',      'id': 'score'},
            {'name': 'Grade',      'id': 'grade'},
            {'name': 'MTTR (min)', 'id': 'avg_repair_min'},
            {'name': 'Resp (min)', 'id': 'avg_response_min'},
            {'name': 'FTFR %',    'id': 'ftfr_pct'},
            {'name': 'Jobs',       'id': 'job_count'},
            {'name': 'Areas',      'id': 'area_count'},
        ],
        data=tbl.to_dict('records'),
        sort_action='native', sort_mode='multi',
        page_action='native', page_size=15,
        row_selectable='single',
        style_header={
            'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
            'fontWeight': '600', 'fontSize': '12px', 'padding': '10px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
        style_cell={
            'fontSize': '13px', 'padding': '8px 12px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'textAlign': 'left', 'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
        },
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            # Grade colors
            {'if': {'filter_query': '{grade} = "A"', 'column_id': 'grade'},
             'color': GREEN, 'fontWeight': '700'},
            {'if': {'filter_query': '{grade} = "B"', 'column_id': 'grade'},
             'color': PRIMARY_BLUE, 'fontWeight': '700'},
            {'if': {'filter_query': '{grade} = "C"', 'column_id': 'grade'},
             'color': ORANGE, 'fontWeight': '700'},
            {'if': {'filter_query': '{grade} = "D"', 'column_id': 'grade'},
             'color': RED, 'fontWeight': '700'},
            # Score column bold
            {'if': {'column_id': 'score'}, 'fontWeight': '700'},
            # Rank column
            {'if': {'column_id': 'rank'}, 'fontWeight': '600',
             'color': MED_GRAY, 'width': '40px'},
            {'if': {'column_id': 'technician'}, 'color': MED_GRAY,
             'fontSize': '11px'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )

    # ── Score Heatmap (top 25 techs × 5 metrics) ─────────────────────────────
    top_h = scored.head(25)
    heat_metrics = ['n_mttr', 'n_response', 'n_ftfr', 'n_volume', 'n_versatility']
    heat_labels = ['MTTR', 'Response', 'FTFR', 'Volume', 'Versatility']
    z = top_h[heat_metrics].values
    y_names = top_h['display_name'].tolist()

    # Reverse so rank 1 is at top
    z = z[::-1]
    y_names = y_names[::-1]

    heatmap = go.Figure(go.Heatmap(
        z=z, x=heat_labels, y=y_names,
        colorscale=[
            [0, '#FDDEDE'], [0.30, '#FEC89A'], [0.50, '#FFF3B0'],
            [0.65, '#D0EFFF'], [0.80, '#B7E4C7'], [1.0, '#52B788'],
        ],
        zmin=0, zmax=100,
        texttemplate='%{z:.0f}',
        textfont=dict(size=10, color='#1A1F2E'),
        hovertemplate='<b>%{y}</b><br>%{x}: %{z:.0f}/100<extra></extra>',
        colorbar=dict(title='Score', tickvals=[0, 25, 50, 75, 100]),
    ))
    heatmap.update_layout(
        template='plotly_white',
        height=max(320, len(y_names) * 24 + 80),
        margin=dict(t=10, b=30, l=10, r=10),
        xaxis=dict(side='top', tickfont=dict(size=11)),
        yaxis=dict(automargin=True, tickfont=dict(size=11)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Grade Distribution Donut ──────────────────────────────────────────────
    grade_counts = scored['grade'].value_counts()
    grade_order = ['A', 'B', 'C', 'D']
    grade_colors = [GREEN, PRIMARY_BLUE, ORANGE, RED]
    g_labels, g_vals, g_cols = [], [], []
    for g, c in zip(grade_order, grade_colors):
        cnt = grade_counts.get(g, 0)
        if cnt > 0:
            g_labels.append(f"Grade {g}")
            g_vals.append(cnt)
            g_cols.append(c)

    donut = go.Figure(go.Pie(
        labels=g_labels, values=g_vals,
        hole=0.55, marker=dict(colors=g_cols),
        textinfo='label+value',
        textfont=dict(size=12),
        hovertemplate='<b>%{label}</b>: %{value} techs<extra></extra>',
    ))
    donut.update_layout(
        template='plotly_white', height=320,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
        annotations=[dict(
            text=f"<b>{len(scored)}</b><br>Techs",
            x=0.5, y=0.5, font_size=16, showarrow=False,
            font=dict(family='Inter, Calibri, sans-serif'),
        )],
    )

    # ── Supervisor Comparison Bar ─────────────────────────────────────────────
    supv_fig = _empty()
    if 'supv' in scored.columns and scored['supv'].notna().any():
        supv_avg = (scored[scored['supv'].notna()]
                    .groupby('supv')['score']
                    .agg(['mean', 'count'])
                    .reset_index()
                    .sort_values('mean', ascending=True))
        supv_colors = [_grade(v)[1] for v in supv_avg['mean']]
        supv_fig = go.Figure(go.Bar(
            y=supv_avg['supv'],
            x=supv_avg['mean'].round(1),
            orientation='h',
            marker_color=supv_colors,
            text=[f"{v:.0f} ({int(c)} techs)"
                  for v, c in zip(supv_avg['mean'], supv_avg['count'])],
            textposition='outside',
            textfont=dict(size=11),
            hovertemplate='<b>%{y}</b>: %{x:.1f} avg score<extra></extra>',
        ))
        supv_fig.update_layout(
            template='plotly_white', height=280,
            margin=dict(t=10, b=30, l=10, r=80),
            xaxis=dict(title='Average Score', range=[0, 110],
                       showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
            yaxis=dict(automargin=True, tickfont=dict(size=12)),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri, Segoe UI, sans-serif'),
        )

    # ── Default Radar (top tech) ──────────────────────────────────────────────
    radar_fig = _build_radar(scored, 0)

    # Store score data for radar click callback
    store_cols = ['rank', 'display_name', 'score', 'grade',
                  'n_mttr', 'n_response', 'n_ftfr', 'n_volume', 'n_versatility']
    store_data = scored[store_cols].to_dict('records')

    return kpis, leaderboard, heatmap, donut, supv_fig, store_data, radar_fig


def _build_radar(scored_df, row_idx):
    """Build radar chart for a specific technician vs team average."""
    metrics = ['n_mttr', 'n_response', 'n_ftfr', 'n_volume', 'n_versatility']
    labels = ['MTTR', 'Response', 'FTFR', 'Volume', 'Versatility']

    if isinstance(scored_df, pd.DataFrame):
        team_avg = scored_df[metrics].mean().tolist()
        if row_idx < len(scored_df):
            tech = scored_df.iloc[row_idx]
            tech_vals = [tech[m] for m in metrics]
            tech_name = tech.get('display_name', f'#{row_idx+1}')
            tech_score = tech.get('score', 0)
            tech_grade = tech.get('grade', '-')
        else:
            tech_vals = team_avg
            tech_name = 'Team Average'
            tech_score = sum(team_avg) / len(team_avg)
            tech_grade = '-'
    else:
        # From store data (list of dicts)
        records = scored_df
        team_avg = [np.mean([r[m] for r in records]) for m in metrics]
        if row_idx < len(records):
            rec = records[row_idx]
            tech_vals = [rec[m] for m in metrics]
            tech_name = rec.get('display_name', f'#{row_idx+1}')
            tech_score = rec.get('score', 0)
            tech_grade = rec.get('grade', '-')
        else:
            tech_vals = team_avg
            tech_name = 'Team Average'
            tech_score = 0
            tech_grade = '-'

    # Close the polygon
    tech_vals_closed = tech_vals + [tech_vals[0]]
    avg_closed = team_avg + [team_avg[0]]
    labels_closed = labels + [labels[0]]

    grade_label, grade_color = _grade(tech_score)

    fig = go.Figure()
    # Team average (background)
    fig.add_trace(go.Scatterpolar(
        r=avg_closed, theta=labels_closed,
        fill='toself', fillcolor='rgba(138,150,168,0.1)',
        line=dict(color=MED_GRAY, width=1, dash='dot'),
        name='Team Avg',
        hovertemplate='Team Avg<br>%{theta}: %{r:.0f}<extra></extra>',
    ))
    # Selected technician
    fig.add_trace(go.Scatterpolar(
        r=tech_vals_closed, theta=labels_closed,
        fill='toself',
        fillcolor=f'rgba({int(grade_color[1:3],16)},{int(grade_color[3:5],16)},{int(grade_color[5:7],16)},0.12)',
        line=dict(color=grade_color, width=2.5),
        name=tech_name,
        hovertemplate=f'{tech_name}<br>%{{theta}}: %{{r:.0f}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=True,
                            tickfont=dict(size=9), gridcolor='rgba(128,128,128,0.2)'),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        template='plotly_white', height=350,
        margin=dict(t=50, b=30, l=50, r=50),
        legend=dict(orientation='h', y=-0.05, font=dict(size=11)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
        title=dict(
            text=f"<b>{tech_name[:25]}</b> — {tech_score:.0f} ({tech_grade})",
            font=dict(size=14, color=grade_color,
                      family='DM Sans, Calibri, sans-serif'),
            x=0.5, xanchor='center',
        ),
    )
    return fig


# ── Radar update on leaderboard row click ─────────────────────────────────────
@callback(
    Output('tp-radar', 'figure', allow_duplicate=True),
    Input('tp-leader-table', 'selected_rows'),
    State('tp-score-store', 'data'),
    prevent_initial_call=True,
)
def update_radar_on_click(selected_rows, store_data):
    if not selected_rows or not store_data:
        return _empty()
    row_idx = selected_rows[0]
    return _build_radar(store_data, row_idx)
