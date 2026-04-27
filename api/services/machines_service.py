"""Machines service — master list + detail."""
import logging
from typing import Optional, List
import pandas as pd

log = logging.getLogger(__name__)


def get_machines(area: Optional[str] = None, key_only: bool = False) -> dict:
    """Return machine master list from dbo.machine."""
    from db import query_df
    from config import MACHINE_TABLE

    clauses = ["[id_operation] IS NOT NULL", "[id_operation] != ''",
               "ISNULL([flag_delete], 0) != 1"]
    params = {}
    if area:
        clauses.append("[id_operation] = :area")
        params['area'] = area
    if key_only:
        clauses.append("[flag_key] = 1")
    where = "WHERE " + " AND ".join(clauses)

    sql = f"""
        SELECT [code_machine] AS machine_id, [des_machine],
               [mfg], [model], [sn],
               [id_operation] AS area, [short_name] AS area_name,
               ISNULL([flag_key], 0) AS flag_key,
               ISNULL([flag_automotive], 0) AS flag_automotive,
               ISNULL([flag_gold], 0) AS flag_gold
        FROM {MACHINE_TABLE}
        {where}
        ORDER BY [id_operation], [code_machine]
    """
    df = query_df(sql, params)

    machines = []
    for _, r in df.iterrows():
        machines.append({
            'machine_id': str(r['machine_id'] or '').strip(),
            'des_machine': str(r.get('des_machine') or '') or None,
            'area': str(r.get('area') or '') or None,
            'area_name': str(r.get('area_name') or '') or None,
            'mfg': str(r.get('mfg') or '') or None,
            'model': str(r.get('model') or '') or None,
            'sn': str(r.get('sn') or '') or None,
            'short_name': str(r.get('area_name') or '') or None,
            'flag_key': int(r.get('flag_key') or 0),
            'flag_automotive': int(r.get('flag_automotive') or 0),
            'flag_gold': int(r.get('flag_gold') or 0),
        })
    return {'machines': machines, 'total': len(machines)}


def get_machine_detail(machine_id: str, recent_limit: int = 20) -> Optional[dict]:
    """Machine master info + recent events + downtime KPIs."""
    from db import query_df
    from utils.queries import machine_master_info, machine_downtime_kpis

    info_df = query_df(machine_master_info(), {'machine_id': machine_id.strip()})
    if info_df.empty:
        return None
    info = info_df.iloc[0].to_dict()

    kpi_df = query_df(machine_downtime_kpis(), {'machine_id': machine_id.strip()})
    kpi = kpi_df.iloc[0].to_dict() if not kpi_df.empty else {}

    from config import VIEW_NAME, COLUMN_MAP
    sym = COLUMN_MAP.get('symptom', 'des_job') or 'des_job'
    otc = COLUMN_MAP.get('opr_start_time', 'datex') or 'datex'
    ttc = COLUMN_MAP.get('tech_start_time', 'date_ack') or 'date_ack'
    ec  = COLUMN_MAP.get('end_time', 'date_close') or 'date_close'
    mid = COLUMN_MAP.get('machine_id', 'code_machine') or 'code_machine'

    events_df = query_df(f"""
        SELECT TOP {int(recent_limit)}
               job_type, [{sym}] AS symptom,
               [{otc}] AS opr_start, [{ec}] AS end_time,
               ISNULL(Waiting_time, 0) AS wait_min,
               DATEDIFF(MINUTE, [{ttc}], [{ec}]) AS repair_min,
               ISNULL(by_perform, by_ack) AS technician
        FROM {VIEW_NAME}
        WHERE [{mid}] = :machine_id
          AND [{ec}] IS NOT NULL
          AND [{ttc}] IS NOT NULL
        ORDER BY [{otc}] DESC
    """, {'machine_id': machine_id.strip()})

    recent = []
    for _, r in events_df.iterrows():
        recent.append({
            'job_type': str(r.get('job_type') or ''),
            'symptom': str(r.get('symptom') or '') or None,
            'opr_start': r.get('opr_start'),
            'end_time': r.get('end_time'),
            'wait_min': int(r.get('wait_min') or 0),
            'repair_min': int(r.get('repair_min') or 0),
            'technician': str(r.get('technician') or '') or None,
        })

    def _none_if_nan(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return v

    return {
        'info': {
            'machine_id': str(info.get('code_machine', '') or '').strip(),
            'des_machine': _none_if_nan(info.get('des_machine')),
            'area': _none_if_nan(info.get('id_operation')),
            'area_name': _none_if_nan(info.get('short_name')),
            'mfg': _none_if_nan(info.get('mfg')),
            'model': _none_if_nan(info.get('model')),
            'sn': _none_if_nan(info.get('sn')),
            'short_name': _none_if_nan(info.get('short_name')),
            'flag_key': int(info.get('flag_key') or 0),
            'flag_automotive': int(info.get('flag_automotive') or 0),
            'flag_gold': int(info.get('flag_gold') or 0),
        },
        'date_install': _none_if_nan(info.get('date_install')),
        'flags': {
            'key': int(info.get('flag_key') or 0),
            'automotive': int(info.get('flag_automotive') or 0),
            'gold': int(info.get('flag_gold') or 0),
            'downtime': int(info.get('flag_downtime') or 0),
            'pm': int(info.get('flag_pm') or 0),
        },
        'kpis': {
            'total_events': int(kpi.get('total_events') or 0),
            'down_events': int(kpi.get('down_events') or 0),
            'avg_mttr_min': float(kpi['avg_mttr_min']) if kpi.get('avg_mttr_min') is not None and not pd.isna(kpi.get('avg_mttr_min')) else None,
            'avg_wait_min': float(kpi['avg_wait_min']) if kpi.get('avg_wait_min') is not None and not pd.isna(kpi.get('avg_wait_min')) else None,
            'total_down_hrs': float(kpi['total_down_hrs']) if kpi.get('total_down_hrs') is not None and not pd.isna(kpi.get('total_down_hrs')) else None,
        },
        'recent_events': recent,
    }
