"""Daily morning meeting summary — sent 07:30 daily.

Covers entire plant: BSDA, WB, MOLD, PLATE, EOL, SAW_QFN.
Includes Hard Down, Long-term down, Focus Packages, Utilization per area.
"""
import os
import logging
from datetime import datetime, timedelta
import pandas as pd

log = logging.getLogger(__name__)

# Area groups (reuse same structure as shift_email)
AREA_GROUPS = {
    'BSDA': ['BG', 'SAW', 'DA'],
    'WB':   ['WB'],
    'MOLD': ['MOLD'],
    'PLATE': ['PLATE'],
    'EOL':  ['MARK', 'TF', 'ISO', 'FS'],
    'SAW_QFN': ['SAW_QFN'],
}
AREA_NAMES = {
    'BG': 'Back Grind', 'SAW': 'SAW', 'DA': 'Die Attach',
    'WB': 'Wire Bond', 'MOLD': 'Mold', 'PLATE': 'Plating',
    'MARK': 'Marking', 'TF': 'Trim Form', 'ISO': 'Isolate',
    'FS': 'Form Singulation', 'SAW_QFN': 'SAW QFN',
}

# Group → TechnicianList AERA code
GROUP_TO_AERA = {
    'BSDA':    'A0005',
    'WB':      'A0001',
    'MOLD':    'A0004',
    'PLATE':   'A0002',
    'EOL':     'A0003',
    'SAW_QFN': 'A0003',
}

HARD_DOWN_THRESHOLD_MIN = 60  # events > 60min repair = hard down
LONG_TERM_DAYS = 3            # open jobs > 3 days = long-term down
LONG_TERM_MAX_DAYS = 90       # cap — ignore very old stale records


def _query_hard_down(start, end):
    """Query machines with long downtime events in the past 24h."""
    from db import query_df
    from config import VIEW_NAME
    df = query_df(f"""
        SELECT code_machine AS machine_id, id_operation AS area,
               des_job AS symptom, cause, [action],
               datex AS event_time, date_ack, date_close,
               ISNULL(by_perform, by_ack) AS tech,
               DATEDIFF(MINUTE, date_ack, COALESCE(date_close, GETDATE())) AS repair_min,
               [Package Type] AS package_type,
               CASE WHEN date_close IS NULL THEN 'Still Down' ELSE 'Resolved' END AS status
        FROM {VIEW_NAME}
        WHERE job_type = 'M/C DOWN'
          AND datex >= :start_dt AND datex <= :end_dt
          AND date_ack IS NOT NULL
          AND (DATEDIFF(MINUTE, date_ack, COALESCE(date_close, GETDATE())) > :threshold
               OR date_close IS NULL)
        ORDER BY repair_min DESC
    """, {'start_dt': start, 'end_dt': end, 'threshold': HARD_DOWN_THRESHOLD_MIN})
    return df


def _query_long_term_down():
    """Machines with open jobs 3–90 days old (exclude stale records >90d)."""
    from db import query_df
    from config import VIEW_NAME
    now = datetime.now()
    cutoff_max = now - timedelta(days=LONG_TERM_DAYS)        # must be at least 3 days old
    cutoff_min = now - timedelta(days=LONG_TERM_MAX_DAYS)    # but not older than 90 days
    df = query_df(f"""
        SELECT code_machine AS machine_id, id_operation AS area,
               des_job AS symptom, cause, [action],
               datex AS opened_date,
               DATEDIFF(DAY, datex, GETDATE()) AS days_down,
               [Package Type] AS package_type
        FROM {VIEW_NAME}
        WHERE date_close IS NULL
          AND job_type = 'M/C DOWN'
          AND datex < :cutoff_max
          AND datex > :cutoff_min
        ORDER BY days_down DESC
    """, {'cutoff_max': cutoff_max, 'cutoff_min': cutoff_min})
    # Group by machine_id (collapse duplicates)
    if not df.empty:
        df = df.sort_values('days_down', ascending=False).drop_duplicates('machine_id', keep='first')
    return df


