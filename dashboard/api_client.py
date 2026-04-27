"""Thin HTTP client for the middleware API.

Used by dashboard pages when USE_API=1. Handles auth, retries, and
converts JSON responses into pandas DataFrames matching the shape
existing code expects, so migration is a minimal diff.
"""
import logging
import os
from functools import lru_cache
from typing import Optional, List
import pandas as pd
import requests

log = logging.getLogger(__name__)

API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')
API_KEY = os.getenv('API_KEY', 'mch_dev_12345')
API_TIMEOUT = float(os.getenv('API_TIMEOUT', '10'))
USE_API = os.getenv('USE_API', '0') == '1'


class APIError(Exception):
    """Raised when an API call fails or returns an error envelope."""


def _get(path: str, params: Optional[dict] = None) -> dict:
    """GET an API endpoint; raises APIError on non-2xx or error envelope."""
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    try:
        r = requests.get(url, params=params,
                         headers={'X-API-Key': API_KEY},
                         timeout=API_TIMEOUT)
    except requests.RequestException as e:
        raise APIError(f"API request failed: {e}") from e
    if r.status_code != 200:
        raise APIError(f"API returned {r.status_code}: {r.text[:200]}")
    body = r.json()
    if body.get('status') != 'ok':
        err = body.get('error', {})
        raise APIError(f"API error {err.get('code')}: {err.get('message')}")
    return body


# ── Overview ──────────────────────────────────────────────────────────────────

def fetch_overview(areas: Optional[List[str]] = None) -> dict:
    """Return {'kpi': {...}, 'status_matrix': [...], 'updated_at': '...'}."""
    params = {}
    if areas:
        params['areas'] = ','.join(areas)
    body = _get('/api/v1/overview', params)
    return body['data']


