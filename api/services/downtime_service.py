"""Downtime service — event-level list + pareto by reason + full detail."""
import logging
from typing import List, Optional
import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_JOB_TYPES = ['M/C DOWN']

ALL_DT_JOB_TYPES = [
    'M/C DOWN', 'SETUP', 'SETUP BY OPERATOR', 'PM', 'CONVERT',
    'FACILITY DOWN', 'ENGINEERING DOWN', 'CLEAN MOLD', 'CHANGE CAP',
]


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        row = {}
        for k, v in r.items():
            if v is None:
                row[k] = None
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
            elif hasattr(v, 'item'):
                try:
                    row[k] = v.item()
                except Exception:
                    row[k] = str(v)
            elif isinstance(v, pd.Timestamp):
                row[k] = v.isoformat()
            else:
                row[k] = v
        out.append(row)
    return out


def _build_dt_where(otc, ec, sc, ac, mid,
                    start_date, end_date, areas, machines, shift, job_types):
    """Mirror pages/downtime.py::_build_where."""
    from utils.queries import ORACLE_ONLY_AREAS
    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else areas
    if areas and not sql_areas:
        return "WHERE 1=0", {}

    phs_jt = ', '.join(f"'{j}'" for j in job_types)
    clauses = [f"[{sc}] IN ({phs_jt})"]
    params = {}
    if start_date:
        clauses.append(f"[{otc}] >= :start_date"); params['start_date'] = start_date
    if end_date:
        clauses.append(f"[{otc}] < DATEADD(DAY, 1, CAST(:end_date AS DATE))"); params['end_date'] = end_date
    if sql_areas:
        phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
        clauses.append(f"[{ac}] IN ({phs})")
        for i, a in enumerate(sql_areas): params[f'area_{i}'] = a
    if machines:
        mphs = ', '.join(f":machine_{i}" for i in range(len(machines)))
        clauses.append(f"[{mid}] IN ({mphs})")
        for i, m in enumerate(machines): params[f'machine_{i}'] = m
    if shift == 'DAY':
        clauses.append(f"DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18")
    elif shift == 'NIGHT':
        clauses.append(f"DATEPART(HOUR, [{otc}]) NOT BETWEEN 7 AND 18")
    return "WHERE " + " AND ".join(clauses), params


