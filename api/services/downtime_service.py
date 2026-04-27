"""Downtime service — event-level list + pareto by reason."""
import logging
from typing import List, Optional
import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_JOB_TYPES = ['M/C DOWN']


def _sql_events(start_date: str, end_date: str,
                areas: Optional[List[str]], job_types: List[str]) -> pd.DataFrame:
    """Pull event-level rows from SQL Server view."""
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import ORACLE_ONLY_AREAS

    # Map dashboard COLUMN_MAP (matches pages/downtime.py)
    sym = COLUMN_MAP.get('symptom', 'des_job') or 'des_job'
    rc  = COLUMN_MAP.get('downtime_reason', 'cause') or 'cause'
    otc = COLUMN_MAP.get('opr_start_time', 'datex') or 'datex'
    ttc = COLUMN_MAP.get('tech_start_time', 'date_ack') or 'date_ack'
    ec  = COLUMN_MAP.get('end_time', 'date_close') or 'date_close'
    mid = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'
    ac  = COLUMN_MAP.get('machine_area', 'id_operation') or 'id_operation'
    sc  = COLUMN_MAP.get('status', 'job_type') or 'job_type'

    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else areas
    if areas and not sql_areas:
        return pd.DataFrame()

    clauses = [
        f"[{otc}] >= :start",
        f"[{otc}] < DATEADD(DAY, 1, CAST(:end AS DATE))",
        f"[{ec}] IS NOT NULL",
        f"[{ttc}] IS NOT NULL",
        f"[{ec}] > [{ttc}]",
    ]
    params = {'start': start_date, 'end': end_date}

    if sql_areas:
        phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
        clauses.append(f"[{ac}] IN ({phs})")
        for i, a in enumerate(sql_areas):
            params[f'area_{i}'] = a
    if job_types:
        phs = ', '.join(f":jt_{i}" for i in range(len(job_types)))
        clauses.append(f"[{sc}] IN ({phs})")
        for i, jt in enumerate(job_types):
            params[f'jt_{i}'] = jt

    where = " AND ".join(clauses)
    sql = f"""
        SELECT [{mid}] AS machine_id,
               [{ac}]  AS area,
               [{sc}]  AS job_type,
               [{sym}] AS symptom,
               [{rc}]  AS cause,
               [action],
               ISNULL(by_perform, by_ack) AS technician,
               [Package Type] AS package_type,
               [lot_no]       AS lot_number,
               [mpc]          AS die_mask,
               [{otc}] AS opr_start,
               [{ttc}] AS tech_start,
               [{ec}]  AS end_time,
               ISNULL(Waiting_time, 0) AS wait_min,
               DATEDIFF(MINUTE, [{ttc}], [{ec}]) AS repair_min,
               CASE WHEN DATEPART(HOUR, [{ttc}]) BETWEEN 7 AND 18 THEN 'D' ELSE 'N' END AS shift
        FROM {VIEW_NAME}
        WHERE {where}
        ORDER BY [{otc}] DESC
    """
    df = query_df(sql, params)
    if not df.empty:
        df['source'] = 'sql'
    return df


def _oracle_events(start_date: str, end_date: str,
                   areas: Optional[List[str]], job_types: List[str]) -> pd.DataFrame:
    """Pull event-level rows from Oracle."""
    try:
        from config import ORA_ENABLED
        if not ORA_ENABLED:
            return pd.DataFrame()
        from oracle_db import fetch_oracle_data
        df = fetch_oracle_data(start_date, end_date, areas, None)
        if df is None or df.empty:
            return pd.DataFrame()
        if job_types:
            df = df[df['job_type'].isin(job_types)]
        if df.empty:
            return pd.DataFrame()
        out = pd.DataFrame({
            'machine_id': df.get('machine_id', ''),
            'area': df.get('area', ''),
            'job_type': df.get('job_type', ''),
            'symptom': df.get('symptom', ''),
            'cause': df.get('cause', ''),
            'action': df.get('action', ''),
            'technician': df.get('technician', df.get('by_ack', '')),
            'package_type': df.get('package_type', ''),
            'lot_number': df.get('lot_number', ''),
            'die_mask': df.get('die_mask', ''),
            'opr_start': df.get('date_act', df.get('datex')),
            'tech_start': df.get('datex'),
            'end_time': df.get('date_close'),
            'wait_min': df.get('wait_min', 0).fillna(0).astype(int),
            'repair_min': df.get('repair_min', 0).fillna(0).astype(int),
            'shift': df.get('shift_code', ''),
            'source': 'oracle',
        })
        return out
    except Exception as e:
        log.warning(f"Oracle events fetch failed: {e}")
        return pd.DataFrame()