def fetch_open_jobs(areas: Optional[List[str]] = None,
                    job_type: Optional[str] = None) -> pd.DataFrame:
    """Return open jobs as a DataFrame matching overview_open_jobs() shape."""
    params = {}
    if areas:
        params['areas'] = ','.join(areas)
    if job_type and job_type != 'ALL':
        params['job_type'] = job_type
    body = _get('/api/v1/overview/open-jobs', params)
    jobs = body['data'].get('jobs', [])
    if not jobs:
        return pd.DataFrame(columns=[
            'code_machine', 'area', 'job_type', 'des_job', 'datex', 'date_ack',
            'tech', 'wait_min', 'repair_min', 'status',
            'die_mask', 'die_size', 'package_type', 'wire_type', 'source',
        ])
    df = pd.DataFrame(jobs)
    for col in ('datex', 'date_ack'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


# ── Utilization ───────────────────────────────────────────────────────────────

def _rows_to_df(rows: list, date_cols=()) -> pd.DataFrame:
    """List of dicts → DataFrame, parsing any ISO date columns."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def fetch_utilization_detail(start: str, end: str,
                             areas=None, shift=None,
                             selected_month=None) -> dict:
    """Return full utilization payload (see utilization_service.get_utilization_detail)."""
    params = {'start': start, 'end': end}
    if areas:
        params['areas'] = ','.join(areas)
    if shift:
        params['shift'] = shift
    if selected_month:
        params['selected_month'] = selected_month
    return _get('/api/v1/utilization/detail', params)['data']


def fetch_utilization_by_machine(start: str, end: str,
                                 areas=None, shift=None) -> pd.DataFrame:
    """Per-machine util rows matching util_by_machine() output."""
    params = {'start': start, 'end': end}
    if areas:
        params['areas'] = ','.join(areas)
    if shift:
        params['shift'] = shift
    rows = _get('/api/v1/utilization/by-machine', params)['data'].get('rows', [])
    return _rows_to_df(rows)


def fetch_utilization_attention(start: str, end: str,
                                areas=None, shift=None) -> pd.DataFrame:
    """Attention machines rows matching util_attention_machines() output."""
    params = {'start': start, 'end': end}
    if areas:
        params['areas'] = ','.join(areas)
    if shift:
        params['shift'] = shift
    rows = _get('/api/v1/utilization/attention', params)['data'].get('rows', [])
    return _rows_to_df(rows)


def utilization_detail_to_frames(data: dict) -> dict:
    """Convert /utilization/detail JSON into the DataFrames that
    pages/utilization.py's update_primary uses (drop-in replacement).

    Returns keys: kpi_df, trend_df, area_df, cnt_df, area_cnt_df,
    scatter_df, top_down_df, top_lost_df, mach_per_cause_df,
    prev_df, prev_cnt_total (int).
    """
    raw = data.get('raw', {}) or {}
    return {
        'kpi_df':      _rows_to_df(raw.get('kpi_totals', [])),
        'trend_df':    _rows_to_df(data.get('monthly_trend', [])),
        'area_df':     _rows_to_df(raw.get('area_totals', [])),
        'area_cnt_df': _rows_to_df(raw.get('area_counts', [])),
        'cnt_df':      pd.DataFrame([{'machine_count': raw.get('machine_count', 0)}]),
        'scatter_df':  _rows_to_df(data.get('scatter', [])),
        'top_down_df': _rows_to_df(data.get('top_down', [])),
        'top_lost_df': _rows_to_df(data.get('top_lost', [])),
        'mach_per_cause_df': _rows_to_df(data.get('machines_per_cause', [])),
        'prev_df':     _rows_to_df(raw.get('prev_kpi_totals', [])),
        'prev_mc':     int(raw.get('prev_machine_count', 0)),
    }


# ── Machines / areas ──────────────────────────────────────────────────────────

def fetch_areas() -> list:
    """Return list of areas, each a dict with keys: area, short_name, source, machine_count."""
    body = _get('/api/v1/areas')
    return body['data'].get('areas', [])


def fetch_machine_list(area=None, key_only=False) -> pd.DataFrame:
    """Return machine master rows as DataFrame."""
    params = {}
    if area:
        params['area'] = area
    if key_only:
        params['key_only'] = 'true'
    rows = _get('/api/v1/machines', params)['data'].get('machines', [])
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['machine_id', 'des_machine', 'area', 'area_name',
                 'mfg', 'model', 'sn', 'short_name', 'flag_key',
                 'flag_automotive', 'flag_gold'])


def fetch_machine_detail(machine_id: str, recent_limit: int = 20) -> dict:
    """Return machine detail (info + flags + kpis + recent_events)."""
    params = {'id': machine_id, 'recent_limit': recent_limit}
    return _get('/api/v1/machines/detail', params)['data']


def fetch_machine_records(machine_id: str, limit: int = 200) -> pd.DataFrame:
    """Return raw records for a machine (from vw_job_nokey, all columns)."""
    params = {'id': machine_id, 'limit': limit}
    rows = _get('/api/v1/machines/records', params)['data'].get('records', [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ('datex', 'date_ack', 'date_close', 'date_act', 'opr_start', 'end_time'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def overview_to_dataframes(data: dict) -> tuple:
    """Convert /overview JSON into (matrix_df, kpi_dict) matching page expectations."""
    matrix_rows = data.get('status_matrix', [])
    matrix_df = pd.DataFrame(matrix_rows) if matrix_rows else pd.DataFrame(
        columns=['job_type', 'waiting', 'on_process', 'closed', 'total'])

    kpi = data.get('kpi', {})
    # Match the dict shape that pages/overview.py expects from kpi_df.iloc[0]
    return matrix_df, {
        'total_key_machines': kpi.get('total_machines', 0),
        'waiting_count':      kpi.get('waiting', 0),
        'on_process_count':   kpi.get('on_process', 0),
        'down_count':         kpi.get('down', 0),
        'closed_this_shift':  kpi.get('closed_this_shift', 0),
        'running':            kpi.get('running', 0),
    }