def get_downtime_detail(
    job_types: List[str],
    start_date: str, end_date: str,
    areas: Optional[List[str]] = None,
    machines: Optional[List[str]] = None,
    shift: Optional[str] = None,
    reason_col: Optional[str] = None,
) -> dict:
    """Bundled detail payload for the Downtime & Setup page.

    Returns 6 datasets merged from SQL Server + Oracle:
      reason (pareto), machines_by_reason, daily_shift,
      machine_daily, symptom_cause, events
    """
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP

    rc  = COLUMN_MAP.get('downtime_reason', 'cause') or 'cause'
    sym = COLUMN_MAP.get('symptom', 'des_job') or 'des_job'
    otc = COLUMN_MAP.get('opr_start_time', 'datex') or 'datex'
    ttc = COLUMN_MAP.get('tech_start_time', 'date_ack') or 'date_ack'
    ec  = COLUMN_MAP.get('end_time', 'date_close') or 'date_close'
    mid = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'
    ac  = COLUMN_MAP.get('machine_area', 'id_operation') or 'id_operation'
    sc  = COLUMN_MAP.get('status', 'job_type') or 'job_type'
    grp = reason_col or rc

    where, params = _build_dt_where(
        otc, ec, sc, ac, mid, start_date, end_date, areas, machines, shift, job_types)

    reason_df = query_df(f"""
        SELECT [{grp}] AS reason,
               COUNT(*) AS events,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
               SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0
                   + SUM(ISNULL(Waiting_time, 0)) / 60.0      AS total_hrs,
               AVG(DATEDIFF(MINUTE, [{ttc}], [{ec}]))          AS avg_repair_min,
               AVG(ISNULL(Waiting_time, 0))                    AS avg_wait_min,
               MAX(ISNULL(Waiting_time, 0))                    AS max_wait_min
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{grp}]
        ORDER BY total_hrs DESC
    """, params)

    machine_df = query_df(f"""
        SELECT [{mid}] AS machine_id,
               [{grp}] AS reason,
               COUNT(*) AS event_count,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS total_hours
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{mid}], [{grp}]
        ORDER BY total_hours DESC
    """, params)

    symptom_cause_df = pd.DataFrame()
    if reason_col and reason_col != rc:
        symptom_cause_df = query_df(f"""
            SELECT [{sym}] AS symptom, [{rc}] AS root_cause,
                   COUNT(*) AS events,
                   SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
                   SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs,
                   SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0
                       + SUM(ISNULL(Waiting_time, 0)) / 60.0      AS total_hrs,
                   AVG(DATEDIFF(MINUTE, [{ttc}], [{ec}]))          AS avg_repair_min,
                   AVG(ISNULL(Waiting_time, 0))                    AS avg_wait_min
            FROM {VIEW_NAME} {where}
            AND [{rc}] IS NOT NULL AND [{rc}] != ''
            AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
            GROUP BY [{sym}], [{rc}]
            ORDER BY total_hrs DESC
        """, params)

    machine_daily_df = query_df(f"""
        SELECT [{mid}] AS machine_id,
               [{grp}] AS reason,
               CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                    THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                    ELSE CAST([{otc}] AS DATE) END AS day,
               CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                    THEN 'Day' ELSE 'Night' END AS shift_name,
               COUNT(*) AS events,
               SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS total_hours,
               SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs
        FROM {VIEW_NAME} {where}
        AND [{grp}] IS NOT NULL AND [{grp}] != ''
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY [{mid}], [{grp}],
                 CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                      THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                      ELSE CAST([{otc}] AS DATE) END,
                 CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                      THEN 'Day' ELSE 'Night' END
    """, params)

    daily_shift_df = query_df(f"""
        SELECT
            CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                 THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                 ELSE CAST([{otc}] AS DATE)
            END AS day,
            CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                 THEN 'Day' ELSE 'Night' END AS shift_name,
            COUNT(*) AS events,
            SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0 AS repair_hrs,
            SUM(ISNULL(Waiting_time, 0)) / 60.0            AS wait_hrs
        FROM {VIEW_NAME} {where}
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        GROUP BY
            CASE WHEN DATEPART(HOUR, [{otc}]) >= 19
                 THEN DATEADD(DAY, 1, CAST([{otc}] AS DATE))
                 ELSE CAST([{otc}] AS DATE) END,
            CASE WHEN DATEPART(HOUR, [{otc}]) BETWEEN 7 AND 18
                 THEN 'Day' ELSE 'Night' END
        ORDER BY day, shift_name
    """, params)

    # Event detail (ALL job types, not just this section's)
    evt_where, evt_params = _build_dt_where(
        otc, ec, sc, ac, mid, start_date, end_date, areas, machines, shift,
        ALL_DT_JOB_TYPES)
    events_df = query_df(f"""
        SELECT TOP 500 [{mid}] AS machine_id, [{ac}] AS area,
               [{sc}] AS job_type, [{sym}] AS symptom, [{rc}] AS cause, [action],
               [{otc}] AS event_time,
               ISNULL(by_perform, by_ack) AS tech,
               ISNULL(Waiting_time, 0) AS wait_min,
               DATEDIFF(MINUTE, [{ttc}], [{ec}]) AS repair_min,
               [Package Type] AS package_type, [lot_no], [mpc] AS die_mask
        FROM {VIEW_NAME} {evt_where}
        AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
        ORDER BY [{otc}] DESC
    """, evt_params)

    # ── Oracle merge ──────────────────────────────────────────────────────────
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import (
                ora_dt_reason, ora_dt_machine, ora_dt_daily_shift,
                ora_dt_machine_daily, ora_dt_symptom_cause,
            )
            if not areas or any(a in ('ISO', 'FS') for a in areas):
                ora = fetch_oracle_data(start_date, end_date, areas, shift)
                if ora is not None:
                    r_col = 'symptom' if reason_col else 'cause'
                    reason_df = pd.concat(
                        [reason_df, ora_dt_reason(ora, job_types, r_col)],
                        ignore_index=True)
                    reason_df = (reason_df.groupby('reason')
                                 .agg({c: 'sum' for c in reason_df.columns if c != 'reason'})
                                 .reset_index()
                                 .sort_values('total_hrs', ascending=False)
                                 .reset_index(drop=True))
                    machine_df = pd.concat(
                        [machine_df, ora_dt_machine(ora, job_types, r_col)],
                        ignore_index=True)
                    daily_shift_df = pd.concat(
                        [daily_shift_df, ora_dt_daily_shift(ora, job_types)],
                        ignore_index=True)
                    daily_shift_df = (daily_shift_df.groupby(['day', 'shift_name'])
                                      .agg({c: 'sum' for c in daily_shift_df.columns if c not in ('day', 'shift_name')})
                                      .reset_index()
                                      .sort_values(['day', 'shift_name']))
                    machine_daily_df = pd.concat(
                        [machine_daily_df, ora_dt_machine_daily(ora, job_types, r_col)],
                        ignore_index=True)
                    if reason_col and reason_col != rc:
                        ora_sc = ora_dt_symptom_cause(ora, job_types)
                        if not ora_sc.empty:
                            symptom_cause_df = pd.concat(
                                [symptom_cause_df, ora_sc], ignore_index=True)
                    if {'machine_id', 'area', 'job_type', 'symptom',
                        'cause', 'datex', 'badge', 'wait_min', 'repair_min'
                        }.issubset(ora.columns):
                        # Oracle S_DATE (mapped to datex) is midnight-aligned,
                        # so it would always render as HH:MM = 00:00 in the
                        # Event Detail table. P_START (mapped to date_ack) is
                        # the actual tech start timestamp — use it when present.
                        time_col = 'date_ack' if 'date_ack' in ora.columns else 'datex'
                        base_cols = ['machine_id', 'area', 'job_type',
                                     'symptom', 'cause', time_col, 'badge',
                                     'wait_min', 'repair_min']
                        extra_cols = [c for c in
                                      ('package_type', 'lot_no', 'die_mask')
                                      if c in ora.columns]
                        ora_events = ora[base_cols + extra_cols].copy()
                        ora_events = ora_events.rename(
                            columns={time_col: 'event_time', 'badge': 'tech'})
                        ora_events['wait_min'] = ora_events['wait_min'].round(0).astype(int)
                        ora_events['repair_min'] = ora_events['repair_min'].round(0).astype(int)
                        for c in ('package_type', 'lot_no', 'die_mask'):
                            if c not in ora_events.columns:
                                ora_events[c] = ''
                            else:
                                ora_events[c] = ora_events[c].fillna('').astype(str)
                        events_df = pd.concat(
                            [events_df, ora_events], ignore_index=True)
                        events_df = events_df.sort_values(
                            'event_time', ascending=False).head(200)
    except Exception as e:
        log.warning(f"Oracle downtime merge failed: {e}")

    return {
        'reason': _df_to_records(reason_df),
        'machines_by_reason': _df_to_records(machine_df),
        'daily_shift': _df_to_records(daily_shift_df),
        'machine_daily': _df_to_records(machine_daily_df),
        'symptom_cause': _df_to_records(symptom_cause_df),
        'events': _df_to_records(events_df),
        'period': {
            'start': start_date, 'end': end_date,
            'shift': shift or 'ALL', 'job_types': job_types,
            'reason_col': reason_col,
        },
    }