def _query_tech_count(aera_code, start=None, end=None):
    """Count technicians per AERA code, split by Group with active counts.
    Returns: {'total', 'active', 'Day': {reg, active}, 'Shift-1': ..., 'Shift-2': ...}
    """
    from db import query_df
    empty = {'total': 0, 'active': 0,
             'Day': {'reg': 0, 'active': 0},
             'Shift-1': {'reg': 0, 'active': 0},
             'Shift-2': {'reg': 0, 'active': 0}}
    if not aera_code:
        return empty

    # Registered per group
    df = query_df(
        "SELECT [Group], COUNT(*) AS cnt FROM [dbo].[TechnicianList] "
        "WHERE AERA = :aera GROUP BY [Group]",
        {'aera': aera_code})
    result = {'Day': {'reg': 0, 'active': 0},
              'Shift-1': {'reg': 0, 'active': 0},
              'Shift-2': {'reg': 0, 'active': 0}}
    for _, r in df.iterrows():
        g = r['Group']
        if g in result:
            result[g]['reg'] = int(r['cnt'])
    result['total'] = sum(result[g]['reg'] for g in ('Day', 'Shift-1', 'Shift-2'))

    # Active techs per group in time range
    result['active'] = 0
    if start and end:
        try:
            from config import VIEW_NAME
            act_df = query_df(f"""
                SELECT t.[Group],
                       COUNT(DISTINCT ISNULL(j.by_perform, j.by_ack)) AS cnt
                FROM {VIEW_NAME} j
                JOIN [dbo].[TechnicianList] t
                  ON ISNULL(j.by_perform, j.by_ack) = t.Badge
                WHERE t.AERA = :aera
                  AND j.datex >= :start_dt AND j.datex <= :end_dt
                  AND j.date_ack IS NOT NULL
                GROUP BY t.[Group]
            """, {'aera': aera_code, 'start_dt': start, 'end_dt': end})
            for _, r in act_df.iterrows():
                g = r['Group']
                if g in result:
                    result[g]['active'] = int(r['cnt'])
            result['active'] = sum(result[g]['active'] for g in ('Day', 'Shift-1', 'Shift-2'))
        except Exception:
            pass
    return result


def _query_tech_count_OLD(aera_code, start=None, end=None):
    """(deprecated) Old implementation kept for reference."""
    from db import query_df
    if not aera_code:
        return {'total': 0, 'Day': 0, 'Shift-1': 0, 'Shift-2': 0, 'active': 0}
    df = query_df(
        "SELECT [Group], COUNT(*) AS cnt FROM [dbo].[TechnicianList] "
        "WHERE AERA = :aera GROUP BY [Group]",
        {'aera': aera_code})
    result = {'Day': 0, 'Shift-1': 0, 'Shift-2': 0}
    for _, r in df.iterrows():
        result[r['Group']] = int(r['cnt'])
    result['total'] = sum(result.values())
    result['active'] = 0
    if start and end:
        try:
            from config import VIEW_NAME
            active_df = query_df(f"""
                SELECT COUNT(DISTINCT ISNULL(j.by_perform, j.by_ack)) AS cnt
                FROM {VIEW_NAME} j
                JOIN [dbo].[TechnicianList] t
                  ON ISNULL(j.by_perform, j.by_ack) = t.Badge
                WHERE t.AERA = :aera
                  AND j.datex >= :start_dt AND j.datex <= :end_dt
                  AND j.date_ack IS NOT NULL
            """, {'aera': aera_code, 'start_dt': start, 'end_dt': end})
            result['active'] = int(active_df['cnt'].iloc[0]) if not active_df.empty else 0
        except Exception:
            pass
    return result


