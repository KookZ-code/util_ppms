"""Page header and chart title components — Industrial Command theme."""
from dash import html
from datetime import datetime


def make_page_header(title, subtitle=None, show_timestamp=True):
    """Dark blue gradient header bar with title, subtitle, and last-updated badge."""
    right = html.Span(
        f"Last updated: {datetime.now():%H:%M:%S}",
        style={
            'background': 'rgba(255,255,255,0.15)',
            'border': '1px solid rgba(255,255,255,0.25)',
            'padding': '4px 12px',
            'borderRadius': '20px',
            'fontSize': '11px',
            'color': '#FFFFFF',
            'whiteSpace': 'nowrap',
        }
    ) if show_timestamp else None

    left = html.Div([
        html.Div(title, style={'fontWeight': '600', 'fontSize': '18px', 'letterSpacing': '0.2px'}),
        html.Div(subtitle, className='page-header-sub') if subtitle else None,
    ])

    children = [left, right] if right else [left]
    return html.Div([c for c in children if c is not None], className='page-header')


def make_chart_title(title, badge=None, badge_color=None):
    """Chart card title with optional badge pill on the right.

    Args:
        title:       Title text
        badge:       Optional short label shown as pill (e.g. 'Monthly', 'Live')
        badge_color: Optional hex color for badge text/border (defaults to gray)
    """
    from utils.colors import PRIMARY_BLUE
    color = badge_color or '#8A96A8'
    bg    = color + '18'  # ~10% opacity tint

    badge_el = html.Span(
        badge,
        style={
            'fontSize': '10px', 'fontWeight': '600',
            'color': color, 'background': bg,
            'padding': '2px 9px', 'borderRadius': '10px',
            'textTransform': 'uppercase', 'letterSpacing': '0.4px',
        }
    ) if badge else None

    children = [html.Span(title)]
    if badge_el:
        children.append(badge_el)

    return html.Div(
        children,
        className='chart-title',
        style={'display': 'flex', 'alignItems': 'center',
               'justifyContent': 'space-between'},
    )
