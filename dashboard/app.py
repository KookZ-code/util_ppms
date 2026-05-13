"""Machine Utilization & Downtime Dashboard.

Usage:
    python app.py              # Development mode (auto-reload)
    python app.py --prod       # Production mode (waitress)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import dash
from dash import Dash, html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from config import REFRESH_MINUTES, DASH_HOST, DASH_PORT

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap',
    ],
    suppress_callback_exceptions=True,
    title="EMH — Equipment Maintenance Hub",
)

# ── Auth setup ────────────────────────────────────────────────────────────────
from flask import redirect
from auth import setup_auth, ensure_users_table, current_user
app.server.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mch-dash-2026-secret-key')
setup_auth(app)
try:
    ensure_users_table()
except Exception as e:
    print(f"Warning: could not create users table: {e}")

# ── Navbar ────────────────────────────────────────────────────────────────────
# Navigation entries — ordered list of (label, href). Visibility is filtered
# per-role via PAGE_ACCESS inside build_navbar().
NAV_LINKS = [
    ('Overview',         '/'),
    ('Live Board',       '/live'),
    ('Utilization',      '/utilization'),
    ('Downtime & Setup', '/downtime'),
    ('Machine Detail',   '/machine-detail'),
    ('Tech Performance', '/timeline'),
    ('Inventory',        '/inventory'),
    ('Admin',            '/admin'),
]


def build_navbar(role: str, is_authenticated: bool = True):
    """Build a navbar showing only links the given role is allowed to visit.

    is_authenticated=False → shows a "Login" button instead of "Logout" so
    guest/anonymous users can switch to a named account.
    """
    from auth import PAGE_ACCESS
    allowed = PAGE_ACCESS.get(role, set())
    links = [
        dbc.NavLink(label, href=href, active='exact',
                    id=f'nav-{href.strip("/") or "home"}')
        for label, href in NAV_LINKS
        if href in allowed
    ]
    # Show Logout only for named (non-guest) authenticated users;
    # everyone else sees a Login link so they can elevate to a named role.
    auth_btn = (
        html.A("Logout", href='/auth/logout', id='navbar-logout', style={
            'color': '#FFD53A', 'fontSize': '12px', 'marginRight': '14px',
            'textDecoration': 'none', 'fontWeight': '600',
        })
        if is_authenticated
        else html.A("Login", href='/login', id='navbar-logout', style={
            'color': '#FFD53A', 'fontSize': '12px', 'marginRight': '14px',
            'textDecoration': 'none', 'fontWeight': '600',
        })
    )
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand([
                html.Span("EMH", style={'fontWeight': '700', 'letterSpacing': '0.5px'}),
                html.Span(" — Equipment Maintenance Hub", style={
                    'fontWeight': '400', 'opacity': '0.85',
                    'fontSize': '13px', 'marginLeft': '6px',
                }),
            ], href='/', style={'color': '#FFFFFF'}),
            dbc.Nav(links, navbar=True),
            html.Div([
                html.Span(id='navbar-user', style={
                    'color': 'rgba(255,255,255,0.7)', 'fontSize': '12px',
                    'marginRight': '10px',
                }),
                auth_btn,
                html.Button(
                    "🌙 Dark Mode",
                    id='theme-btn',
                    className='theme-toggle-btn',
                    n_clicks=0,
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginLeft': 'auto'}),
        ], fluid=True),
        color='#0E3689',
        dark=True,
        className='mb-0',
    )

# ── App layout ────────────────────────────────────────────────────────────────
def serve_layout():
    """Dynamic layout — unauthenticated users get guest/viewer access
    (no login wall). They see a 'Login' button to switch to a named account.
    """
    if not current_user.is_authenticated:
        # Anonymous visitor — show the full dashboard as guest (viewer role).
        # build_navbar('viewer', is_authenticated=False) shows Login not Logout.
        return html.Div([
            dcc.Store(id='theme-store', storage_type='local', data='light'),
            dcc.Store(id='global-area-filter', storage_type='session'),
            dcc.Interval(id='auto-refresh', interval=REFRESH_MINUTES * 60 * 1000,
                         n_intervals=0),
            dcc.Location(id='url', refresh=False),
            build_navbar('viewer', is_authenticated=False),
            html.Div(dash.page_container, style={'minHeight': 'calc(100vh - 52px)'}),
            html.Div(
                html.Span(f"Auto-refresh every {REFRESH_MINUTES} min  ·  Microchip Technology  ·  Proprietary and Confidential"),
                className='footer-bar',
            ),
            html.Script('document.getElementById("navbar-user").textContent = "Guest (viewer)";'),
        ])

    user_label = f"{current_user.display_name} ({current_user.role})"
    return html.Div([
        dcc.Store(id='theme-store', storage_type='local', data='light'),
        dcc.Store(id='global-area-filter', storage_type='session'),
        dcc.Interval(id='auto-refresh', interval=REFRESH_MINUTES * 60 * 1000,
                     n_intervals=0),
        dcc.Location(id='url', refresh=False),
        build_navbar(current_user.role, is_authenticated=True),
        html.Div(dash.page_container, style={'minHeight': 'calc(100vh - 52px)'}),
        html.Div(
            html.Span(f"Auto-refresh every {REFRESH_MINUTES} min  ·  Microchip Technology  ·  Proprietary and Confidential"),
            className='footer-bar',
        ),
        # Inject user info into navbar
        html.Script(f'document.getElementById("navbar-user").textContent = "{user_label}";'),
    ])


app.layout = serve_layout

# ── Dark mode toggle (server-side callback) ──────────────────────────────────
@callback(
    Output('theme-store', 'data'),
    Output('theme-btn', 'children'),
    Input('theme-btn', 'n_clicks'),
    State('theme-store', 'data'),
    prevent_initial_call=True,
)
def toggle_theme(n_clicks, current):
    if not n_clicks:
        return dash.no_update, dash.no_update
    nxt = 'light' if current == 'dark' else 'dark'
    label = '☀️ Light Mode' if nxt == 'dark' else '🌙 Dark Mode'
    return nxt, label

# ── Global callbacks ──────────────────────────────────────────────────────────
@callback(
    Output('filter-area', 'options'),
    Input('auto-refresh', 'n_intervals'),
)
def load_filter_areas(n):
    from db import query_df
    from utils.queries import distinct_areas
    from config import MACHINE_AREAS, ORA_ENABLED
    try:
        df = query_df(distinct_areas())
        db_areas = df['area'].tolist()
        # Add Oracle areas if enabled
        if ORA_ENABLED:
            for a in ('ISO', 'FS'):
                if a not in db_areas:
                    db_areas.append(a)
        # Sort by MACHINE_AREAS order, unknown areas appended at end
        order = {a: i for i, a in enumerate(MACHINE_AREAS)}
        sorted_areas = sorted(db_areas, key=lambda a: order.get(a, 999))
        return [{'label': a, 'value': a} for a in sorted_areas]
    except Exception:
        return []


server = app.server

# ── Page access control (no login wall — anonymous = viewer) ──────────────────
@server.before_request
def check_login():
    """No login wall: unauthenticated visitors are treated as viewer (guest).
    Named users (/login) can still authenticate for elevated roles.
    Admin-only pages are protected regardless.
    """
    from flask import request as req
    from auth import PAGE_ACCESS
    always_allowed = {'/login', '/auth/login', '/auth/logout',
                      '/_dash-component-suites/', '/_dash-layout',
                      '/_dash-dependencies', '/_dash-update-component',
                      '/_favicon.ico', '/assets/'}
    path = req.path
    if any(path.startswith(a) for a in always_allowed):
        return

    # Determine effective role: authenticated user's role, else 'viewer'
    role = getattr(current_user, 'role', 'viewer') if current_user.is_authenticated else 'viewer'

    # For authenticated users, use the existing can_access helper
    if current_user.is_authenticated and hasattr(current_user, 'can_access'):
        if not current_user.can_access(path):
            return redirect('/?denied=1')
        return

    # For anonymous visitors, apply viewer role page-access rules
    viewer_pages = PAGE_ACCESS.get('viewer', set())
    # Allow Dash internal endpoints and root
    if path.startswith('/_') or path == '/':
        return
    # Allow pages the viewer role can see
    if path in viewer_pages:
        return
    # Anything else (e.g. /admin, /timeline) redirect to root silently
    return redirect('/')


if __name__ == '__main__':
    # Start email scheduler (both dev and prod)
    try:
        from email_scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"Warning: email scheduler failed to start: {e}")

    if '--prod' in sys.argv:
        from waitress import serve
        print(f"Production server starting on http://{DASH_HOST}:{DASH_PORT}")
        serve(server, host=DASH_HOST, port=DASH_PORT)
    else:
        print(f"Development server starting on http://localhost:{DASH_PORT}")
        app.run(debug=True, dev_tools_ui=False, host=DASH_HOST, port=DASH_PORT)
