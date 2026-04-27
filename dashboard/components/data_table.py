"""Styled DataTable component with Microchip theme."""
from dash import dash_table
from utils.colors import PRIMARY_BLUE, BG_GRAY, WHITE, DARK_TEXT, GREEN, ORANGE, RED


def make_data_table(df, table_id, page_size=15, status_col=None):
    """Create a styled DataTable from a DataFrame.

    Args:
        df: pandas DataFrame
        table_id: unique ID for the table
        page_size: rows per page
        status_col: column name to apply status color formatting
    """
    if df.empty:
        columns = []
        data = []
    else:
        columns = [{'name': col, 'id': col} for col in df.columns]
        data = df.to_dict('records')

    style_data_conditional = [
        {'if': {'row_index': 'odd'}, 'backgroundColor': BG_GRAY},
    ]

    if status_col and status_col in df.columns:
        style_data_conditional.extend([
            {
                'if': {'filter_query': f'{{{status_col}}} contains "Run"', 'column_id': status_col},
                'color': GREEN, 'fontWeight': '600',
            },
            {
                'if': {'filter_query': f'{{{status_col}}} contains "Idle"', 'column_id': status_col},
                'color': ORANGE, 'fontWeight': '600',
            },
            {
                'if': {'filter_query': f'{{{status_col}}} contains "Down"', 'column_id': status_col},
                'color': RED, 'fontWeight': '600',
            },
        ])

    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=data,
        page_size=page_size,
        sort_action='native',
        filter_action='native',
        style_header={
            'backgroundColor': PRIMARY_BLUE,
            'color': WHITE,
            'fontWeight': '600',
            'fontSize': '13px',
            'padding': '10px 12px',
        },
        style_cell={
            'fontSize': '13px',
            'padding': '8px 12px',
            'textAlign': 'left',
            'fontFamily': 'Calibri, Segoe UI, sans-serif',
        },
        style_data={
            'backgroundColor': WHITE,
            'color': DARK_TEXT,
        },
        style_data_conditional=style_data_conditional,
        style_table={'overflowX': 'auto'},
    )
