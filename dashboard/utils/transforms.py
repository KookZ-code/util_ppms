"""Data transformation and aggregation functions."""
import pandas as pd


def compute_kpi_summary(status_df):
    """Compute KPI values from status count DataFrame.

    Args:
        status_df: DataFrame with columns ['status', 'cnt']

    Returns:
        dict with total, running, idle, down counts and utilization %
    """
    total = int(status_df['cnt'].sum())
    status_map = {}
    for _, row in status_df.iterrows():
        s = str(row['status']).strip().lower()
        status_map[s] = status_map.get(s, 0) + int(row['cnt'])

    running = status_map.get('running', 0) + status_map.get('run', 0)
    idle = status_map.get('idle', 0) + status_map.get('standby', 0)
    down = status_map.get('down', 0) + status_map.get('maintenance', 0) + status_map.get('pm', 0)

    utilization = (running / total * 100) if total > 0 else 0

    return {
        'total': total,
        'running': running,
        'idle': idle,
        'down': down,
        'utilization': round(utilization, 1),
    }


def pivot_status_by_area(df):
    """Pivot status-by-area data for stacked bar chart.

    Args:
        df: DataFrame with columns ['area', 'status', 'cnt']

    Returns:
        DataFrame pivoted with areas as rows and statuses as columns
    """
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index='area', columns='status', values='cnt', fill_value=0).reset_index()


def compute_utilization_trend(df):
    """Compute daily utilization percentage from trend data.

    Args:
        df: DataFrame with columns ['date', 'status', 'cnt']

    Returns:
        DataFrame with ['date', 'utilization_pct']
    """
    if df.empty:
        return pd.DataFrame(columns=['date', 'utilization_pct'])

    daily = df.pivot_table(index='date', columns='status', values='cnt', fill_value=0).reset_index()

    running_cols = [c for c in daily.columns if str(c).lower() in ('running', 'run')]
    total_cols = [c for c in daily.columns if c != 'date']

    daily['running_total'] = daily[running_cols].sum(axis=1) if running_cols else 0
    daily['total'] = daily[total_cols].sum(axis=1)
    daily['utilization_pct'] = (daily['running_total'] / daily['total'] * 100).round(1)

    return daily[['date', 'utilization_pct']]


def format_duration(hours):
    """Format hours into a readable string."""
    if pd.isna(hours) or hours == 0:
        return "0h"
    if hours < 1:
        return f"{int(hours * 60)}m"
    return f"{hours:.1f}h"
