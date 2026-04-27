"""Overview service — unified live plant status from SQL Server + Oracle.

Reuses dashboard/utils/queries.py and dashboard/oracle_db.py. No duplication.
"""
import logging
import pandas as pd
from typing import List, Optional

log = logging.getLogger(__name__)


def _sql_overview(selected_areas: Optional[List[str]] = None):
    """Run SQL Server overview queries, filtered by area if given."""
    from db import query_df
    from utils.queries import (
        overview_status_matrix, overview_kpi_summary, ORACLE_ONLY_AREAS,
    )

    if not selected_areas:
        matrix_df = query_df(overview_status_matrix())
        kpi_df = query_df(overview_kpi_summary())
        return matrix_df, kpi_df

    sql_areas = [a for a in selected_areas if a not in ORACLE_ONLY_AREAS]
    if not sql_areas:
        empty_matrix = pd.DataFrame(
            columns=['job_type', 'waiting', 'on_process', 'closed', 'total']
        )
        empty_kpi = pd.DataFrame([{
            'total_key_machines': 0, 'waiting_count': 0,
            'on_process_count': 0, 'down_count': 0, 'closed_this_shift': 0,
        }])
        return empty_matrix, empty_kpi

    area_in = ', '.join(f"'{a}'" for a in sql_areas)
    matrix_df = query_df(f"""
        SELECT job_type,
               SUM(CASE WHEN date_ack IS NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS waiting,
               SUM(CASE WHEN date_ack IS NOT NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS on_process,
               SUM(CASE WHEN date_close IS NOT NULL THEN 1 ELSE 0 END) AS closed,
               COUNT(*) AS total
        FROM [dbo].[job_list]
        WHERE code_machine IS NOT NULL AND code_machine != ''
          AND id_operation IN ({area_in})
        GROUP BY job_type ORDER BY total DESC
    """)
    kpi_df = query_df(f"""
        SELECT
            (SELECT COUNT(*) FROM dbo.machine
             WHERE id_operation IN ({area_in}) AND id_operation != 'WB'
               AND flag_key = 1 AND ISNULL(flag_delete,0) != 1) AS total_key_machines,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
               AND date_ack IS NULL AND id_operation IN ({area_in})) AS waiting_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
               AND date_ack IS NOT NULL AND id_operation IN ({area_in})) AS on_process_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
               AND job_type = 'M/C DOWN' AND id_operation IN ({area_in})) AS down_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NOT NULL AND code_machine != ''
               AND LEN(code_machine) > 3
               AND id_operation IN ({area_in})
               AND date_close >= CASE
                   WHEN DATEPART(HOUR, GETDATE()) BETWEEN 7 AND 18
                   THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '07:00'
                   WHEN DATEPART(HOUR, GETDATE()) >= 19
                   THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '19:00'
                   ELSE CAST(DATEADD(DAY, -1, CAST(GETDATE() AS DATE)) AS DATETIME) + '19:00'
               END) AS closed_this_shift
    """)
    return matrix_df, kpi_df


def _oracle_overview_extra(selected_areas: Optional[List[str]] = None):
    """Fetch Oracle ISO/FS live status counts. Returns (kpi_extra, matrix_rows)."""
    kpi_extra = {
        'waiting': 0, 'on_process': 0, 'down': 0,
        'closed_shift': 0, 'machines': 0,
    }
    matrix_rows = []
    try:
        from config import ORA_ENABLED
        if not ORA_ENABLED:
            return kpi_extra, matrix_rows

        from oracle_db import fetch_oracle_live_status
        ora_df = fetch_oracle_live_status()
        if ora_df is None or ora_df.empty:
            return kpi_extra, matrix_rows

        if selected_areas:
            ora_df = ora_df[ora_df['area'].isin(selected_areas)]

        if ora_df.empty:
            return kpi_extra, matrix_rows

        kpi_extra['machines'] = int(ora_df['code_machine'].nunique())
        kpi_extra['waiting'] = int((ora_df['status'] == 'Waiting').sum())
        kpi_extra['on_process'] = int((ora_df['status'] == 'On Process').sum())
        kpi_extra['down'] = int((ora_df['job_type'] == 'M/C DOWN').sum())
    except Exception as e:
        log.warning(f"Oracle overview fetch failed: {e}")

    return kpi_extra, matrix_rows


