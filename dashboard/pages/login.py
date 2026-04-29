"""Login page — clean, professional login form."""
import dash
from dash import html, dcc, callback, Input, Output

dash.register_page(__name__, path='/login', name='Login')

layout = html.Div([
    html.Div([
        # Logo / Brand
        html.Div([
            html.Div(style={
                'width': '10px', 'height': '10px', 'borderRadius': '50%',
                'background': '#FFD53A', 'display': 'inline-block',
                'marginRight': '10px', 'verticalAlign': 'middle',
            }),
            html.Span("Machine Dashboard", style={
                'fontSize': '20px', 'fontWeight': '700', 'color': '#0E3689',
                'fontFamily': 'DM Sans, sans-serif',
            }),
        ], style={'textAlign': 'center', 'marginBottom': '30px'}),

        # Login form (plain HTML form, posts to /auth/login)
        html.Form([
            html.Div([
                html.Label("Username", style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': '#4A5568',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px',
                    'marginBottom': '6px', 'display': 'block',
                }),
                dcc.Input(
                    type='text', name='username', id='login-username',
                    placeholder='Enter username',
                    value='guest',
                    autoComplete='username',
                    style={
                        'width': '100%', 'padding': '10px 14px', 'fontSize': '14px',
                        'border': '1.5px solid #E2E6ED', 'borderRadius': '8px',
                        'outline': 'none', 'fontFamily': 'IBM Plex Sans, sans-serif',
                    },
                ),
            ], style={'marginBottom': '16px'}),

            html.Div([
                html.Label("Password", style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': '#4A5568',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px',
                    'marginBottom': '6px', 'display': 'block',
                }),
                dcc.Input(
                    type='password', name='password', id='login-password',
                    placeholder='Enter password',
                    value='guest',
                    autoComplete='current-password',
                    style={
                        'width': '100%', 'padding': '10px 14px', 'fontSize': '14px',
                        'border': '1.5px solid #E2E6ED', 'borderRadius': '8px',
                        'outline': 'none', 'fontFamily': 'IBM Plex Sans, sans-serif',
                    },
                ),
            ], style={'marginBottom': '8px'}),

            # Hint so users know these are the guest defaults
            html.Div("Default: guest / guest — click Sign In to continue as viewer",
                     style={'fontSize': '11px', 'color': '#8A96A8',
                            'marginBottom': '16px', 'textAlign': 'center'}),

            html.Button("Sign In", type='submit', style={
                'width': '100%', 'padding': '12px', 'fontSize': '14px',
                'fontWeight': '600', 'color': '#fff', 'background': '#0E3689',
                'border': 'none', 'borderRadius': '8px', 'cursor': 'pointer',
                'fontFamily': 'DM Sans, sans-serif',
                'boxShadow': '0 2px 8px rgba(14,54,137,0.3)',
            }),

            # Error message
            html.Div(id='login-error', style={'marginTop': '12px', 'textAlign': 'center'}),

        ], method='POST', action='/auth/login'),

        # Footer
        html.Div("Microchip Technology  ·  Proprietary and Confidential",
                 style={'textAlign': 'center', 'fontSize': '11px', 'color': '#8A96A8',
                        'marginTop': '30px'}),

    ], style={
        'width': '380px', 'padding': '40px', 'background': '#FFFFFF',
        'borderRadius': '16px', 'boxShadow': '0 8px 32px rgba(0,0,0,0.12)',
        'border': '1px solid #E2E6ED',
    }),
], style={
    'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center',
    'minHeight': '100vh', 'background': '#F0F2F5',
})


@callback(
    Output('login-error', 'children'),
    Input('url', 'search'),
)
def show_login_error(search):
    if search and 'error=1' in search:
        return html.Span("Invalid username or password",
                         style={'color': '#CC0000', 'fontSize': '13px', 'fontWeight': '600'})
    return ""