def _query_area_kpi(area, start, end):
    """Per-area KPI: running machines, utilization, focus packages.

    Handles both SQL Server areas and Oracle areas (ISO, FS).
    """
    import pandas as pd
    from db import query_df
    from config import VIEW_NAME

    # Oracle areas: query from Oracle view
    if area in ('ISO', 'FS'):
        return _query_area_kpi_oracle(area, start, end)

    # Utilization
    util_df = query_df(f"""
        SELECT job_type,
               SUM(DATEDIFF(MINUTE, date_ack, date_close)) AS repair_min,
               SUM(ISNULL(Waiting_time, 0)) AS wait_min,
               COUNT(DISTINCT code_machine) AS machine_count
        FROM {VIEW_NAME}
        WHERE id_operation = :area
          AND datex >= :start_dt AND datex <= :end_dt
          AND date_ack IS NOT NULL AND date_close > date_ack
        GROUP BY job_type
    """, {'area': area, 'start_dt': start, 'end_dt': end})

    # Focus packages (top 3 by downtime hours)
    pkg_df = query_df(f"""
        SELECT TOP 3 [Package Type] AS package,
               SUM(DATEDIFF(MINUTE, date_ack, date_close)) / 60.0 AS hours,
               COUNT(*) AS events
        FROM {VIEW_NAME}
        WHERE id_operation = :area
          AND datex >= :start_dt AND datex <= :end_dt
          AND date_ack IS NOT NULL AND date_close > date_ack
          AND job_type = 'M/C DOWN'
          AND [Package Type] IS NOT NULL AND [Package Type] != ''
        GROUP BY [Package Type]
        ORDER BY hours DESC
    """, {'area': area, 'start_dt': start, 'end_dt': end})

    # Machine count from master
    mach_df = query_df(f"""
        SELECT COUNT(*) AS total
        FROM dbo.machine
        WHERE id_operation = :area
          AND flag_key = 1
          AND ISNULL(flag_delete, 0) != 1
    """, {'area': area})
    total_machines = int(mach_df['total'].iloc[0]) if not mach_df.empty else 0

    return util_df, pkg_df, total_machines


def _query_area_kpi_oracle(area, start, end):
    """Oracle equivalent for ISO/FS areas."""
    import pandas as pd
    try:
        from oracle_db import fetch_oracle_data, _store, _ensure_loaded
        import time as _t
        _ensure_loaded()
        for _ in range(45):
            if _store['df'] is not None:
                break
            _t.sleep(1)

        # Get 24h raw events
        ora = fetch_oracle_data(start.strftime('%Y-%m-%d'),
                                 end.strftime('%Y-%m-%d'),
                                 areas=[area])
        if ora is None or ora.empty:
            return pd.DataFrame(), pd.DataFrame(), _oracle_total_machines(area)

        # Filter to time range by date_ack
        ora = ora.copy()
        ora['date_ack'] = pd.to_datetime(ora['date_ack'], errors='coerce')
        ora = ora[(ora['date_ack'] >= start) & (ora['date_ack'] <= end)]

        # Aggregate util_df (same schema as SQL version)
        if ora.empty:
            util_df = pd.DataFrame(columns=['job_type', 'repair_min', 'wait_min', 'machine_count'])
        else:
            util_df = ora.groupby('job_type').agg(
                repair_min=('repair_min', lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()),
                wait_min=('wait_min', lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum()),
                machine_count=('machine_id', 'nunique'),
            ).reset_index()

        # Focus packages (PKG in Oracle)
        if 'PKG' in ora.columns:
            pkg_col = 'PKG'
        elif 'package_type' in ora.columns:
            pkg_col = 'package_type'
        else:
            pkg_col = None

        if pkg_col and not ora.empty:
            mc = ora[ora['job_type'] == 'M/C DOWN']
            if not mc.empty:
                mc = mc[mc[pkg_col].notna() & (mc[pkg_col].astype(str).str.strip() != '')]
                pkg_df = mc.groupby(pkg_col).agg(
                    hours=('repair_min', lambda x: round(pd.to_numeric(x, errors='coerce').fillna(0).sum() / 60.0, 1)),
                    events=('repair_min', 'count'),
                ).reset_index().rename(columns={pkg_col: 'package'}).nlargest(3, 'hours')
            else:
                pkg_df = pd.DataFrame(columns=['package', 'hours', 'events'])
        else:
            pkg_df = pd.DataFrame(columns=['package', 'hours', 'events'])

        total_machines = _oracle_total_machines(area)
        return util_df, pkg_df, total_machines

    except Exception as e:
        log.warning(f"Oracle area KPI for {area} failed: {e}")
        return pd.DataFrame(), pd.DataFrame(), 0


