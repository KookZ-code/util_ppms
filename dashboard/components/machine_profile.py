"""Machine profile card — shows specs, flags, and age from dbo.machine."""
from dash import html
import dash_bootstrap_components as dbc
from datetime import date
from utils.colors import PRIMARY_BLUE, LIGHT_BLUE, ORANGE, RED, PURPLE, MED_GRAY


def _flag_badge(label, color, active):
    if not active:
        return None
    return html.Span(label, style={
        'display': 'inline-block',
        'background': color + '18',
        'color': color,
        'padding': '3px 10px',
        'borderRadius': '12px',
        'fontSize': '11px',
        'fontWeight': '600',
        'marginBottom': '6px',
    })


def _spec_row(label, value):
    if not value or str(value).strip() in ('', 'None', 'NaT'):
        value = '—'
    return html.Div([
        html.Span(label, className='spec-label'),
        html.Span(str(value), className='spec-value'),
    ], className='spec-row')


def _machine_age(install_date):
    if not install_date:
        return '—'
    try:
        if hasattr(install_date, 'date'):
            install_date = install_date.date()
        today = date.today()
        diff = today - install_date
        years = diff.days // 365
        months = (diff.days % 365) // 30
        if years > 0:
            return f"{years}y {months}m"
        return f"{months}m"
    except Exception:
        return '—'


def make_machine_profile(row):
    """Build a machine profile card from a dict of machine master data.

    Args:
        row: dict with keys from dbo.machine
             (code_machine, des_machine, mfg, model, sn, date_install, etc.)
    """
    name = row.get('des_machine') or '—'
    code = row.get('code_machine') or '—'

    # Specs
    specs = [
        _spec_row('Manufacturer', row.get('mfg')),
        _spec_row('Model',        row.get('model')),
        _spec_row('Serial No.',   row.get('sn')),
        _spec_row('ODS Name',     row.get('ods_name')),
        _spec_row('Installed',    str(row.get('date_install', ''))[:10]),
        _spec_row('Machine Age',  _machine_age(row.get('date_install'))),
        _spec_row('Remark',       row.get('remark')),
    ]

    # Flag badges
    # KEY machine badge — prominent
    key_badge = None
    if row.get('flag_key'):
        key_badge = html.Span('★ KEY MACHINE', style={
            'display': 'inline-block',
            'background': PRIMARY_BLUE,
            'color': '#FFFFFF',
            'padding': '4px 14px',
            'borderRadius': '14px',
            'fontSize': '12px',
            'fontWeight': '700',
            'letterSpacing': '0.5px',
            'marginBottom': '8px',
        })

    flags = [c for c in [
        key_badge,
        _flag_badge('AUTOMOTIVE',  LIGHT_BLUE, row.get('flag_automotive')),
        _flag_badge('GOLD WIRE',   '#D4A017',  row.get('flag_gold')),
        _flag_badge('PM TRACKED',  PURPLE,     row.get('flag_pm')),
        _flag_badge('DT TRACKED',  RED,        row.get('flag_downtime')),
    ] if c is not None]

    area_text = row.get('short_name') or row.get('id_operation') or '—'
    group_text = row.get('id_group') or '—'

    return html.Div([
        dbc.Row([
            # Left: name + specs
            dbc.Col([
                html.Div(name, className='machine-name'),
                html.Div(code, className='machine-code'),
                html.Div(specs, className='spec-grid',
                         style={'marginTop': '14px'}),
            ], lg=8, md=7, sm=12),
            # Right: flags + area
            dbc.Col([
                html.Div(flags, style={
                    'display': 'flex', 'flexDirection': 'column',
                    'alignItems': 'flex-start', 'gap': '4px',
                }),
                html.Hr(style={'margin': '10px 0', 'borderColor': 'var(--divider)'}),
                html.Div([
                    html.Span('Area: ', style={'fontSize': '11px', 'color': 'var(--text-light)'}),
                    html.Span(area_text, style={'fontSize': '13px', 'fontWeight': '600'}),
                ]),
                html.Div([
                    html.Span('Group: ', style={'fontSize': '11px', 'color': 'var(--text-light)'}),
                    html.Span(group_text, style={'fontSize': '13px'}),
                ], style={'marginTop': '4px'}),
            ], lg=4, md=5, sm=12,
               style={'borderLeft': '1px solid var(--divider)', 'paddingLeft': '20px'}),
        ]),
    ], className='chart-card machine-profile')