def get_open_jobs(selected_areas: Optional[List[str]] = None,
                  job_type_filter: Optional[str] = None) -> dict:
    """Currently open jobs (Waiting + On Process) — SQL + Oracle merged."""
    from db import query_df
    from utils.queries import overview_open_jobs, ORACLE_ONLY_AREAS
    import pandas as pd

    open_df = query_df(overview_open_jobs())
    if not open_df.empty:
        open_df['source'] = 'sql'

    if selected_areas:
        open_df = open_df[open_df['area'].isin(selected_areas)]

    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_live_status
            ora_live = fetch_oracle_live_status(selected_areas)
            if ora_live is not None and not ora_live.empty:
                ora_open = ora_live[ora_live['status'] != 'Closed'].copy()
                if not ora_open.empty:
                    ora_open['source'] = 'oracle'
                    open_df = pd.concat([open_df, ora_open], ignore_index=True)
    except Exception as e:
        log.warning(f"Oracle open jobs merge failed: {e}")

    if job_type_filter and job_type_filter != 'ALL':
        open_df = open_df[open_df['job_type'] == job_type_filter]

    def _null_safe(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    def _opt_int(v):
        v = _null_safe(v)
        return int(v) if v is not None else None

    def _opt_str(v):
        v = _null_safe(v)
        return str(v) if v is not None and str(v).strip() != '' else None

    jobs = []
    for _, r in open_df.iterrows():
        jobs.append({
            'code_machine': str(r.get('code_machine') or ''),
            'area': _opt_str(r.get('area')),
            'job_type': str(r.get('job_type') or ''),
            'des_job': _opt_str(r.get('des_job')),
            'datex': _null_safe(r.get('datex')),
            'date_ack': _null_safe(r.get('date_ack')),
            'tech': _opt_str(r.get('tech')),
            'wait_min': _opt_int(r.get('wait_min')),
            'repair_min': _opt_int(r.get('repair_min')),
            'status': str(r.get('status') or ''),
            'die_mask': _opt_str(r.get('die_mask')),
            'die_size': _opt_str(r.get('die_size')),
            'package_type': _opt_str(r.get('package_type')),
            'wire_type': _opt_str(r.get('wire_type')),
            'source': str(r.get('source') or 'sql'),
        })
    return {'jobs': jobs, 'total': len(jobs)}


def get_overview(selected_areas: Optional[List[str]] = None) -> dict:
    """Unified overview: KPI + status matrix across SQL Server + Oracle.

    Returns a dict ready for the OverviewData schema.
    """
    from datetime import datetime

    matrix_df, kpi_df = _sql_overview(selected_areas)
    ora_extra, _ = _oracle_overview_extra(selected_areas)

    row = kpi_df.iloc[0] if not kpi_df.empty else {}
    total_machines = int(row.get('total_key_machines', 0) or 0) + ora_extra['machines']
    waiting = int(row.get('waiting_count', 0) or 0) + ora_extra['waiting']
    on_process = int(row.get('on_process_count', 0) or 0) + ora_extra['on_process']
    down = int(row.get('down_count', 0) or 0) + ora_extra['down']
    closed_shift = int(row.get('closed_this_shift', 0) or 0) + ora_extra['closed_shift']
    running = max(0, total_machines - waiting - on_process - down)

    status_matrix = []
    if not matrix_df.empty:
        for _, r in matrix_df.iterrows():
            status_matrix.append({
                'job_type': str(r.get('job_type') or ''),
                'waiting': int(r.get('waiting', 0) or 0),
                'on_process': int(r.get('on_process', 0) or 0),
                'closed': int(r.get('closed', 0) or 0),
                'total': int(r.get('total', 0) or 0),
            })

    return {
        'kpi': {
            'total_machines': total_machines,
            'running': running,
            'down': down,
            'waiting': waiting,
            'on_process': on_process,
            'closed_this_shift': closed_shift,
        },
        'status_matrix': status_matrix,
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }
