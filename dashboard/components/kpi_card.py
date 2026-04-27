"""KPI card component — Industrial Command theme.
Matches demo_layout.html exactly: icon + title row, big number, subtitle.
"""
from dash import html
from utils.colors import PRIMARY_BLUE


def make_kpi_card(value, label, accent_color=PRIMARY_BLUE,
                  subtitle=None, icon=None, unit=None, trend=None,
                  trend_label=None):
    """Professional KPI card with colored accent bar, icon, large value.

    Args:
        value:        Numeric or string value to display large (e.g. "83.2" or 42)
        label:        Card label shown as uppercase small caps beside icon
        accent_color: Top bar color + value text color
        subtitle:     Small descriptive text below value
        icon:         Emoji icon shown in colored bubble (e.g. '⚙', '🔧')
        unit:         Unit appended to value in smaller text (e.g. '%', 'hrs')
    """
    bg_light = accent_color + '18'  # ~10% opacity tint

    icon_el = html.Span(
        icon,
        style={
            'width': '34px', 'height': '34px',
            'borderRadius': '8px',
            'background': bg_light,
            'color': accent_color,
            'display': 'inline-flex',
            'alignItems': 'center',
            'justifyContent': 'center',
            'fontSize': '16px',
            'flexShrink': '0',
        }
    ) if icon else None

    header = html.Div(
        [c for c in [icon_el,
                     html.Span(label, className='kpi-title-text')] if c],
        className='kpi-header',
    )

    value_children = [str(value)]
    if unit:
        value_children.append(html.Span(unit, className='kpi-unit'))

    value_el = html.Div(value_children, className='kpi-value',
                        style={'color': accent_color})

    body_children = [header, value_el]
    if subtitle:
        body_children.append(html.Div(subtitle, className='kpi-sub'))

    if trend is not None:
        delta     = trend.get('delta', 0)
        direction = trend.get('direction', 'flat')
        improved  = trend.get('improved', None)
        arrow     = '▲' if direction == 'up' else ('▼' if direction == 'down' else '—')
        sign      = '+' if delta > 0 else ''
        # Color by improvement, not by direction
        if improved is None:
            color_cls = 'kpi-trend-flat'
        elif improved:
            color_cls = 'kpi-trend-up'    # green
        else:
            color_cls = 'kpi-trend-down'  # red
        body_children.append(
            html.Div(f"{arrow} {sign}{delta:.1f}%  {trend_label or 'vs prev period'}",
                     className=f'kpi-trend {color_cls}')
        )

    return html.Div([
        html.Div(style={'background': accent_color}, className='kpi-accent'),
        html.Div(body_children, className='kpi-body'),
    ], className='kpi-card')
