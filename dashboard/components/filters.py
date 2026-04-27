"""Filter bar component — Industrial Command theme."""
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def make_filter_bar(areas=None, show_date=True, show_area=True,
                    show_machine=True, show_shift=False, show_job_type=False,
                    default_days=365):
    row1 = []  # main filters
    row2 = []  # button row (always aligned right)

    if show_date:
        row1.append(dbc.Col([
            html.Label("Date Range", className='filter-label'),
            dcc.DatePickerRange(
                id='filter-date-range',
                start_date=(datetime.now() - timedelta(days=default_days)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                display_format='YYYY-MM-DD',
                style={'width': '100%'},
            ),
        ], lg=4, md=6, sm=12))

    if show_area:
        row1.append(dbc.Col([
            html.Label("Machine Area", className='filter-label'),
            dcc.Dropdown(
                id='filter-area',
                options=[{'label': a, 'value': a} for a in (areas or [])],
                value=None, multi=True, placeholder='All Areas',
                style={'fontSize': '13px'},
            ),
        ], lg=2, md=3, sm=12))

    if show_shift:
        row1.append(dbc.Col([
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
        ], lg=2, md=3, sm=12))

    if show_job_type:
        row1.append(dbc.Col([
            html.Label("Job Type", className='filter-label'),
            dcc.Dropdown(
                id='filter-job-type',
                options=[
                    {'label': 'M/C DOWN',            'value': 'M/C DOWN'},
                    {'label': 'SETUP',               'value': 'SETUP'},
                    {'label': 'SETUP BY OPERATOR',   'value': 'SETUP BY OPERATOR'},
                    {'label': 'PM',                  'value': 'PM'},
                    {'label': 'CONVERT',             'value': 'CONVERT'},
                ],
                value=None, placeholder='All Types',
                style={'fontSize': '13px'},
            ),
        ], lg=2, md=3, sm=12))

    if show_machine:
        row1.append(dbc.Col([
            html.Label("Machine", className='filter-label'),
            dcc.Dropdown(
                id='filter-machine',
                options=[], value=None, multi=True,
                placeholder='All Machines',
                style={'fontSize': '13px'},
            ),
        ], lg=2, md=3, sm=12))

    # Apply button — aligned to end of row
    row1.append(dbc.Col([
        html.Label("\u00a0", className='filter-label'),
        dbc.Button("Apply Filter", id='btn-refresh', size='sm',
                   style={
                       'backgroundColor': '#0E3689', 'color': '#fff',
                       'border': 'none', 'fontWeight': '600', 'fontSize': '13px',
                       'borderRadius': '6px', 'padding': '7px 18px',
                       'boxShadow': '0 2px 4px rgba(14,54,137,0.3)',
                       'whiteSpace': 'nowrap',
                   }),
    ], lg=2, md=3, sm=12, className='d-flex flex-column align-items-end'))

    return html.Div(
        dbc.Row(row1, className='g-2 align-items-end'),
        className='filter-bar',
    )