def _oracle_total_machines(area):
    """Count distinct machines for ISO/FS from Oracle store."""
    try:
        from oracle_db import _store
        if _store.get('df') is not None:
            full = _store['df']
            sub = full[full['area'] == area]
            return int(sub['machine_id'].nunique()) if not sub.empty else 0
    except Exception:
        pass
    return 0


def _calc_util_from_df(util_df, machine_count, hours=24):
    """Calculate util%, down%, lost% from aggregated util_df."""
    if machine_count <= 0 or util_df.empty or 'job_type' not in util_df.columns:
        return 100.0 if machine_count > 0 else 0, 0, 0
    avail = machine_count * hours * 60
    if avail <= 0:
        return 0, 0, 0
    down = util_df[util_df['job_type'] == 'M/C DOWN']['repair_min'].sum()
    lost_types = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'FACILITY DOWN',
                  'ENGINEERING DOWN', 'CLEAN MOLD', 'CHANGE CAP')
    lost = (util_df[util_df['job_type'].isin(lost_types)]['repair_min'].sum()
            + util_df['wait_min'].sum())
    pm = util_df[util_df['job_type'] == 'PM']['repair_min'].sum()
    down_pct = round(down / avail * 100, 2)
    lost_pct = round(lost / avail * 100, 2)
    pm_pct = round(pm / avail * 100, 2)
    util_pct = round(max(0, 100 - down_pct - lost_pct - pm_pct), 2)
    return util_pct, down_pct, lost_pct


