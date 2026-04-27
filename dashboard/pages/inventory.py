"""Machine Inventory — quick lookup for machines, models, areas, packages."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd

from components.header import make_page_header, make_chart_title
from components.kpi_card import make_kpi_card
from utils.colors import (
    PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE,
    MED_GRAY, WHITE, CHART_COLORS,
)

dash.register_page(__name__, path='/inventory', name='Inventory')

# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    make_page_header("Machine Inventory"),

    # Filter bar
    html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Area", className='filter-label'),
                dcc.Dropdown(id='inv-filter-area', options=[], value=None,
                             multi=True, placeholder='All Areas',
                             style={'fontSize': '13px'}),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Model", className='filter-label'),
                dcc.Dropdown(id='inv-filter-model', options=[], value=None,
                             multi=True, placeholder='All Models',
                             style={'fontSize': '13px'}),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Manufacturer", className='filter-label'),
                dcc.Dropdown(id='inv-filter-mfg', options=[], value=None,
                             multi=True, placeholder='All Mfg',
                             style={'fontSize': '13px'}),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Flags", className='filter-label'),
                dbc.Checklist(
                    id='inv-flag-toggles',
                    options=[
                        {'label': ' KEY', 'value': 'KEY'},
                        {'label': ' Auto', 'value': 'AUTO'},
                        {'label': ' Gold', 'value': 'GOLD'},
                    ],
                    value=[], inline=True,
                    style={'fontSize': '12px', 'paddingTop': '6px'},
                ),
            ], lg=2, md=3, sm=12),
            dbc.Col([
                html.Label("Search", className='filter-label'),
                dcc.Input(
                    id='inv-search', type='text', placeholder='Machine or description...',
                    debounce=True,
                    style={'fontSize': '13px', 'width': '100%', 'padding': '6px 10px',
                           'border': '1px solid var(--border)', 'borderRadius': '6px',
                           'background': 'var(--input-bg)', 'color': 'var(--text)'},
                ),
            ], lg=2, md=3, sm=12),
        ], className='g-2 align-items-end'),
    ], className='filter-bar'),

    # KPI row
    dbc.Row(id='inv-kpi-row', className='g-3 mb-3'),

    # Charts row
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Machines by Area", "Count"),
                dcc.Graph(id='inv-chart-area', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=5, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("Top 15 Models", "Count"),
                dcc.Graph(id='inv-chart-model', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=4, md=12),
        dbc.Col([
            html.Div([
                make_chart_title("By Manufacturer", "Count"),
                dcc.Graph(id='inv-chart-mfg', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=3, md=12),
    ]),

    # Treemap: Area → Model → Machine hierarchy
    html.Div([
        make_chart_title("Equipment Health Map (Last 7 Days)", "Size = Downtime Hrs · Color = Health"),
        dcc.Graph(id='inv-treemap', config={'displayModeBar': False}),
    ], className='chart-card'),

    # Machine Age Distribution
    html.Div([
        make_chart_title("Machine Age Distribution", "Years Since Install"),
        dcc.Graph(id='inv-chart-age', config={'displayModeBar': False}),
    ], className='chart-card'),

    # Machine table
    html.Div([
        html.Div(id='inv-table-header'),
        dcc.Download(id='inv-download-csv'),
        html.Div(id='inv-machine-table'),
    ], className='chart-card'),

], className='page-container')


# ── Load all machine data once ────────────────────────────────────────────────
def _load_machines():
    # Phase 3: API path first, fallback to direct DB
    try:
        from api_client import USE_API, fetch_inventory_machines
        if USE_API:
            df = fetch_inventory_machines()
            if not df.empty:
                return df
    except Exception as _api_err:
        import logging
        logging.warning(f"_load_machines API failed ({_api_err}), fallback to DB")

    from db import query_df
    from utils.queries import inventory_all_machines
    df = query_df(inventory_all_machines())
    # Ensure flag columns are int (SQL bit → pandas may read as float/object)
    for col in ['flag_key', 'flag_automotive', 'flag_gold', 'flag_pm', 'flag_downtime']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    # Trim whitespace from text columns to prevent duplicates
    for col in ['model', 'mfg', 'code_machine', 'des_machine', 'short_name', 'id_operation']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', '')

    # Normalize similar model names (MOLD SP80N variants etc.)
    model_map = {
        'GP-PRO SP80N':    'GP-PRO8 SP80N',
        'GP-PRO-8 SP80N':  'GP-PRO8 SP80N',
        'GP-PRO-8-SP80N':  'GP-PRO8 SP80N',
        'GP-PRO8-SP80N':   'GP-PRO8 SP80N',
        'GP-PRO-8-SP170N': 'GP-PRO8 SP170N',
        'GP-PRO8-SP170N':  'GP-PRO8 SP170N',
        'DP80-8-MOUT':     'DP80-8-M',
        'GP-ELF-D24084':   'GP-ELF',
    }
    if 'model' in df.columns:
        df['model'] = df['model'].replace(model_map)

    # MOLD: exclude sub-machines (Press 1-4, L, R suffixes) — count main machines only
    mold_mask = df['id_operation'] == 'MOLD'
    sub_pattern = r'(?i)(\s+Press\s*\d+|L|R)$'
    mold_sub = mold_mask & df['code_machine'].str.contains(sub_pattern, regex=True, na=False)
    df = df[~mold_sub]

    # WB: count HEADS not machines
    # Include L/R heads where base machine is key (even if L/R itself is flag_key=0)
    # Exclude base machines that have L/R children (count heads instead)
    wb_mask = df['id_operation'] == 'WB'
    wb_lr_pattern = r'[LR]$'

    # Get all WB L/R records from the FULL dataset (before key filter may have removed them)
    wb_all = query_df(inventory_all_machines())
    wb_all_lr = wb_all[(wb_all['id_operation'] == 'WB') &
                        wb_all['code_machine'].astype(str).str.strip().str.match(r'.*[LR]$', na=False)]
    # Find base names that have L/R children
    wb_all_lr['base_name'] = wb_all_lr['code_machine'].astype(str).str.strip().str[:-1]
    bases_with_lr = set(wb_all_lr['base_name'].unique())

    # Remove WB base machines that have L/R heads (they'll be represented by L/R rows)
    wb_base_to_remove = wb_mask & df['code_machine'].isin(bases_with_lr)
    df = df[~wb_base_to_remove]

    # Add L/R heads whose base machine is key=1 (even if L/R flag_key=0)
    wb_key_bases = df[wb_mask]['code_machine'].tolist()  # remaining WB key machines
    # Also get key bases that were just removed (they had L/R children)
    all_wb_key = set(query_df("""
        SELECT code_machine FROM dbo.machine
        WHERE id_operation = 'WB' AND flag_key = 1
    """)['code_machine'].str.strip().tolist())
    key_bases_with_lr = bases_with_lr & all_wb_key

    # Get L/R heads for key base machines
    lr_to_add = wb_all_lr[wb_all_lr['base_name'].isin(key_bases_with_lr)].copy()
    if not lr_to_add.empty:
        lr_to_add = lr_to_add.drop(columns=['base_name'])
        # Ensure same columns and types
        for col in ['flag_key', 'flag_automotive', 'flag_gold', 'flag_pm', 'flag_downtime']:
            if col in lr_to_add.columns:
                lr_to_add[col] = pd.to_numeric(lr_to_add[col], errors='coerce').fillna(0).astype(int)
        for col in ['model', 'mfg', 'code_machine', 'des_machine', 'short_name', 'id_operation']:
            if col in lr_to_add.columns:
                lr_to_add[col] = lr_to_add[col].astype(str).str.strip().replace('nan', '')
        # Mark as key (inherited from base)
        lr_to_add['flag_key'] = 1
        # Only add columns that exist in df
        common_cols = [c for c in df.columns if c in lr_to_add.columns]
        df = pd.concat([df, lr_to_add[common_cols]], ignore_index=True)

    return df


def _empty():
    fig = go.Figure()
    fig.update_layout(template='plotly_white', paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Calibri, Segoe UI, sans-serif'))
    return fig


# ── Populate filter dropdowns ─────────────────────────────────────────────────
@callback(
    Output('inv-filter-area',  'options'),
    Output('inv-filter-model', 'options'),
    Output('inv-filter-mfg',   'options'),
    Input('inv-flag-toggles',  'value'),
)
def load_filters(flags):
    from config import MACHINE_AREAS
    try:
        df = _load_machines()

        # Apply flag filters to narrow dropdown options
        if flags:
            if 'KEY'  in flags: df = df[df['flag_key'] == 1]
            if 'AUTO' in flags: df = df[df['flag_automotive'] == 1]
            if 'GOLD' in flags: df = df[df['flag_gold'] == 1]

        # Areas sorted by process order, pick first meaningful short_name per area
        order = {a: i for i, a in enumerate(MACHINE_AREAS)}
        areas = sorted(df['id_operation'].dropna().unique(),
                       key=lambda a: order.get(a, 999))
        # Map area → friendly name (use most common non-empty short_name)
        area_names = {}
        for a in areas:
            names = df[df['id_operation'] == a]['short_name'].dropna()
            names = names[names != '']
            area_names[a] = names.mode().iloc[0] if not names.empty else a
        area_opts = [{'label': f"{a} ({area_names.get(a, a)})", 'value': a}
                     for a in areas]

        models = sorted(df['model'].dropna().unique())
        model_opts = [{'label': m, 'value': m} for m in models if m]

        mfgs = sorted(df['mfg'].dropna().unique())
        mfg_opts = [{'label': m, 'value': m} for m in mfgs if m]

        return area_opts, model_opts, mfg_opts
    except Exception:
        return [], [], []


# ── Main callback ─────────────────────────────────────────────────────────────
@callback(
    Output('inv-kpi-row',         'children'),
    Output('inv-chart-area',      'figure'),
    Output('inv-chart-model',     'figure'),
    Output('inv-chart-mfg',       'figure'),
    Output('inv-treemap',         'figure'),
    Output('inv-chart-age',       'figure'),
    Output('inv-table-header',    'children'),
    Output('inv-machine-table',   'children'),
    Input('inv-filter-area',   'value'),
    Input('inv-filter-model',  'value'),
    Input('inv-filter-mfg',    'value'),
    Input('inv-flag-toggles',  'value'),
    Input('inv-search',        'value'),
)
def update_inventory(areas, models, mfgs, flags, search):
    ef = _empty()
    try:
        df = _load_machines()
    except Exception as e:
        err = html.Div(f"Error: {e}", style={'color': RED, 'padding': '16px'})
        return [], ef, ef, ef, ef, ef, "", err

    # ── Apply filters ─────────────────────────────────────────────────────────
    if areas:
        df = df[df['id_operation'].isin(areas)]
    if models:
        df = df[df['model'].isin(models)]
    if mfgs:
        df = df[df['mfg'].isin(mfgs)]
    if flags:
        if 'KEY'  in flags: df = df[df['flag_key'] == 1]
        if 'AUTO' in flags: df = df[df['flag_automotive'] == 1]
        if 'GOLD' in flags: df = df[df['flag_gold'] == 1]
    if search:
        s = search.lower()
        df = df[df['code_machine'].str.lower().str.contains(s, na=False) |
                df['des_machine'].fillna('').str.lower().str.contains(s, na=False)]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    kpis = [
        dbc.Col(make_kpi_card(len(df), "Total Machines", PRIMARY_BLUE, icon="🏭"),
                lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(int((df['flag_key'] == 1).sum()), "KEY Machines",
                              RED, icon="★"), lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(df['id_operation'].nunique(), "Areas",
                              GREEN, icon="🏗"), lg=3, md=6, sm=6),
        dbc.Col(make_kpi_card(df['model'].nunique(), "Models",
                              LIGHT_BLUE, icon="⚙"), lg=3, md=6, sm=6),
    ]

    # ── Chart: Machines by Area ───────────────────────────────────────────────
    area_fig = _empty()
    if not df.empty:
        area_counts = df.groupby('id_operation').size().reset_index(name='count')
        area_counts = area_counts.sort_values('count', ascending=True)
        area_fig.add_trace(go.Bar(
            y=area_counts['id_operation'],
            x=area_counts['count'],
            orientation='h', marker_color=PRIMARY_BLUE,
            text=area_counts['count'], textposition='outside',
            textfont=dict(size=11),
            hovertemplate='<b>%{y}</b>: %{x} machines<extra></extra>',
        ))
    area_fig.update_layout(
        template='plotly_white',
        height=max(250, len(df['id_operation'].unique()) * 32 + 60),
        margin=dict(t=10, b=30, l=10, r=50),
        xaxis=dict(title=None, showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
        yaxis=dict(title=None, automargin=True),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Chart: Top 15 Models ──────────────────────────────────────────────────
    model_fig = _empty()
    if not df.empty:
        model_counts = df['model'].value_counts().head(15).sort_values(ascending=True)
        model_fig.add_trace(go.Bar(
            y=model_counts.index.astype(str),
            x=model_counts.values,
            orientation='h', marker_color=LIGHT_BLUE,
            text=model_counts.values, textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b>: %{x}<extra></extra>',
        ))
    model_fig.update_layout(
        template='plotly_white', height=max(250, min(15, df['model'].nunique()) * 24 + 60),
        margin=dict(t=10, b=30, l=10, r=40),
        xaxis=dict(title=None, showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
        yaxis=dict(title=None, automargin=True, tickfont=dict(size=10)),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Chart: By Manufacturer ────────────────────────────────────────────────
    mfg_fig = _empty()
    if not df.empty:
        mfg_counts = df['mfg'].value_counts().sort_values(ascending=True)
        mfg_fig.add_trace(go.Bar(
            y=mfg_counts.index.astype(str),
            x=mfg_counts.values,
            orientation='h', marker_color=GREEN,
            text=mfg_counts.values, textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b>: %{x}<extra></extra>',
        ))
    mfg_fig.update_layout(
        template='plotly_white', height=max(200, mfg_counts.shape[0] * 28 + 60) if not df.empty else 200,
        margin=dict(t=10, b=30, l=10, r=40),
        xaxis=dict(title=None, showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
        yaxis=dict(title=None, automargin=True, tickfont=dict(size=10)),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Treemap: Area → Model → Machine (color=utilization, size=downtime) ───
    import plotly.express as px
    treemap_fig = _empty()
    if not df.empty and not areas:
        # No area selected — show placeholder
        treemap_fig.add_annotation(
            text="Select an Area to view Equipment Health Map",
            showarrow=False, font=dict(size=14, color=MED_GRAY),
            xref='paper', yref='paper', x=0.5, y=0.5,
        )
        treemap_fig.update_layout(
            height=200,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
        )

    if not df.empty and areas:
        # Only load heavy downtime query when area is selected
        dt_df = pd.DataFrame(columns=['code_machine', 'down_events', 'down_hrs', 'avg_mttr_min'])
        # Phase 3: try API first
        try:
            from api_client import USE_API, fetch_inventory_downtime
            if USE_API:
                dt_df = fetch_inventory_downtime()
        except Exception:
            dt_df = pd.DataFrame(columns=['code_machine', 'down_events', 'down_hrs', 'avg_mttr_min'])
        if dt_df.empty:
            try:
                from db import query_df as qdf2
                from utils.queries import inventory_machine_downtime
                dt_df = qdf2(inventory_machine_downtime())
            except Exception:
                pass

        tm_df = df[['code_machine', 'id_operation', 'model', 'mfg',
                     'flag_key']].copy()
        tm_df = tm_df.fillna('')
        tm_df['model_label'] = tm_df['model'].where(tm_df['model'] != '', 'Unknown')

        # Merge downtime data
        tm_df = tm_df.merge(dt_df, on='code_machine', how='left')
        tm_df['down_hrs']      = tm_df['down_hrs'].fillna(0)
        tm_df['down_events']   = tm_df['down_events'].fillna(0).astype(int)
        tm_df['avg_mttr_min']  = tm_df['avg_mttr_min'].fillna(0).astype(int)

        # Size = downtime hours (min 0.1 so zero-downtime machines still show)
        tm_df['size'] = tm_df['down_hrs'].clip(lower=0.1)

        # Color = health category (thresholds for 7-day window)
        tm_df['health'] = tm_df['down_hrs'].apply(
            lambda h: 'Critical' if h > 12
            else 'Warning' if h > 8
            else 'Monitor' if h > 3
            else 'Healthy')

        health_colors = {
            'Healthy':   GREEN,
            'Monitor':   '#E0C800',
            'Warning':   ORANGE,
            'Critical':  RED,
        }

        treemap_fig = px.treemap(
            tm_df,
            path=['id_operation', 'model_label', 'code_machine'],
            values='size',
            color='health',
            color_discrete_map=health_colors,
        )
        treemap_fig.update_traces(
            textinfo='label+value',
            texttemplate='%{label}<br>%{value:.1f}h',
            hovertemplate='<b>%{label}</b><br>Downtime: %{value:.1f} hrs<extra></extra>',
        )
        treemap_fig.update_layout(
            height=500,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Calibri, Segoe UI, sans-serif'),
            legend=dict(orientation='h', y=-0.05, font=dict(size=11)),
        )

    # ── Machine Age Distribution ─────────────────────────────────────────────
    from datetime import date as _date
    age_fig = _empty()
    if not df.empty:
        age_df = df[['code_machine', 'id_operation', 'date_install']].copy()
        age_df['date_install'] = pd.to_datetime(age_df['date_install'], errors='coerce')
        age_df = age_df.dropna(subset=['date_install'])
        if not age_df.empty:
            age_df['age_years'] = (pd.Timestamp.now() - age_df['date_install']).dt.days / 365.25

            # Lifecycle buckets
            age_df['lifecycle'] = age_df['age_years'].apply(
                lambda y: 'New (<2y)' if y < 2
                else 'Prime (2-5y)' if y < 5
                else 'Mature (5-10y)' if y < 10
                else 'Aging (>10y)')

            lifecycle_order = ['New (<2y)', 'Prime (2-5y)', 'Mature (5-10y)', 'Aging (>10y)']
            lifecycle_colors = {
                'New (<2y)':      LIGHT_BLUE,
                'Prime (2-5y)':   GREEN,
                'Mature (5-10y)': ORANGE,
                'Aging (>10y)':   RED,
            }

            # Grouped by area + lifecycle
            pivot = age_df.groupby(['id_operation', 'lifecycle']).size().reset_index(name='count')

            for lc in lifecycle_order:
                grp = pivot[pivot['lifecycle'] == lc]
                if not grp.empty:
                    age_fig.add_trace(go.Bar(
                        x=grp['id_operation'], y=grp['count'],
                        name=lc, marker_color=lifecycle_colors[lc],
                        hovertemplate='<b>%{x}</b><br>' + lc + ': %{y} machines<extra></extra>',
                    ))

            # Average age annotation per area
            avg_age = age_df.groupby('id_operation')['age_years'].mean()
            for area, avg in avg_age.items():
                age_fig.add_annotation(
                    x=area, yref='paper', y=1.05,
                    text=f"avg {avg:.1f}y", showarrow=False,
                    font=dict(size=9, color=MED_GRAY),
                )

    age_fig.update_layout(
        barmode='stack', template='plotly_white', height=320,
        margin=dict(t=30, b=50, l=40, r=10),
        xaxis=dict(showgrid=False),
        yaxis=dict(title='Machines', showgrid=True, gridcolor='rgba(128,128,128,0.15)'),
        legend=dict(orientation='h', y=-0.18, font=dict(size=11)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Calibri, Segoe UI, sans-serif'),
    )

    # ── Machine table ─────────────────────────────────────────────────────────
    if df.empty:
        return kpis, area_fig, model_fig, mfg_fig, _empty(), age_fig, "", \
               html.Div("No machines match filters.", style={'color': MED_GRAY, 'padding': '16px'})

    display = df[['code_machine', 'des_machine', 'id_operation', 'short_name',
                   'model', 'mfg', 'sn', 'date_install',
                   'flag_key', 'flag_automotive', 'flag_gold']].copy()
    display = display.fillna('')
    display['date_install'] = pd.to_datetime(display['date_install'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    display['flag_key']        = display['flag_key'].map({1: '★', 0: '', '': ''}).fillna('')
    display['flag_automotive'] = display['flag_automotive'].map({1: '✓', 0: '', '': ''}).fillna('')
    display['flag_gold']       = display['flag_gold'].map({1: '✓', 0: '', '': ''}).fillna('')

    col_map = [
        {'name': 'Machine',     'id': 'code_machine'},
        {'name': 'Description', 'id': 'des_machine'},
        {'name': 'Area',        'id': 'id_operation'},
        {'name': 'Area Name',   'id': 'short_name'},
        {'name': 'Model',       'id': 'model'},
        {'name': 'Mfg',         'id': 'mfg'},
        {'name': 'S/N',         'id': 'sn'},
        {'name': 'Installed',   'id': 'date_install'},
        {'name': 'KEY',         'id': 'flag_key'},
        {'name': 'Auto',        'id': 'flag_automotive'},
        {'name': 'Gold',        'id': 'flag_gold'},
    ]

    table_header = html.Div([
        html.Div([
            html.Span("All Machines", style={
                'fontSize': '14px', 'fontWeight': '600', 'color': 'var(--text)'}),
            html.Span(f"  {len(display)} machines", style={
                'fontSize': '10px', 'fontWeight': '600', 'color': MED_GRAY,
                'background': 'var(--badge-bg)', 'padding': '2px 9px',
                'borderRadius': '10px', 'marginLeft': '10px'}),
        ]),
        html.Button([
            html.Span("⬇", style={'marginRight': '5px'}), "Export CSV",
        ], id='btn-inv-export-csv', style={
            'background': PRIMARY_BLUE, 'color': '#fff', 'border': 'none',
            'borderRadius': '6px', 'padding': '5px 14px', 'fontSize': '12px',
            'fontWeight': '600', 'cursor': 'pointer',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'boxShadow': '0 2px 4px rgba(14,54,137,0.25)',
        }),
    ], style={'display': 'flex', 'justifyContent': 'space-between',
              'alignItems': 'center', 'marginBottom': '12px',
              'paddingBottom': '10px', 'borderBottom': '1px solid var(--divider)'})

    machine_table = dash_table.DataTable(
        # No static ID — created dynamically each callback
        columns=col_map,
        data=display.to_dict('records'),
        sort_action='native', sort_mode='multi',
        filter_action='native',
        page_action='native', page_size=20,
        style_header={
            'backgroundColor': PRIMARY_BLUE, 'color': '#fff',
            'fontWeight': '600', 'fontSize': '12px', 'padding': '10px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
        },
        style_cell={
            'fontSize': '13px', 'padding': '8px 14px',
            'fontFamily': 'Inter, Calibri, Segoe UI, sans-serif',
            'textAlign': 'left', 'border': 'none',
            'borderBottom': '1px solid #EEF0F4',
        },
        style_data={'color': '#1A1F2E'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
            {'if': {'column_id': 'flag_key', 'filter_query': '{flag_key} = "★"'},
             'color': RED, 'fontWeight': '700', 'textAlign': 'center'},
            {'if': {'column_id': 'flag_automotive'}, 'textAlign': 'center', 'color': LIGHT_BLUE},
            {'if': {'column_id': 'flag_gold'}, 'textAlign': 'center', 'color': '#D4A017'},
        ],
        style_table={'overflowX': 'auto', 'borderRadius': '6px'},
        style_as_list_view=True,
    )

    return kpis, area_fig, model_fig, mfg_fig, treemap_fig, age_fig, table_header, machine_table


# ── Export CSV ────────────────────────────────────────────────────────────────
@callback(
    Output('inv-download-csv', 'data'),
    Input('btn-inv-export-csv', 'n_clicks'),
    State('inv-filter-area',  'value'),
    State('inv-filter-model', 'value'),
    State('inv-filter-mfg',   'value'),
    State('inv-flag-toggles', 'value'),
    State('inv-search',       'value'),
    prevent_initial_call=True,
)
def export_inventory_csv(n_clicks, areas, models, mfgs, flags, search):
    if not n_clicks:
        return None
    df = _load_machines()
    if areas:  df = df[df['id_operation'].isin(areas)]
    if models: df = df[df['model'].isin(models)]
    if mfgs:   df = df[df['mfg'].isin(mfgs)]
    if flags:
        if 'KEY'  in flags: df = df[df['flag_key'] == 1]
        if 'AUTO' in flags: df = df[df['flag_automotive'] == 1]
        if 'GOLD' in flags: df = df[df['flag_gold'] == 1]
    if search:
        s = search.lower()
        df = df[df['code_machine'].str.lower().str.contains(s, na=False) |
                df['des_machine'].str.lower().str.contains(s, na=False)]

    export = df[['code_machine', 'des_machine', 'id_operation', 'model', 'mfg',
                  'sn', 'date_install', 'flag_key', 'flag_automotive', 'flag_gold']].copy()
    export.columns = ['Machine', 'Description', 'Area', 'Model', 'Manufacturer',
                       'Serial No', 'Install Date', 'KEY', 'Automotive', 'Gold']
    return dcc.send_data_frame(export.to_csv, 'machine_inventory.csv', index=False)