def get_downtime_machines(areas: Optional[List[str]] = None) -> dict:
    """Distinct machines with M/C DOWN or SETUP events — for filter dropdown.

    Handles Oracle-only areas (ISO/FS) by pulling their machine list from
    the Oracle in-memory store instead of SQL Server.
    """
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import ORACLE_ONLY_AREAS

    mid = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'
    ac  = COLUMN_MAP.get('machine_area', 'id_operation') or 'id_operation'
    sc  = COLUMN_MAP.get('status', 'job_type') or 'job_type'

    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else None
    ora_areas = [a for a in areas if a in ORACLE_ONLY_AREAS] if areas else list(ORACLE_ONLY_AREAS)

    machines = []

    # SQL Server side — only query if the user selected at least one non-Oracle
    # area, or didn't filter at all. If they filtered to Oracle-only areas,
    # skip SQL entirely instead of returning every machine.
    if sql_areas or not areas:
        clauses = [f"[{sc}] IN ('M/C DOWN','SETUP','SETUP BY OPERATOR')"]
        params = {}
        if sql_areas:
            phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
            clauses.append(f"[{ac}] IN ({phs})")
            for i, a in enumerate(sql_areas):
                params[f'area_{i}'] = a
        where = "WHERE " + " AND ".join(clauses)
        df = query_df(f"SELECT DISTINCT [{mid}] AS m FROM {VIEW_NAME} {where} ORDER BY [{mid}]",
                      params)
        machines.extend(str(r['m']) for _, r in df.iterrows() if r.get('m'))

    # Oracle side — ISO/FS machines come from the background-loaded Oracle
    # dataset (no current SQL Server connection for them).
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED and ora_areas:
            from oracle_db import _ensure_loaded, _store, _lock
            _ensure_loaded()
            with _lock:
                ora_df = _store.get('df')
            if ora_df is not None and not ora_df.empty:
                sub = ora_df[ora_df['area'].isin(ora_areas)]
                if 'job_type' in sub.columns:
                    sub = sub[sub['job_type'].isin(
                        ['M/C DOWN', 'SETUP', 'SETUP BY OPERATOR'])]
                machines.extend(
                    str(m) for m in sub['machine_id'].dropna().unique())
    except Exception as e:
        log.warning(f"Oracle machine list fetch failed: {e}")

    # Dedupe + sort
    machines = sorted(set(machines))
    return {'machines': machines, 'total': len(machines)}


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
