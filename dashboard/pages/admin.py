"""Admin page — User management (CRUD + role assignment)."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
from flask_login import current_user

from components.header import make_page_header
from utils.colors import PRIMARY_BLUE, GREEN, ORANGE, RED, MED_GRAY

dash.register_page(__name__, path='/admin', name='Admin')

ROLE_OPTIONS = [
    {'label': 'Admin',      'value': 'admin'},
    {'label': 'Supervisor', 'value': 'supervisor'},
    {'label': 'Viewer',     'value': 'viewer'},
]

layout = html.Div([
    make_page_header("User Management"),

    # Access check — rendered dynamically
    html.Div(id='admin-content'),

    # Hidden stores
    dcc.Store(id='admin-refresh-trigger', data=0),

    # Add user modal
    dbc.Modal([
        dbc.ModalHeader("Add New User"),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Username", className='filter-label'),
                    dbc.Input(id='admin-new-username', type='text',
                              placeholder='e.g. B04469'),
                ], md=6),
                dbc.Col([
                    html.Label("Display Name", className='filter-label'),
                    dbc.Input(id='admin-new-display', type='text',
                              placeholder='e.g. John Smith'),
                ], md=6),
            ], className='mb-3'),
            dbc.Row([
                dbc.Col([
                    html.Label("Password", className='filter-label'),
                    dbc.Input(id='admin-new-password', type='password',
                              placeholder='Min 6 characters'),
                ], md=6),
                dbc.Col([
                    html.Label("Role", className='filter-label'),
                    dcc.Dropdown(id='admin-new-role', options=ROLE_OPTIONS,
                                 value='viewer', clearable=False,
                                 style={'fontSize': '13px'}),
                ], md=6),
            ]),
        ]),
        dbc.ModalFooter([
            html.Div(id='admin-add-msg', style={'flex': '1', 'fontSize': '13px'}),
            dbc.Button("Cancel", id='admin-modal-cancel', color='secondary', size='sm'),
            dbc.Button("Create User", id='admin-modal-save', color='primary', size='sm'),
        ]),
    ], id='admin-modal', is_open=False, centered=True),

], className='page-container')


@callback(
    Output('admin-content', 'children'),
    Input('admin-refresh-trigger', 'data'),
)
def load_admin_content(trigger):
    """Load user table — admin only."""
    if not current_user.is_authenticated or current_user.role != 'admin':
        return html.Div([
            html.H4("Access Denied", style={'color': RED}),
            html.P("Only admin users can access this page.",
                    style={'color': MED_GRAY}),
        ], style={'padding': '40px', 'textAlign': 'center'})

    from db import query_df
    try:
        df = query_df("SELECT id, username, display_name, role, created_at FROM dbo.dashboard_users ORDER BY id")
    except Exception as e:
        return html.Div(f"Error: {e}", style={'color': RED, 'padding': '20px'})

    if df.empty:
        return html.Div("No users found.", style={'color': MED_GRAY, 'padding': '20px'})

    df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d %H:%M')

    return html.Div([
        # Action bar
        html.Div([
            html.Span(f"{len(df)} users", style={
                'fontSize': '13px', 'color': MED_GRAY, 'marginRight': '16px'}),
            dbc.Button("Add User", id='admin-btn-add', size='sm', color='primary'),
        ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'flex-end',
                  'marginBottom': '12px'}),

        # User table
        dash_table.DataTable(
            id='admin-user-table',
            columns=[
                {'name': 'ID',       'id': 'id', 'editable': False},
                {'name': 'Username', 'id': 'username', 'editable': False},
                {'name': 'Display Name', 'id': 'display_name', 'editable': True},
                {'name': 'Role',     'id': 'role', 'editable': True,
                 'presentation': 'dropdown'},
                {'name': 'Created',  'id': 'created_at', 'editable': False},
            ],
            data=df.to_dict('records'),
            editable=True,
            dropdown={
                'role': {
                    'options': ROLE_OPTIONS,
                },
            },
            row_deletable=True,
            sort_action='native',
            style_header={
                'backgroundColor': '#EDF2FF', 'color': PRIMARY_BLUE,
                'fontWeight': '600', 'fontSize': '12px', 'padding': '10px 14px',
                'fontFamily': 'DM Sans, sans-serif',
                'borderBottom': f'2px solid {PRIMARY_BLUE}',
            },
            style_cell={
                'fontSize': '13px', 'padding': '8px 14px',
                'fontFamily': 'IBM Plex Sans, sans-serif',
                'textAlign': 'left', 'border': 'none',
                'borderBottom': '1px solid #EEF0F4',
            },
            style_data={'color': '#1A1F2E'},
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#FAFBFC'},
                {'if': {'column_id': 'role', 'filter_query': '{role} = "admin"'},
                 'color': PRIMARY_BLUE, 'fontWeight': '700'},
                {'if': {'column_id': 'role', 'filter_query': '{role} = "supervisor"'},
                 'color': GREEN, 'fontWeight': '600'},
                {'if': {'column_id': 'role', 'filter_query': '{role} = "viewer"'},
                 'color': ORANGE, 'fontWeight': '600'},
            ],
            style_table={'overflowX': 'auto', 'borderRadius': '8px'},
            style_as_list_view=True,
        ),

        # Save changes button
        html.Div([
            dbc.Button("Save Changes", id='admin-save-changes', size='sm',
                       color='success', className='me-2'),
            html.Span(id='admin-save-msg', style={'fontSize': '13px'}),
        ], style={'marginTop': '12px'}),

        # Reset password section
        html.Hr(style={'margin': '24px 0', 'opacity': '0.15'}),
        html.H6("Reset Password", style={'fontWeight': '600', 'fontSize': '14px',
                                          'fontFamily': 'DM Sans, sans-serif'}),
        dbc.Row([
            dbc.Col([
                dbc.Input(id='admin-reset-username', type='text',
                          placeholder='Username', size='sm'),
            ], md=3),
            dbc.Col([
                dbc.Input(id='admin-reset-password', type='password',
                          placeholder='New password', size='sm'),
            ], md=3),
            dbc.Col([
                dbc.Button("Reset", id='admin-reset-btn', size='sm', color='warning'),
                html.Span(id='admin-reset-msg', style={'fontSize': '13px', 'marginLeft': '10px'}),
            ], md=6),
        ], className='g-2'),
    ])


# ── Open/close modal ──────────────────────────────────────────────────────────
@callback(
    Output('admin-modal', 'is_open'),
    Input('admin-btn-add', 'n_clicks'),
    Input('admin-modal-cancel', 'n_clicks'),
    Input('admin-modal-save', 'n_clicks'),
    State('admin-modal', 'is_open'),
    prevent_initial_call=True,
)
def toggle_modal(open_clicks, cancel_clicks, save_clicks, is_open):
    ctx = dash.ctx.triggered_id
    if ctx == 'admin-btn-add':
        return True
    return False


# ── Create user ───────────────────────────────────────────────────────────────
@callback(
    Output('admin-add-msg', 'children'),
    Output('admin-refresh-trigger', 'data', allow_duplicate=True),
    Input('admin-modal-save', 'n_clicks'),
    State('admin-new-username', 'value'),
    State('admin-new-display', 'value'),
    State('admin-new-password', 'value'),
    State('admin-new-role', 'value'),
    State('admin-refresh-trigger', 'data'),
    prevent_initial_call=True,
)
def create_user(n, username, display_name, password, role, trigger):
    if not n or not username or not password:
        return html.Span("Fill in all fields", style={'color': ORANGE}), dash.no_update
    if len(password) < 6:
        return html.Span("Password must be 6+ chars", style={'color': ORANGE}), dash.no_update

    from auth import hash_password
    from db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO dbo.dashboard_users (username, password_hash, role, display_name) "
                "VALUES (:u, :h, :r, :d)"
            ), {'u': username, 'h': hash_password(password),
                'r': role, 'd': display_name or username})
            conn.commit()
        return html.Span(f"User '{username}' created!", style={'color': GREEN}), (trigger or 0) + 1
    except Exception as e:
        return html.Span(f"Error: {e}", style={'color': RED}), dash.no_update


# ── Save changes (role + display name edits, row deletions) ───────────────────
@callback(
    Output('admin-save-msg', 'children'),
    Output('admin-refresh-trigger', 'data', allow_duplicate=True),
    Input('admin-save-changes', 'n_clicks'),
    State('admin-user-table', 'data'),
    State('admin-refresh-trigger', 'data'),
    prevent_initial_call=True,
)
def save_changes(n, table_data, trigger):
    if not n or not table_data:
        return "", dash.no_update

    from db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # Get current IDs in DB
            existing = conn.execute(text("SELECT id FROM dbo.dashboard_users")).fetchall()
            existing_ids = {r[0] for r in existing}
            table_ids = {r['id'] for r in table_data}

            # Delete removed rows
            deleted = existing_ids - table_ids
            for did in deleted:
                conn.execute(text("DELETE FROM dbo.dashboard_users WHERE id = :id"),
                             {'id': did})

            # Update remaining rows
            for row in table_data:
                conn.execute(text(
                    "UPDATE dbo.dashboard_users SET role = :r, display_name = :d "
                    "WHERE id = :id"
                ), {'r': row['role'], 'd': row.get('display_name', ''), 'id': row['id']})

            conn.commit()
        return html.Span("Saved!", style={'color': GREEN, 'fontWeight': '600'}), (trigger or 0) + 1
    except Exception as e:
        return html.Span(f"Error: {e}", style={'color': RED}), dash.no_update


# ── Reset password ────────────────────────────────────────────────────────────
@callback(
    Output('admin-reset-msg', 'children'),
    Input('admin-reset-btn', 'n_clicks'),
    State('admin-reset-username', 'value'),
    State('admin-reset-password', 'value'),
    prevent_initial_call=True,
)
def reset_password(n, username, new_password):
    if not n or not username or not new_password:
        return html.Span("Fill in username + new password", style={'color': ORANGE})
    if len(new_password) < 6:
        return html.Span("Password must be 6+ chars", style={'color': ORANGE})

    from auth import hash_password
    from db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "UPDATE dbo.dashboard_users SET password_hash = :h WHERE username = :u"
            ), {'h': hash_password(new_password), 'u': username})
            conn.commit()
            if result.rowcount == 0:
                return html.Span(f"User '{username}' not found", style={'color': RED})
        return html.Span(f"Password reset for '{username}'!", style={'color': GREEN})
    except Exception as e:
        return html.Span(f"Error: {e}", style={'color': RED})