def get_events(
    start_date: str,
    end_date: str,
    areas: Optional[List[str]] = None,
    job_types: Optional[List[str]] = None,
    limit: int = 1000,
) -> dict:
    """Return event-level downtime list merged from SQL + Oracle."""
    if not job_types:
        job_types = DEFAULT_JOB_TYPES

    sql_df = _sql_events(start_date, end_date, areas, job_types)
    ora_df = _oracle_events(start_date, end_date, areas, job_types)

    merged = pd.concat([sql_df, ora_df], ignore_index=True)
    total = len(merged)
    if not merged.empty:
        merged = merged.sort_values('tech_start', ascending=False, na_position='last')
        merged = merged.head(limit)

    events = []
    for _, r in merged.iterrows():
        def _s(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return v
        events.append({
            'machine_id': str(r.get('machine_id', '') or ''),
            'area': str(r.get('area', '') or ''),
            'job_type': str(r.get('job_type', '') or ''),
            'symptom': _s(r.get('symptom')),
            'cause': _s(r.get('cause')),
            'action': _s(r.get('action')),
            'technician': _s(r.get('technician')),
            'package_type': _s(r.get('package_type')),
            'lot_number': _s(r.get('lot_number')),
            'die_mask': _s(r.get('die_mask')),
            'opr_start': _s(r.get('opr_start')),
            'tech_start': _s(r.get('tech_start')),
            'end_time': _s(r.get('end_time')),
            'wait_min': int(r.get('wait_min', 0) or 0),
            'repair_min': int(r.get('repair_min', 0) or 0),
            'shift': _s(r.get('shift')),
            'source': str(r.get('source', 'sql')),
        })

    return {
        'events': events,
        'total': int(total),
        'period': {
            'start': start_date, 'end': end_date,
            'job_types': job_types, 'limit': limit,
        },
    }


def get_pareto(
    start_date: str,
    end_date: str,
    areas: Optional[List[str]] = None,
    job_types: Optional[List[str]] = None,
    reason_col: str = 'symptom',
    top_n: int = 20,
) -> dict:
    """Return pareto (grouped by symptom or cause) merged from SQL + Oracle."""
    if not job_types:
        job_types = DEFAULT_JOB_TYPES
    if reason_col not in ('symptom', 'cause'):
        reason_col = 'symptom'

    sql_df = _sql_events(start_date, end_date, areas, job_types)
    ora_df = _oracle_events(start_date, end_date, areas, job_types)
    merged = pd.concat([sql_df, ora_df], ignore_index=True)

    if merged.empty:
        return {
            'rows': [], 'total_events': 0, 'total_hours': 0.0,
            'period': {'start': start_date, 'end': end_date,
                       'job_types': job_types, 'reason_col': reason_col},
        }

    merged = merged[merged[reason_col].notna() & (merged[reason_col] != '')]
    if merged.empty:
        return {
            'rows': [], 'total_events': 0, 'total_hours': 0.0,
            'period': {'start': start_date, 'end': end_date,
                       'job_types': job_types, 'reason_col': reason_col},
        }

    agg = merged.groupby(reason_col).agg(
        events=('repair_min', 'count'),
        repair_hrs=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        wait_hrs=('wait_min', lambda x: round(x.sum() / 60.0, 1)),
        avg_repair_min=('repair_min', 'mean'),
        avg_wait_min=('wait_min', 'mean'),
        max_wait_min=('wait_min', 'max'),
    ).reset_index().rename(columns={reason_col: 'reason'})
    agg['total_hrs'] = (agg['repair_hrs'] + agg['wait_hrs']).round(1)
    agg[['avg_repair_min', 'avg_wait_min', 'max_wait_min']] = agg[
        ['avg_repair_min', 'avg_wait_min', 'max_wait_min']
    ].round(0)
    agg = agg.sort_values('total_hrs', ascending=False).head(top_n)

    rows = [{
        'reason': str(r['reason'] or 'Unknown'),
        'events': int(r['events']),
        'repair_hrs': float(r['repair_hrs']),
        'wait_hrs': float(r['wait_hrs']),
        'total_hrs': float(r['total_hrs']),
        'avg_repair_min': float(r['avg_repair_min']),
        'avg_wait_min': float(r['avg_wait_min']),
        'max_wait_min': float(r['max_wait_min']),
    } for _, r in agg.iterrows()]

    return {
        'rows': rows,
        'total_events': int(agg['events'].sum()),
        'total_hours': float(round(agg['total_hrs'].sum(), 1)),
        'period': {
            'start': start_date, 'end': end_date,
            'job_types': job_types, 'reason_col': reason_col,
        },
    }
