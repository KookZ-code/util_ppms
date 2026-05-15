"""Store Inventory Usage Monitor — monthly Assembly store-item issue costs.

Access: supervisor + admin only (enforced via PAGE_ACCESS in auth.py).
Data:   dbo.store_item_issues (MTHAI_ppm_db1), loaded by scripts/import_store_items.py.
"""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd

from components.header import make_page_header, make_chart_title
from components.kpi_card import make_kpi_card
from utils.colors import PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, MED_GRAY

dash.register_page(__name__, path='/store-items', name='Store Items')

# ── Category colours (mirrors standalone HTML dashboard) ─────────────────────
CAT_COLORS = {
    'Emergency':   RED,
    'JIT':         ORANGE,
    'Consumable':  LIGHT_BLUE,
    'Consignment': GREEN,
}
CAT_ORDER = ['Emergency', 'JIT', 'Consumable', 'Consignment']

GRAPH_CFG = {'displayModeBar': False, 'responsive': True}


# ── Data loader ───────────────────────────────────────────────────────────────
def _load_store_items() -> pd.DataFrame:
    from db import query_df
    df = query_df("""
        SELECT month_key, month_label, source, item_no, description,
               process, machine_model, category, quantity, unit_cost, total_cost
        FROM dbo.store_item_issues
        ORDER BY month_key
    """)
    df['total_cost']    = pd.to_numeric(df['total_cost'],  errors='coerce').fillna(0)
    df['quantity']      = pd.to_numeric(df['quantity'],    errors='coerce').fillna(0).astype(int)
    df['machine_model'] = df['machine_model'].fillna('').astype(str)
    return df


def _month_list(df: pd.DataFrame) -> list[str]:
    return df.sort_values('month_key')['month_label'].drop_duplicates().tolist()


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    make_page_header("Store Inventory Usage Monitor",
                     subtitle="ASSY Division · MTHAI · monthly issue costs"),

    # Filter bar
    html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Period", className='filter-label'),
                html.Div([
                    dcc.Dropdown(id='si-from-month', options=[], clearable=False,
                                 style={'fontSize': '13px', 'minWidth': '100px'}),
                    html.Span('→', style={'padding': '0 8px', 'color': 'var(--muted)',
                                          'lineHeight': '38px'}),
                    dcc.Dropdown(id='si-to-month', options=[], clearable=False,
                                 style={'fontSize': '13px', 'minWidth': '100px'}),
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ], lg=3, md=6, sm=12),

            dbc.Col([
                html.Label("Process", className='filter-label'),
                dcc.Dropdown(id='si-filter-process', options=[], value=None,
                             multi=True, placeholder='All Processes',
                             style={'fontSize': '13px'}),
            ], lg=3, md=6, sm=12),

            dbc.Col([
                html.Label("Category", className='filter-label'),
                dcc.Dropdown(id='si-filter-category', options=[], value=None,
                             multi=True, placeholder='All Categories',
                             style={'fontSize': '13px'}),
            ], lg=2, md=4, sm=12),

            dbc.Col([
                html.Label("Search", className='filter-label'),
                dcc.Input(id='si-search', type='text',
                          placeholder='Item # or description…',
                          debounce=True,
                          style={'fontSize': '13px', 'width': '100%',
                                 'padding': '6px 10px', 'borderRadius': '6px',
                                 'border': '1px solid var(--border)',
                                 'background': 'var(--input-bg)',
                                 'color': 'var(--text)'}),
            ], lg=2, md=4, sm=12),

            dbc.Col([
                html.Label(" ", className='filter-label'),
                dbc.Button('↺ Reset', id='si-reset', color='secondary',
                           outline=True, size='sm',
                           style={'width': '100%', 'fontSize': '12px'}),
            ], lg=1, md=2, sm=6),

            dbc.Col([
                html.Label(" ", className='filter-label'),
                dbc.Button('⬇ Export CSV', id='btn-si-export', color='primary',
                           outline=True, size='sm',
                           style={'width': '100%', 'fontSize': '12px'}),
            ], lg=1, md=2, sm=6),
        ], className='g-2 align-items-end'),
    ], className='filter-bar'),

    # KPI row
    dbc.Row(id='si-kpi-row', className='g-3 mb-3'),

    # Monthly trend
    html.Div([
        make_chart_title("Monthly Cost Trend", "Click a bar to filter that month"),
        dcc.Graph(id='si-trend-chart', config=GRAPH_CFG,
                  style={'height': '280px'}),
    ], className='chart-card'),

    # Process + Machine side by side
    dbc.Row([
        dbc.Col([
            html.Div([
                make_chart_title("Cost by Process", "Top 10 · stacked by Category"),
                dcc.Graph(id='si-process-chart', config=GRAPH_CFG,
                          style={'height': '370px'}),
            ], className='chart-card'),
        ], lg=6, md=12),

        dbc.Col([
            html.Div([
                make_chart_title("Cost by Machine Model", "Top 10"),
                dcc.Graph(id='si-machine-chart', config=GRAPH_CFG,
                          style={'height': '370px'}),
            ], className='chart-card'),
        ], lg=6, md=12),
    ], className='g-3'),

    # Detail table
    html.Div([
        html.Div([
            html.Div(id='si-table-meta', style={'fontSize': '12px',
                                                 'color': 'var(--muted)',
                                                 'marginBottom': '10px'}),
            dcc.Download(id='si-download'),
            html.Div(id='si-table-wrap'),
        ]),
    ], className='chart-card'),

    # Hidden stores
    dcc.Store(id='si-data-cache', storage_type='memory'),
    dcc.Store(id='si-click-month', data=None, storage_type='memory'),

], className='page-container')