def build_daily_report(target_date=None):
    """Generate HTML daily summary for morning meeting.

    target_date: date to report on (covers target 07:00 → next day 07:00).
                 If None, uses yesterday 07:00 → today 07:00 (normal run).
    """
    if target_date is None:
        now = datetime.now()
        start = (now - timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=7, minute=0, second=0, microsecond=0)
        date_str = start.strftime('%B %d, %Y')
    else:
        start = datetime(target_date.year, target_date.month, target_date.day, 7, 0, 0)
        end = start + timedelta(days=1)
        date_str = start.strftime('%B %d, %Y')

    # Query data
    hard_down = _query_hard_down(start, end)
    long_term = _query_long_term_down()

    # Build plant-wide sections
    area_sections_html = []
    plant_running = 0
    plant_total = 0

    for group, sub_areas in AREA_GROUPS.items():
        group_html = []
        group_running = 0
        group_total = 0
        group_util_parts = []

        for area in sub_areas:
            util_df, pkg_df, total_machines = _query_area_kpi(area, start, end)
            active = int(util_df['machine_count'].max()) if not util_df.empty else 0
            util_pct, down_pct, lost_pct = _calc_util_from_df(util_df, max(total_machines, 1))
            group_running += active
            group_total += total_machines

            # Focus packages
            pkgs = ""
            if not pkg_df.empty:
                pkgs = ", ".join(
                    f"{r['package']} ({r['hours']:.1f}h)"
                    for _, r in pkg_df.iterrows())

            # Hard down count for this area
            area_hard = hard_down[hard_down['area'] == area] if not hard_down.empty else pd.DataFrame()
            hard_count = len(area_hard)

            group_html.append(f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #EEF0F4">
                    <b>{AREA_NAMES.get(area, area)}</b> <span style="color:#8A96A8">({area})</span>
                </td>
                <td style="padding:8px 12px;border-bottom:1px solid #EEF0F4;text-align:right">
                    {active}/{total_machines}
                </td>
                <td style="padding:8px 12px;border-bottom:1px solid #EEF0F4;text-align:right;color:{'#2E9E4F' if util_pct >= 80 else '#FD7F20' if util_pct >= 60 else '#CC0000'};font-weight:600">
                    {util_pct}%
                </td>
                <td style="padding:8px 12px;border-bottom:1px solid #EEF0F4;text-align:center;color:#CC0000">
                    {hard_count}
                </td>
                <td style="padding:8px 12px;border-bottom:1px solid #EEF0F4;font-size:11px;color:#4A5568">
                    {pkgs or '—'}
                </td>
            </tr>""")

        plant_running += group_running
        plant_total += group_total

        # Technician count (registered + active) per shift
        aera_code = GROUP_TO_AERA.get(group, '')
        tech = _query_tech_count(aera_code, start, end)
        tech_html = (f"<span style='font-size:12px;color:#4A5568;font-weight:500;margin-left:12px'>"
                     f"👷 {tech['active']}/{tech['total']} · "
                     f"<span style='color:#FD7F20'>Day {tech['Day']['active']}/{tech['Day']['reg']}</span> · "
                     f"<span style='color:#702076'>Shift-1 {tech['Shift-1']['active']}/{tech['Shift-1']['reg']}</span> · "
                     f"<span style='color:#1D9CE4'>Shift-2 {tech['Shift-2']['active']}/{tech['Shift-2']['reg']}</span>"
                     f"</span>") if aera_code else ''

        area_sections_html.append(f"""
        <div style="margin-bottom:20px">
            <div style="font-size:14px;font-weight:700;color:#0E3689;margin-bottom:8px;
                        font-family:'DM Sans',sans-serif;border-bottom:2px solid #0E3689;padding-bottom:6px">
                {group} — {group_running}/{group_total} running
                {tech_html}
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <tr style="background:#EDF2FF">
                    <th style="padding:6px 12px;text-align:left;color:#0E3689;font-size:11px">Area</th>
                    <th style="padding:6px 12px;text-align:right;color:#0E3689;font-size:11px">M/C</th>
                    <th style="padding:6px 12px;text-align:right;color:#0E3689;font-size:11px">Util</th>
                    <th style="padding:6px 12px;text-align:center;color:#0E3689;font-size:11px">Hard Down</th>
                    <th style="padding:6px 12px;text-align:left;color:#0E3689;font-size:11px">Focus Packages</th>
                </tr>
                {''.join(group_html)}
            </table>
        </div>""")

    # Split Hard Down: Still Down (priority) vs Resolved (FYI)
    still_down = hard_down[hard_down['status'] == 'Still Down'] if not hard_down.empty else pd.DataFrame()
    resolved = hard_down[hard_down['status'] == 'Resolved'] if not hard_down.empty else pd.DataFrame()

    # Build rows for Still Down (top 5, full detail)
    still_rows = ""
    for _, r in still_down.head(5).iterrows():
        hrs = round(r['repair_min'] / 60, 1)
        still_rows += f"""
        <tr style="border-bottom:1px solid #EEF0F4">
            <td style="padding:8px 12px;font-weight:600;color:#CC0000">{r['machine_id']}</td>
            <td style="padding:8px 12px;color:#4A5568">{r['area']}</td>
            <td style="padding:8px 12px;font-size:12px">{r.get('symptom','')}</td>
            <td style="padding:8px 12px;font-size:12px;color:#6B3FA0">{r.get('action','') or '—'}</td>
            <td style="padding:8px 12px;text-align:right;color:#CC0000;font-weight:700">{hrs}h</td>
            <td style="padding:8px 12px;font-size:11px;color:#4A5568">{r.get('package_type','') or '—'}</td>
        </tr>"""

    # Build rows for Resolved (top 3, compact)
    resolved_rows = ""
    for _, r in resolved.head(3).iterrows():
        hrs = round(r['repair_min'] / 60, 1)
        resolved_rows += f"""
        <tr style="border-bottom:1px solid #EEF0F4">
            <td style="padding:6px 12px;font-weight:600">{r['machine_id']}</td>
            <td style="padding:6px 12px;color:#4A5568">{r['area']}</td>
            <td style="padding:6px 12px;font-size:12px">{r.get('symptom','')}</td>
            <td style="padding:6px 12px;text-align:right;color:#8A96A8;font-weight:500">{hrs}h</td>
        </tr>"""

    # Long-term down
    lt_rows = ""
    for _, r in long_term.head(10).iterrows():
        lt_rows += f"""
        <tr style="border-bottom:1px solid #EEF0F4">
            <td style="padding:6px 12px;font-weight:600">{r['machine_id']}</td>
            <td style="padding:6px 12px;color:#4A5568">{r['area']}</td>
            <td style="padding:6px 12px;text-align:right;color:#CC0000;font-weight:700">{r['days_down']}d</td>
            <td style="padding:6px 12px;font-size:12px">{r.get('symptom','')}</td>
            <td style="padding:6px 12px;font-size:11px;color:#4A5568">{r.get('package_type','') or '—'}</td>
        </tr>"""

    # Build full HTML
    plant_pct = round(plant_running / max(plant_total, 1) * 100, 1)
    html = f"""
    <div style="font-family:'IBM Plex Sans',Calibri,sans-serif;max-width:900px;margin:0 auto;background:#fff">

        <!-- Header -->
        <div style="background:#0E3689;padding:20px 24px;border-radius:10px 10px 0 0">
            <div style="color:#FFD53A;font-size:12px;font-weight:600;letter-spacing:0.5px">DAILY MORNING SUMMARY</div>
            <div style="color:#fff;font-size:22px;font-weight:700;font-family:'DM Sans',sans-serif;margin-top:4px">
                Plant Status — {date_str}
            </div>
            <div style="color:rgba(255,255,255,0.7);font-size:13px;margin-top:2px">
                Coverage: {start.strftime('%b %d %H:%M')} → {end.strftime('%b %d %H:%M')} (24h)
            </div>
        </div>

        <!-- Executive Summary -->
        <div style="background:#EDF2FF;padding:16px 24px;border-left:4px solid #0E3689">
            <div style="font-size:12px;font-weight:700;color:#0E3689;letter-spacing:0.5px;margin-bottom:8px">
                EXECUTIVE SUMMARY
            </div>
            <div style="font-size:14px;color:#1A1F2E;line-height:1.7">
                • <b>{plant_running}/{plant_total}</b> machines running ({plant_pct}%)<br>
                • <b>{len(still_down)}</b> machines <span style="color:#CC0000;font-weight:600">still down</span>,
                  <b>{len(resolved)}</b> resolved, <b>{len(long_term)}</b> long-term (&gt;{LONG_TERM_DAYS}d)<br>
                • <b>{len(hard_down)}</b> total hard-down events in last 24h
            </div>
        </div>

        <!-- Key Actions Required -->
        {f'''<div style="padding:16px 24px;background:#FFF8E1;border-left:4px solid #FD7F20">
            <div style="font-size:13px;font-weight:700;color:#FD7F20;letter-spacing:0.5px;margin-bottom:6px">
                ⚡ KEY ACTIONS REQUIRED
            </div>
            <div style="font-size:13px;color:#4A5568;line-height:1.6">
                {len(still_down)} machine(s) still down — need immediate attention below.<br>
                {len(long_term)} machine(s) down &gt;{LONG_TERM_DAYS} days — escalate for spare parts / scheduling.
            </div>
        </div>''' if (len(still_down) > 0 or len(long_term) > 0) else ''}

        <!-- Still Down (Priority) -->
        <div style="padding:16px 24px">
            <div style="font-size:15px;font-weight:700;color:#CC0000;margin-bottom:8px;
                        font-family:'DM Sans',sans-serif;border-bottom:2px solid #CC0000;padding-bottom:6px">
                🔴 Still Down Now — Need Attention ({len(still_down)})
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <tr style="background:#FDDEDE">
                    <th style="padding:8px 12px;text-align:left;color:#CC0000;font-size:11px">Machine</th>
                    <th style="padding:8px 12px;text-align:left;color:#CC0000;font-size:11px">Area</th>
                    <th style="padding:8px 12px;text-align:left;color:#CC0000;font-size:11px">Issue</th>
                    <th style="padding:8px 12px;text-align:left;color:#CC0000;font-size:11px">Action</th>
                    <th style="padding:8px 12px;text-align:right;color:#CC0000;font-size:11px">Duration</th>
                    <th style="padding:8px 12px;text-align:left;color:#CC0000;font-size:11px">Package</th>
                </tr>
                {still_rows if still_rows else '<tr><td colspan="6" style="padding:12px;color:#2E9E4F">✓ No machines currently down</td></tr>'}
            </table>
        </div>

        <!-- Resolved (FYI) -->
        {f'''<div style="padding:8px 24px 16px">
            <div style="font-size:13px;font-weight:600;color:#8A96A8;margin-bottom:6px">
                Recently Resolved (Top 3)
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:12px">
                <tr style="background:#F0F2F5">
                    <th style="padding:6px 12px;text-align:left;color:#4A5568;font-size:10px">Machine</th>
                    <th style="padding:6px 12px;text-align:left;color:#4A5568;font-size:10px">Area</th>
                    <th style="padding:6px 12px;text-align:left;color:#4A5568;font-size:10px">Issue</th>
                    <th style="padding:6px 12px;text-align:right;color:#4A5568;font-size:10px">Duration</th>
                </tr>
                {resolved_rows}
            </table>
        </div>''' if resolved_rows else ''}

        <!-- Area breakdown -->
        <div style="padding:16px 24px">
            <div style="font-size:15px;font-weight:700;color:#0E3689;margin-bottom:12px;
                        font-family:'DM Sans',sans-serif">
                Per-Area Breakdown
            </div>
            {''.join(area_sections_html)}
        </div>

        <!-- Long-term down -->
        <div style="padding:16px 24px">
            <div style="font-size:15px;font-weight:700;color:#FD7F20;margin-bottom:8px;
                        font-family:'DM Sans',sans-serif;border-bottom:2px solid #FD7F20;padding-bottom:6px">
                ⚠ Long-term Down ({LONG_TERM_DAYS}–{LONG_TERM_MAX_DAYS} days) — {len(long_term)} machines
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <tr style="background:#FFF3E0">
                    <th style="padding:6px 12px;text-align:left;color:#FD7F20;font-size:11px">Machine</th>
                    <th style="padding:6px 12px;text-align:left;color:#FD7F20;font-size:11px">Area</th>
                    <th style="padding:6px 12px;text-align:right;color:#FD7F20;font-size:11px">Days Down</th>
                    <th style="padding:6px 12px;text-align:left;color:#FD7F20;font-size:11px">Issue</th>
                    <th style="padding:6px 12px;text-align:left;color:#FD7F20;font-size:11px">Package</th>
                </tr>
                {lt_rows if lt_rows else '<tr><td colspan="5" style="padding:12px;color:#8A96A8">No long-term down machines</td></tr>'}
            </table>
        </div>

        <!-- Footer -->
        <div style="background:#F0F2F5;padding:12px 24px;border-radius:0 0 10px 10px;
                     text-align:center;font-size:12px;color:#8A96A8">
            <a href="http://10.50.21.96:8050/" style="color:#0E3689;text-decoration:none;font-weight:600">
                View Full Dashboard
            </a>
            <br>
            <span style="font-size:11px">Auto-generated at 07:30 · Microchip Technology · Proprietary and Confidential</span>
        </div>
    </div>
    """
    return html


def _parse_daily_recipients():
    """Parse DAILY_REPORT_RECIPIENTS from .env (comma separated emails)."""
    raw = os.getenv('DAILY_REPORT_RECIPIENTS', '')
    emails = [e.strip() for e in raw.split(',') if e.strip()]
    return emails


def send_daily_report():
    """Main function: build + send daily summary email."""
    enabled = os.getenv('DAILY_REPORT_ENABLED', '0') == '1'
    if not enabled:
        log.info("Daily report disabled (DAILY_REPORT_ENABLED=0)")
        return

    recipients = _parse_daily_recipients()
    if not recipients:
        log.warning("No DAILY_REPORT_RECIPIENTS configured")
        return

    try:
        html = build_daily_report()
        from shift_email import _get_smtp_config, _send_email
        smtp = _get_smtp_config()
        date_str = datetime.now().strftime('%B %d, %Y')
        subject = f'[Daily Summary] Plant Status — {date_str}'
        _send_email(smtp, recipients, subject, html)
        log.info(f"Sent daily report to {recipients}")
    except Exception as e:
        log.error(f"Daily report failed: {e}")
