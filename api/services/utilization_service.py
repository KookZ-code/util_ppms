"""Utilization service — % util / downtime / lost time per area.

Mirrors dashboard/pages/utilization.py aggregation logic.
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd

log = logging.getLogger(__name__)

# Job type categorization (matches dashboard pages/utilization.py)
DOWNTIME_JOB_TYPES = ['M/C DOWN', 'PM']
DOWN_TYPES = ('M/C DOWN',)
PM_TYPES = ('PM',)
LOST_TYPES = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD',
              'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN')
LOST_TIME_JOB_TYPES = list(LOST_TYPES)


def _calc_time_composition(merged_df: pd.DataFrame) -> tuple:
    """Return (downtime_min, lost_time_min, all_min) from job-type totals."""
    if merged_df.empty:
        return 0, 0, 0
    merged_df = merged_df.copy()
    merged_df['total_min'] = merged_df['total_min'].fillna(0).astype(float)
    merged_df['wait_min'] = merged_df['wait_min'].fillna(0).astype(float)

    down_mask = merged_df['job_type'].isin(DOWNTIME_JOB_TYPES)
    lost_mask = merged_df['job_type'].isin(LOST_TIME_JOB_TYPES)

    downtime_min = merged_df.loc[down_mask, 'total_min'].sum()
    lost_time_min = (merged_df.loc[lost_mask, 'total_min'].sum()
                     + merged_df['wait_min'].sum())
    all_min = merged_df['total_min'].sum() + merged_df['wait_min'].sum()
    return float(downtime_min), float(lost_time_min), float(all_min)


def _calc_util_pct(machines: int, downtime_min: float, lost_min: float,
                   start: str, end: str) -> tuple:
    """% utilization given period length and machine count.

    Returns (util_pct, downtime_pct, lost_pct).
    """
    if machines <= 0:
        return 0.0, 0.0, 0.0
    # Period length in minutes
    try:
        s = pd.Timestamp(start)
        e = pd.Timestamp(end) + pd.Timedelta(days=1)
        period_min = (e - s).total_seconds() / 60.0
    except Exception:
        period_min = 24 * 60
    total_available = machines * period_min
    if total_available <= 0:
        return 0.0, 0.0, 0.0
    down_pct = (downtime_min / total_available) * 100
    lost_pct = (lost_min / total_available) * 100
    util_pct = max(0.0, 100.0 - down_pct - lost_pct)
    return round(util_pct, 2), round(down_pct, 2), round(lost_pct, 2)


def _df_to_records(df: pd.DataFrame) -> list:
    """DataFrame → list of plain dicts, NaN→None, numpy types → python."""
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
            elif hasattr(v, 'item'):  # numpy scalar
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


def get_utilization_detail(
    start_date: str,
    end_date: str,
    areas: Optional[List[str]] = None,
    shift: Optional[str] = None,
    selected_month: Optional[str] = None,
) -> dict:
    """Comprehensive utilization payload for the primary dashboard callback.

    Returns kpi + by_area + monthly_trend + prev_period_kpi + scatter
    + top_down + top_lost + machines_per_cause — all SQL + Oracle merged.
    """
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import (
        build_util_where, util_kpi_totals, util_monthly_composition,
        util_by_area, util_total_machine_count, util_machine_count,
        util_freq_vs_duration, util_top_machines_per_cause,
    )

    tc = COLUMN_MAP.get('tech_start_time') or 'datex'
    otc = COLUMN_MAP.get('opr_start_time') or 'datex'
    ec = COLUMN_MAP.get('end_time') or 'date_close'
    sc = COLUMN_MAP.get('status') or 'job_type'
    ac = COLUMN_MAP.get('machine_area') or 'id_operation'
    mid = COLUMN_MAP.get('machine_id') or 'code_machine'
    sym = COLUMN_MAP.get('symptom', 'des_job') or 'des_job'
    rc_col = COLUMN_MAP.get('downtime_reason', 'cause') or 'cause'

    # Full-range WHERE (KPI + monthly trend + machine counts)
    where, params = build_util_where(otc, ec, ac, start_date, end_date, areas, shift)

    # Month-filtered WHERE (scatter, by_area, top causes — if month selected)
    if selected_month:
        from calendar import monthrange
        yr, mo = int(selected_month[:4]), int(selected_month[5:7])
        ms = f"{yr}-{mo:02d}-01"
        me = f"{yr}-{mo:02d}-{monthrange(yr, mo)[1]}"
        where_m, params_m = build_util_where(otc, ec, ac, ms, me, areas, shift)
    else:
        where_m, params_m = where, params

    # ── SQL Server queries ────────────────────────────────────────────────────
    kpi_df = query_df(util_kpi_totals(VIEW_NAME, tc, ec, sc, where), params)
    trend_df = query_df(util_monthly_composition(VIEW_NAME, otc, tc, ec, sc, where), params)
    area_df = query_df(util_by_area(VIEW_NAME, tc, ec, sc, ac, where_m), params_m)
    cnt_df = query_df(util_total_machine_count(VIEW_NAME, mid, where), params)
    area_cnt_df = query_df(util_machine_count(VIEW_NAME, ac, mid, where), params)
    scatter_df = query_df(
        util_freq_vs_duration(VIEW_NAME, tc, ec, sc, ac, mid, where_m), params_m)

    down_in = ', '.join(f"'{t}'" for t in DOWN_TYPES)
    lost_in = ', '.join(f"'{t}'" for t in LOST_TYPES)
    top_down_df = query_df(f"""
        SELECT TOP 5 [{sym}] AS cause,
               SUM(DATEDIFF(MINUTE, [{tc}], [{ec}])) / 60.0 AS hours
        FROM {VIEW_NAME} {where_m}
        AND [{sc}] IN ({down_in})
        AND [{sym}] IS NOT NULL AND [{sym}] != ''
        GROUP BY [{sym}] ORDER BY hours DESC
    """, params_m)
    top_lost_df = query_df(f"""
        SELECT TOP 5 [{rc_col}] AS cause,
               SUM(DATEDIFF(MINUTE, [{tc}], [{ec}])) / 60.0
               + SUM(ISNULL(Waiting_time, 0)) / 60.0 AS hours
        FROM {VIEW_NAME} {where_m}
        AND [{sc}] IN ({lost_in})
        AND [{rc_col}] IS NOT NULL AND [{rc_col}] != ''
        GROUP BY [{rc_col}] ORDER BY hours DESC
    """, params_m)
    mach_per_cause_df = query_df(
        util_top_machines_per_cause(VIEW_NAME, tc, ec, sc, sym, mid, where_m, down_in),
        params_m)

    # ── Oracle merge ──────────────────────────────────────────────────────────
    ora_df = None
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            if not areas or any(a in ('ISO', 'FS') for a in areas):
                ora_df = fetch_oracle_data(start_date, end_date, areas, shift)
    except Exception as e:
        log.warning(f"Oracle fetch failed: {e}")
        ora_df = None

    if ora_df is not None:
        from utils.oracle_agg import (
            ora_kpi_totals, ora_monthly, ora_by_area,
            ora_machine_count, ora_total_machine_count,
            ora_freq_vs_duration, ora_top_symptoms,
            ora_top_lost_causes, ora_machines_per_cause,
        )
        # Full range
        kpi_df = pd.concat([kpi_df, ora_kpi_totals(ora_df)], ignore_index=True)
        trend_df = pd.concat([trend_df, ora_monthly(ora_df)], ignore_index=True)
        ora_cnt = ora_total_machine_count(ora_df)
        if not ora_cnt.empty and not cnt_df.empty:
            cnt_df['machine_count'] = (int(cnt_df['machine_count'].iloc[0])
                                       + int(ora_cnt['machine_count'].iloc[0]))
        elif not ora_cnt.empty:
            cnt_df = ora_cnt

        # Month-filtered
        if selected_month:
            ora_m = ora_df[ora_df['datex'].dt.strftime('%Y-%m') == selected_month]
            ora_m = ora_m if not ora_m.empty else None
        else:
            ora_m = ora_df

        if ora_m is not None:
            area_df = pd.concat([area_df, ora_by_area(ora_m)], ignore_index=True)
            area_cnt_df = pd.concat(
                [area_cnt_df, ora_machine_count(ora_m)], ignore_index=True)
            scatter_df = pd.concat(
                [scatter_df, ora_freq_vs_duration(ora_m)], ignore_index=True)
            o_td = ora_top_symptoms(ora_m)
            if not o_td.empty:
                top_down_df = pd.concat([top_down_df, o_td], ignore_index=True)
                top_down_df = (top_down_df.groupby('cause')['hours'].sum()
                               .reset_index().nlargest(5, 'hours'))
            o_tl = ora_top_lost_causes(ora_m, list(LOST_TYPES))
            if not o_tl.empty:
                top_lost_df = pd.concat([top_lost_df, o_tl], ignore_index=True)
                top_lost_df = (top_lost_df.groupby('cause')['hours'].sum()
                               .reset_index().nlargest(5, 'hours'))
            o_mpc = ora_machines_per_cause(ora_m)
            if not o_mpc.empty:
                mach_per_cause_df = pd.concat(
                    [mach_per_cause_df, o_mpc], ignore_index=True)

    # ── Merge area counts (sum machine_count per area) ────────────────────────
    if not area_cnt_df.empty:
        area_cnt_df = area_cnt_df.groupby('area', as_index=False).agg(
            machine_count=('machine_count', 'sum'))

    # ── Previous period KPI ───────────────────────────────────────────────────
    from datetime import datetime as _dt, timedelta as _td
    prev_df = pd.DataFrame()
    prev_cnt_total = 0
    prev_start, prev_end = None, None
    try:
        if selected_month:
            from calendar import monthrange as _mr3
            _yr, _mo = int(selected_month[:4]), int(selected_month[5:7])
            if _mo == 1:
                p_yr, p_mo = _yr - 1, 12
            else:
                p_yr, p_mo = _yr, _mo - 1
            prev_start = f"{p_yr}-{p_mo:02d}-01"
            prev_end = f"{p_yr}-{p_mo:02d}-{_mr3(p_yr, p_mo)[1]}"
        else:
            d0 = _dt.strptime(str(start_date)[:10], '%Y-%m-%d')
            d1 = _dt.strptime(str(end_date)[:10], '%Y-%m-%d')
            n_days = (d1 - d0).days + 1
            prev_start = (d0 - _td(days=n_days)).strftime('%Y-%m-%d')
            prev_end = (d0 - _td(days=1)).strftime('%Y-%m-%d')

        p_where, p_params = build_util_where(otc, ec, ac, prev_start, prev_end, areas, shift)
        prev_df = query_df(util_kpi_totals(VIEW_NAME, tc, ec, sc, p_where), p_params)
        p_cnt_df = query_df(util_total_machine_count(VIEW_NAME, mid, p_where), p_params)
        prev_cnt_total = int(p_cnt_df['machine_count'].iloc[0]) if not p_cnt_df.empty else 0

        # Oracle prev period
        try:
            from config import ORA_ENABLED as _OE
            if _OE:
                from oracle_db import fetch_oracle_data as _ofd
                from utils.oracle_agg import (ora_kpi_totals as _okt,
                                              ora_total_machine_count as _otmc)
                if not areas or any(a in ('ISO', 'FS') for a in areas):
                    p_ora = _ofd(prev_start, prev_end, areas, shift)
                    if p_ora is not None:
                        prev_df = pd.concat([prev_df, _okt(p_ora)], ignore_index=True)
                        p_ora_cnt = _otmc(p_ora)
                        if not p_ora_cnt.empty:
                            prev_cnt_total += int(p_ora_cnt['machine_count'].iloc[0])
        except Exception:
            pass
    except Exception as e:
        log.warning(f"Prev period calc failed: {e}")

    # ── Shape output ──────────────────────────────────────────────────────────
    total_machines = int(cnt_df['machine_count'].iloc[0]) if not cnt_df.empty else 0
    down_min, lost_min, _ = _calc_time_composition(kpi_df)
    util_pct, down_pct, lost_pct = _calc_util_pct(
        total_machines, down_min, lost_min, start_date, end_date)

    # Previous period %
    prev_util_pct, prev_down_pct, prev_lost_pct = 0.0, 0.0, 0.0
    if not prev_df.empty and prev_start and prev_end:
        p_down, p_lost, _ = _calc_time_composition(prev_df)
        prev_util_pct, prev_down_pct, prev_lost_pct = _calc_util_pct(
            prev_cnt_total, p_down, p_lost, prev_start, prev_end)

    # By-area
    by_area = []
    from config import AREA_TARGETS
    if not area_cnt_df.empty:
        for _, row in area_cnt_df.iterrows():
            area = row['area']
            a_df = area_df[area_df['area'] == area] if not area_df.empty else pd.DataFrame()
            a_down, a_lost, _ = _calc_time_composition(a_df)
            a_util, a_dp, a_lp = _calc_util_pct(
                int(row['machine_count']), a_down, a_lost,
                (selected_month + '-01') if selected_month else start_date,
                (selected_month + '-28') if selected_month else end_date)
            by_area.append({
                'area': area, 'machines': int(row['machine_count']),
                'utilization_pct': a_util, 'downtime_pct': a_dp,
                'lost_time_pct': a_lp, 'target_pct': AREA_TARGETS.get(area),
            })
    by_area.sort(key=lambda x: x['area'])

    return {
        'kpi': {
            'utilization_pct': util_pct,
            'downtime_pct': down_pct,
            'lost_time_pct': lost_pct,
            'total_machines': total_machines,
            'total_hours': round((down_min + lost_min) / 60.0, 1),
            'downtime_hours': round(down_min / 60.0, 1),
            'lost_time_hours': round(lost_min / 60.0, 1),
        },
        'prev_kpi': {
            'utilization_pct': prev_util_pct,
            'downtime_pct': prev_down_pct,
            'lost_time_pct': prev_lost_pct,
            'period_start': prev_start, 'period_end': prev_end,
        },
        'by_area': by_area,
        'monthly_trend': _df_to_records(trend_df),
        'scatter': _df_to_records(scatter_df),
        'top_down': _df_to_records(top_down_df),
        'top_lost': _df_to_records(top_lost_df),
        'machines_per_cause': _df_to_records(mach_per_cause_df),
        # Raw aggregated tables for the dashboard's internal recomputation
        'raw': {
            'kpi_totals': _df_to_records(kpi_df),         # job_type, total_min, wait_min
            'area_totals': _df_to_records(area_df),       # area, job_type, total_min, wait_min
            'area_counts': _df_to_records(area_cnt_df),   # area, machine_count
            'machine_count': total_machines,              # scalar
            'prev_kpi_totals': _df_to_records(prev_df),   # job_type, total_min, wait_min
            'prev_machine_count': prev_cnt_total,
        },
        'period': {
            'start': start_date, 'end': end_date,
            'shift': shift or 'ALL',
            'selected_month': selected_month,
        },
    }


def get_by_machine(
    start_date: str, end_date: str,
    areas: Optional[List[str]] = None, shift: Optional[str] = None,
) -> dict:
    """Per-machine breakdown (second utilization callback)."""
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import build_util_where, util_by_machine

    tc = COLUMN_MAP.get('tech_start_time') or 'datex'
    otc = COLUMN_MAP.get('opr_start_time') or 'datex'
    ec = COLUMN_MAP.get('end_time') or 'date_close'
    sc = COLUMN_MAP.get('status') or 'job_type'
    ac = COLUMN_MAP.get('machine_area') or 'id_operation'
    mid = COLUMN_MAP.get('machine_id') or 'code_machine'

    where, params = build_util_where(otc, ec, ac, start_date, end_date, areas, shift)
    df = query_df(util_by_machine(VIEW_NAME, tc, ec, sc, ac, mid, where), params)
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import ora_by_machine
            if not areas or any(a in ('ISO', 'FS') for a in areas):
                ora = fetch_oracle_data(start_date, end_date, areas, shift)
                if ora is not None:
                    df = pd.concat([df, ora_by_machine(ora)], ignore_index=True)
    except Exception as e:
        log.warning(f"Oracle by_machine failed: {e}")

    return {'rows': _df_to_records(df), 'total': int(len(df))}


def get_attention_machines(
    start_date: str, end_date: str,
    areas: Optional[List[str]] = None, shift: Optional[str] = None,
) -> dict:
    """Top machines needing attention (third utilization callback)."""
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP
    from utils.queries import build_util_where, util_attention_machines

    tc = COLUMN_MAP.get('tech_start_time') or 'datex'
    otc = COLUMN_MAP.get('opr_start_time') or 'datex'
    ec = COLUMN_MAP.get('end_time') or 'date_close'
    sc = COLUMN_MAP.get('status') or 'job_type'
    ac = COLUMN_MAP.get('machine_area') or 'id_operation'
    mid = COLUMN_MAP.get('machine_id') or 'code_machine'

    where, params = build_util_where(otc, ec, ac, start_date, end_date, areas, shift)
    df = query_df(util_attention_machines(
        VIEW_NAME, otc, tc, ec, sc, ac, mid, where), params)
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import ora_attention_machines
            if not areas or any(a in ('ISO', 'FS') for a in areas):
                ora = fetch_oracle_data(start_date, end_date, areas, shift)
                if ora is not None:
                    o = ora_attention_machines(ora)
                    if not o.empty:
                        df = pd.concat([df, o], ignore_index=True)
                        df = df.nlargest(10, 'score')
    except Exception as e:
        log.warning(f"Oracle attention failed: {e}")

    return {'rows': _df_to_records(df), 'total': int(len(df))}


def get_utilization(
    start_date: str,
    end_date: str,
    areas: Optional[List[str]] = None,
    shift: Optional[str] = None,
) -> dict:
    """Return utilization KPI + per-area breakdown.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD' (inclusive)
        areas:      ['WB', 'DA', ...] or None
        shift:      'DAY' | 'NIGHT' | None
    """
    from db import query_df
    from config import VIEW_NAME, COLUMN_MAP, AREA_TARGETS
    from utils.queries import (
        build_util_where, util_kpi_totals, util_by_area,
        util_machine_count, util_total_machine_count,
    )

    tc = COLUMN_MAP.get('tech_start_time') or 'datex'
    ec = COLUMN_MAP.get('end_time') or 'date_close'
    sc = COLUMN_MAP.get('status') or 'job_type'
    ac = COLUMN_MAP.get('machine_area') or 'id_operation'
    mid = COLUMN_MAP.get('machine_id') or 'code_machine'

    where, params = build_util_where(tc, ec, ac, start_date, end_date, areas, shift)

    sql_kpi = query_df(util_kpi_totals(VIEW_NAME, tc, ec, sc, where), params)
    sql_area = query_df(util_by_area(VIEW_NAME, tc, ec, sc, ac, where), params)
    sql_mc_by_area = query_df(util_machine_count(VIEW_NAME, ac, mid, where), params)
    sql_mc_total = query_df(util_total_machine_count(VIEW_NAME, mid, where), params)

    # Oracle side
    ora_kpi = pd.DataFrame(columns=['job_type', 'total_min', 'wait_min'])
    ora_area = pd.DataFrame(columns=['area', 'job_type', 'total_min', 'wait_min'])
    ora_mc_by_area = pd.DataFrame(columns=['area', 'machine_count'])
    ora_mc_total = 0
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import (
                ora_kpi_totals, ora_by_area,
                ora_machine_count, ora_total_machine_count,
            )
            ora_df = fetch_oracle_data(start_date, end_date, areas, shift)
            if ora_df is not None and not ora_df.empty:
                ora_kpi = ora_kpi_totals(ora_df)
                ora_area = ora_by_area(ora_df)
                ora_mc_by_area = ora_machine_count(ora_df)
                tot = ora_total_machine_count(ora_df)
                ora_mc_total = int(tot['machine_count'].iloc[0]) if not tot.empty else 0
    except Exception as e:
        log.warning(f"Oracle utilization fetch failed: {e}")

    merged_kpi = pd.concat([sql_kpi, ora_kpi], ignore_index=True)
    if not merged_kpi.empty:
        merged_kpi = merged_kpi.groupby('job_type', as_index=False).agg(
            total_min=('total_min', 'sum'),
            wait_min=('wait_min', 'sum'),
        )

    total_machines = int(
        (sql_mc_total['machine_count'].iloc[0] if not sql_mc_total.empty else 0)
    ) + ora_mc_total

    downtime_min, lost_min, all_min = _calc_time_composition(merged_kpi)
    util_pct, down_pct, lost_pct = _calc_util_pct(
        total_machines, downtime_min, lost_min, start_date, end_date
    )

    # Per-area breakdown
    merged_area = pd.concat([sql_area, ora_area], ignore_index=True)
    merged_mc = pd.concat([sql_mc_by_area, ora_mc_by_area], ignore_index=True)
    if not merged_mc.empty:
        merged_mc = merged_mc.groupby('area', as_index=False).agg(
            machine_count=('machine_count', 'sum'),
        )

    by_area = []
    if not merged_mc.empty:
        for _, row in merged_mc.iterrows():
            area = row['area']
            area_df = merged_area[merged_area['area'] == area] if not merged_area.empty else pd.DataFrame()
            a_down, a_lost, _ = _calc_time_composition(area_df)
            a_util, a_dp, a_lp = _calc_util_pct(
                int(row['machine_count']), a_down, a_lost, start_date, end_date
            )
            by_area.append({
                'area': area,
                'machines': int(row['machine_count']),
                'utilization_pct': a_util,
                'downtime_pct': a_dp,
                'lost_time_pct': a_lp,
                'target_pct': AREA_TARGETS.get(area),
            })
    by_area.sort(key=lambda x: x['area'])

    return {
        'kpi': {
            'utilization_pct': util_pct,
            'downtime_pct': down_pct,
            'lost_time_pct': lost_pct,
            'total_machines': total_machines,
            'total_hours': round(all_min / 60.0, 1),
            'downtime_hours': round(downtime_min / 60.0, 1),
            'lost_time_hours': round(lost_min / 60.0, 1),
        },
        'by_area': by_area,
        'period': {
            'start': start_date,
            'end': end_date,
            'shift': shift or 'ALL',
        },
    }