# ── Callback 1: populate filter dropdowns on load ────────────────────────────
@callback(
    Output('si-from-month',      'options'),
    Output('si-from-month',      'value'),
    Output('si-to-month',        'options'),
    Output('si-to-month',        'value'),
    Output('si-filter-process',  'options'),
    Output('si-filter-category', 'options'),
    Input('si-reset',            'n_clicks'),
    Input('si-click-month',      'data'),
)
def load_filters(_, click_month):
    df      = _load_store_items()
    months  = _month_list(df)
    m_opts  = [{'label': m, 'value': m} for m in months]
    to_val  = months[-1] if months else None
    from_val = months[max(0, len(months) - 12)] if months else None

    # If a bar was clicked, snap period to that single month
    if click_month and click_month in months:
        from_val = click_month
        to_val   = click_month

    proc_opts = [{'label': p, 'value': p}
                 for p in sorted(df['process'].dropna().unique())]
    cat_opts  = [{'label': c, 'value': c}
                 for c in CAT_ORDER if c in df['category'].unique()]

    return m_opts, from_val, m_opts, to_val, proc_opts, cat_opts


# ── Callback 2: capture trend bar click → store month ────────────────────────
@callback(
    Output('si-click-month', 'data'),
    Input('si-trend-chart',  'clickData'),
    State('si-from-month',   'value'),
    State('si-to-month',     'value'),
    prevent_initial_call=True,
)
def on_trend_click(click_data, cur_from, cur_to):
    if not click_data:
        return no_update
    clicked = click_data['points'][0]['x']
    # Toggle: if already showing only this month, return None to reset
    if cur_from == clicked and cur_to == clicked:
        return None
    return clicked


# ── Callback 3: main update — KPIs, charts, table ────────────────────────────
@callback(
    Output('si-kpi-row',       'children'),
    Output('si-trend-chart',   'figure'),
    Output('si-process-chart', 'figure'),
    Output('si-machine-chart', 'figure'),
    Output('si-table-wrap',    'children'),
    Output('si-table-meta',    'children'),
    Output('si-data-cache',    'data'),
    Input('si-from-month',      'value'),
    Input('si-to-month',        'value'),
    Input('si-filter-process',  'value'),
    Input('si-filter-category', 'value'),
    Input('si-search',          'value'),
)
def update_store_items(from_m, to_m, procs, cats, search):
    df = _load_store_items()

    # Month range filter
    months = _month_list(df)
    if from_m and to_m and from_m in months and to_m in months:
        i0 = months.index(from_m)
        i1 = months.index(to_m)
        keep = set(months[min(i0, i1): max(i0, i1) + 1])
        df = df[df['month_label'].isin(keep)]

    if procs:  df = df[df['process'].isin(procs)]
    if cats:   df = df[df['category'].isin(cats)]
    if search:
        s = search.strip().lower()
        df = df[
            df['item_no'].str.lower().str.contains(s, na=False) |
            df['description'].fillna('').str.lower().str.contains(s, na=False)
        ]

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total      = float(df['total_cost'].sum())
    active_m   = df.sort_values('month_key')['month_label'].drop_duplicates().tolist()
    latest     = active_m[-1] if active_m else '—'
    prev       = active_m[-2] if len(active_m) >= 2 else None
    latest_tot = float(df[df['month_label'] == latest]['total_cost'].sum())
    prev_tot   = float(df[df['month_label'] == prev]['total_cost'].sum()) if prev else 0
    mom_pct    = (latest_tot - prev_tot) / prev_tot * 100 if prev_tot > 0 else None
    n_items    = df['item_no'].nunique()

    mom_trend = {
        'delta':     round(mom_pct, 1),
        'direction': 'up' if (mom_pct or 0) > 0 else 'down',
        'improved':  (mom_pct or 0) < 0,
    } if mom_pct is not None else None

    def _fmt(v):
        if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
        if v >= 1_000:     return f"${v/1_000:.1f}K"
        return f"${v:,.0f}"

    kpis = dbc.Row([
        dbc.Col(make_kpi_card(_fmt(total), "Total Cost", PRIMARY_BLUE,
                              subtitle=f"{len(active_m)} month(s) selected",
                              icon='💰'), lg=3, md=6),
        dbc.Col(make_kpi_card(_fmt(latest_tot), "Latest Month", LIGHT_BLUE,
                              subtitle=latest, icon='📅'), lg=3, md=6),
        dbc.Col(make_kpi_card(
            f"{mom_pct:+.1f}%" if mom_pct is not None else "—",
            "MoM Change",
            RED if (mom_pct or 0) > 0 else GREEN,
            subtitle=f"{prev or ''} → {latest}" if prev else "Need 2+ months",
            icon='📈',
            trend=mom_trend,
            trend_label='vs prev month',
        ), lg=3, md=6),
        dbc.Col(make_kpi_card(f"{n_items:,}", "Unique Items", GREEN,
                              subtitle="distinct part numbers", icon='📦'), lg=3, md=6),
    ], className='g-3')

    # ── Trend chart ───────────────────────────────────────────────────────────
    by_m = (df.groupby(['month_key', 'month_label'], as_index=False)['total_cost']
              .sum().sort_values('month_key'))
    trend_fig = go.Figure(go.Bar(
        x=by_m['month_label'],
        y=by_m['total_cost'],
        marker_color=PRIMARY_BLUE,
        text=[f"${v/1000:.0f}K" for v in by_m['total_cost']],
        textposition='outside',
        cliponaxis=False,
        hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>',
    ))
    trend_fig.update_layout(
        template='plotly_white', height=260,
        margin=dict(t=40, b=10, l=50, r=10),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(tickprefix='$', tickformat=',.0s', gridcolor='#EEF1F5'),
        xaxis=dict(gridcolor='rgba(0,0,0,0)'),
        uniformtext_minsize=8, uniformtext_mode='hide',
    )

    # ── Process × Category stacked bar ───────────────────────────────────────
    top10_proc = (df.groupby('process')['total_cost'].sum()
                    .nlargest(10).index.tolist())
    pc = (df[df['process'].isin(top10_proc)]
          .groupby(['process', 'category'], as_index=False)['total_cost'].sum())

    proc_fig = go.Figure()
    for cat in CAT_ORDER:
        sub = pc[pc['category'] == cat]
        if sub.empty:
            continue
        proc_fig.add_trace(go.Bar(
            y=sub['process'], x=sub['total_cost'],
            name=cat, orientation='h',
            marker_color=CAT_COLORS[cat],
            hovertemplate=f'<b>%{{y}}</b> · {cat}<br>$%{{x:,.0f}}<extra></extra>',
        ))
    proc_totals = (df[df['process'].isin(top10_proc)]
                   .groupby('process')['total_cost'].sum())
    x_max = proc_totals.max() * 1.22   # 22% headroom for labels

    annotations = [
        dict(
            x=proc_totals.get(p, 0),
            y=p,
            text=f"  ${proc_totals.get(p,0)/1000:.0f}K",
            xanchor='left', yanchor='middle',
            showarrow=False,
            font=dict(size=11, color='#4A4A4A', family='inherit'),
            xref='x', yref='y',
        )
        for p in top10_proc
    ]

    proc_fig.update_layout(
        barmode='stack', template='plotly_white', height=340,
        margin=dict(t=10, b=60, l=10, r=20),
        legend=dict(orientation='h', y=-0.22, font=dict(size=11),
                    xanchor='center', x=0.5),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickprefix='$', tickformat=',.0s', gridcolor='#EEF1F5',
                   range=[0, x_max]),
        yaxis=dict(categoryorder='total ascending', gridcolor='rgba(0,0,0,0)',
                   tickfont=dict(size=11)),
        annotations=annotations,
    )

    # ── Machine model bar ─────────────────────────────────────────────────────
    by_mach = (df[df['machine_model'] != '']
               .groupby('machine_model', as_index=False)['total_cost'].sum()
               .nlargest(10, 'total_cost')
               .sort_values('total_cost'))
    mach_fig = go.Figure(go.Bar(
        y=by_mach['machine_model'],
        x=by_mach['total_cost'],
        orientation='h',
        marker_color=ORANGE,
        text=[f"${v/1000:.0f}K" for v in by_mach['total_cost']],
        textposition='outside',
        cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>$%{x:,.0f}<extra></extra>',
    ))
    mach_fig.update_layout(
        template='plotly_white', height=340,
        margin=dict(t=10, b=10, l=10, r=80),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickprefix='$', tickformat=',.0s', gridcolor='#EEF1F5'),
        yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(size=11)),
        uniformtext_minsize=8, uniformtext_mode='hide',
    )

    # ── Detail table ──────────────────────────────────────────────────────────
    tbl_df = df[['item_no', 'description', 'process', 'machine_model',
                 'category', 'month_label', 'quantity', 'total_cost']].copy()
    tbl_df = tbl_df.sort_values('total_cost', ascending=False)
    tbl_df['total_cost'] = tbl_df['total_cost'].round(2)

    table = dash_table.DataTable(
        data=tbl_df.to_dict('records'),
        columns=[
            {'name': 'Item #',       'id': 'item_no'},
            {'name': 'Description',  'id': 'description'},
            {'name': 'Process',      'id': 'process'},
            {'name': 'Machine',      'id': 'machine_model'},
            {'name': 'Category',     'id': 'category'},
            {'name': 'Month',        'id': 'month_label'},
            {'name': 'Qty',          'id': 'quantity',   'type': 'numeric'},
            {'name': 'Total Cost',   'id': 'total_cost', 'type': 'numeric',
             'format': {'specifier': '$,.2f'}},
        ],
        page_size=50,
        sort_action='native',
        filter_action='native',
        style_table={'overflowX': 'auto'},
        style_header={
            'backgroundColor': 'var(--bg, #F7F7F7)',
            'fontWeight': '700',
            'fontSize': '11px',
            'textTransform': 'uppercase',
            'letterSpacing': '0.05em',
            'color': 'var(--muted, #8A8A8A)',
            'borderBottom': '2px solid var(--border, #e0e0e0)',
        },
        style_cell={
            'fontSize': '13px',
            'padding': '9px 14px',
            'fontFamily': 'inherit',
            'border': 'none',
            'borderBottom': '1px solid var(--border, #f0f0f0)',
            'whiteSpace': 'normal',
            'textAlign': 'left',
        },
        style_data_conditional=[
            {'if': {'row_index': 'odd'},
             'backgroundColor': 'rgba(0,0,0,0.015)'},
            {'if': {'column_id': 'total_cost'},
             'fontWeight': '700', 'color': PRIMARY_BLUE, 'textAlign': 'right'},
            {'if': {'column_id': 'quantity'},
             'textAlign': 'right'},
            {'if': {'column_id': 'item_no'},
             'fontFamily': 'monospace', 'fontSize': '12px',
             'color': MED_GRAY},
        ],
        id='si-table',
    )

    meta = f"{len(tbl_df):,} records  ·  sorted by Total Cost"
    cache = tbl_df.to_dict('records')
    return kpis, trend_fig, proc_fig, mach_fig, table, meta, cache


# ── Callback 4: Export CSV ────────────────────────────────────────────────────
@callback(
    Output('si-download',      'data'),
    Input('btn-si-export',     'n_clicks'),
    State('si-data-cache',     'data'),
    State('si-from-month',     'value'),
    State('si-to-month',       'value'),
    prevent_initial_call=True,
)
def export_csv(n, cached, from_m, to_m):
    if not n or not cached:
        return no_update
    out = pd.DataFrame(cached)
    out.columns = ['Item #', 'Description', 'Process', 'Machine',
                   'Category', 'Month', 'Qty', 'Total Cost']
    fname = (f"store_items_"
             f"{(from_m or '').replace(chr(39), '')}_"
             f"{(to_m   or '').replace(chr(39), '')}.csv")
    return dcc.send_data_frame(out.to_csv, fname, index=False)
