"""SQL query builders for vw_job_nokey.

All queries use the column mapping from config.COLUMN_MAP so they
adapt to whatever schema the view actually has.
"""
from config import COLUMN_MAP, VIEW_NAME


def _col(key):
    """Get mapped column name, falling back to the key itself."""
    return COLUMN_MAP.get(key, '') or key


def overview_status_counts():
    """Count machines by current status."""
    status = _col('status')
    return f"""
        SELECT [{status}] AS status, COUNT(*) AS cnt
        FROM {VIEW_NAME}
        GROUP BY [{status}]
        ORDER BY cnt DESC
    """


def overview_status_by_area():
    """Status counts grouped by machine area."""
    status = _col('status')
    area = _col('machine_area')
    return f"""
        SELECT [{area}] AS area, [{status}] AS status, COUNT(*) AS cnt
        FROM {VIEW_NAME}
        GROUP BY [{area}], [{status}]
        ORDER BY [{area}], cnt DESC
    """


def machine_list(area_filter=None):
    """List all machines, optionally filtered by area."""
    mid = _col('machine_id')
    mname = _col('machine_name')
    area = _col('machine_area')
    status = _col('status')
    where = f"WHERE [{area}] = :area" if area_filter else ""
    return f"""
        SELECT [{mid}] AS machine_id,
               [{mname}] AS machine_name,
               [{area}] AS area,
               [{status}] AS status
        FROM {VIEW_NAME}
        {where}
        ORDER BY [{area}], [{mid}]
    """


def utilization_trend(date_col=None):
    """Daily utilization trend."""
    status = _col('status')
    start = _col('opr_start_time') if not date_col else date_col
    return f"""
        SELECT CAST([{start}] AS DATE) AS date,
               [{status}] AS status,
               COUNT(*) AS cnt
        FROM {VIEW_NAME}
        WHERE [{start}] >= :start_date AND [{start}] <= :end_date
        GROUP BY CAST([{start}] AS DATE), [{status}]
        ORDER BY date
    """


def downtime_by_reason():
    """Downtime events grouped by reason."""
    reason = _col('downtime_reason')
    start = _col('opr_start_time')
    end = _col('end_time')
    return f"""
        SELECT [{reason}] AS reason,
               COUNT(*) AS event_count,
               SUM(DATEDIFF(MINUTE, [{start}], [{end}])) / 60.0 AS total_hours,
               AVG(DATEDIFF(MINUTE, [{start}], [{end}])) / 60.0 AS avg_hours
        FROM {VIEW_NAME}
        WHERE [{reason}] IS NOT NULL AND [{reason}] != ''
        GROUP BY [{reason}]
        ORDER BY total_hours DESC
    """


def downtime_by_machine():
    """Downtime grouped by machine and reason."""
    mid = _col('machine_id')
    reason = _col('downtime_reason')
    start = _col('opr_start_time')
    end = _col('end_time')
    return f"""
        SELECT [{mid}] AS machine_id,
               [{reason}] AS reason,
               COUNT(*) AS event_count,
               SUM(DATEDIFF(MINUTE, [{start}], [{end}])) / 60.0 AS total_hours
        FROM {VIEW_NAME}
        WHERE [{reason}] IS NOT NULL AND [{reason}] != ''
        GROUP BY [{mid}], [{reason}]
        ORDER BY total_hours DESC
    """


def machine_detail(machine_id):
    """All records for a specific machine."""
    mid = _col('machine_id')
    start = _col('opr_start_time')
    return f"""
        SELECT *
        FROM {VIEW_NAME}
        WHERE [{mid}] = :machine_id
        ORDER BY [{start}] DESC
    """


def distinct_areas():
    """Get distinct machine areas."""
    area = _col('machine_area')
    return f"""
        SELECT DISTINCT [{area}] AS area
        FROM {VIEW_NAME}
        WHERE [{area}] IS NOT NULL AND [{area}] != ''
        ORDER BY [{area}]
    """


ORACLE_ONLY_AREAS = {'ISO', 'FS'}


def build_util_where(tc, ec, ac, start_date, end_date, areas, shift):
    """Build shared WHERE clause and params dict for utilization queries."""
    from config import EXCLUDED_MACHINES
    mid = _col('machine_id')

    # Strip Oracle-only areas from SQL Server query
    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else areas
    if areas and not sql_areas:
        # User selected ONLY Oracle areas — SQL Server returns nothing
        return "WHERE 1=0", {}

    clauses = [f"[{ec}] > [{tc}]"]
    params  = {}
    if start_date:
        clauses.append(f"[{tc}] >= :start_date")
        params['start_date'] = start_date
    if end_date:
        clauses.append(f"[{tc}] < DATEADD(DAY, 1, CAST(:end_date AS DATE))")
        params['end_date'] = end_date
    if sql_areas:
        phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
        clauses.append(f"[{ac}] IN ({phs})")
        for i, a in enumerate(sql_areas):
            params[f'area_{i}'] = a
    if shift == 'DAY':
        clauses.append(f"DATEPART(HOUR, [{tc}]) BETWEEN 7 AND 18")
    elif shift == 'NIGHT':
        clauses.append(f"DATEPART(HOUR, [{tc}]) NOT BETWEEN 7 AND 18")
    # Exclude blank areas
    clauses.append(f"[{ac}] IS NOT NULL AND [{ac}] != ''")
    # Exclude specific machines
    if EXCLUDED_MACHINES:
        ephs = ', '.join(f":excl_{i}" for i in range(len(EXCLUDED_MACHINES)))
        clauses.append(f"RTRIM(LTRIM([{mid}])) NOT IN ({ephs})")
        for i, m in enumerate(EXCLUDED_MACHINES):
            params[f'excl_{i}'] = m.strip()
    return "WHERE " + " AND ".join(clauses), params


def util_kpi_totals(view, tech_tc, ec, sc, where):
    """Repair minutes + waiting minutes per job_type.
    repair_min = DATEDIFF(tech_start, end)  → used for Downtime/Lost/PM
    wait_min   = Waiting_time column        → added to Lost Time
    """
    return f"""
        SELECT [{sc}] AS job_type,
               SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) AS total_min,
               SUM(ISNULL(Waiting_time, 0))                AS wait_min
        FROM {view} {where}
        GROUP BY [{sc}]
    """


def util_monthly_composition(view, opr_tc, tech_tc, ec, sc, where):
    """Monthly repair + waiting minutes per job_type."""
    return f"""
        SELECT CONVERT(VARCHAR(7), [{opr_tc}], 120) AS ym,
               [{sc}] AS job_type,
               SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) AS total_min,
               SUM(ISNULL(Waiting_time, 0))                AS wait_min
        FROM {view} {where}
        GROUP BY CONVERT(VARCHAR(7), [{opr_tc}], 120), [{sc}]
        ORDER BY ym
    """


def util_by_area(view, tech_tc, ec, sc, ac, where):
    """Area-level repair + waiting minutes per job_type."""
    return f"""
        SELECT [{ac}] AS area,
               [{sc}] AS job_type,
               SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) AS total_min,
               SUM(ISNULL(Waiting_time, 0))                AS wait_min
        FROM {view} {where}
        GROUP BY [{ac}], [{sc}]
    """


def util_by_machine(view, tech_tc, ec, sc, ac, mid, where):
    """Per-machine repair + waiting minutes per job_type."""
    return f"""
        SELECT [{mid}] AS machine_id,
               [{ac}] AS area,
               [{sc}] AS job_type,
               SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) AS total_min,
               SUM(ISNULL(Waiting_time, 0))                AS wait_min
        FROM {view} {where}
        GROUP BY [{mid}], [{ac}], [{sc}]
    """


def util_top_machines_per_cause(view, tech_tc, ec, sc, rc, mid, where, job_types_in):
    """Top 3 machines by repair hours for each cause (for hover tooltip)."""
    return f"""
        SELECT cause, machine_id, hrs
        FROM (
            SELECT [{rc}] AS cause,
                   [{mid}] AS machine_id,
                   SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0 AS hrs,
                   ROW_NUMBER() OVER (
                       PARTITION BY [{rc}]
                       ORDER BY SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) DESC
                   ) AS rn
            FROM {view} {where}
            AND [{sc}] IN ({job_types_in})
            AND [{rc}] IS NOT NULL AND [{rc}] != ''
            GROUP BY [{rc}], [{mid}]
        ) t
        WHERE rn <= 3
        ORDER BY cause, rn
    """


def util_attention_machines(view, opr_tc, tech_tc, ec, sc, ac, mid, where):
    """Top 10 machines needing attention, ranked by composite score.
    Score = (down_hours * 2) + event_count + (avg_mttr_min / 10)
    Only M/C DOWN events.
    """
    return f"""
        SELECT TOP 10
            [{mid}] AS machine_id,
            [{ac}] AS area,
            ROUND(SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0, 1) AS down_hours,
            COUNT(*) AS event_count,
            ROUND(AVG(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) * 1.0, 0) AS avg_mttr_min,
            ROUND(
                SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0 * 2.0
                + COUNT(*)
                + AVG(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 10.0
            , 1) AS score
        FROM {view} {where}
        AND [{sc}] = 'M/C DOWN'
        AND [{tech_tc}] IS NOT NULL
        AND [{ec}] > [{tech_tc}]
        GROUP BY [{mid}], [{ac}]
        ORDER BY score DESC
    """


def util_freq_vs_duration(view, tech_tc, ec, sc, ac, mid, where):
    """Per-machine downtime frequency vs avg repair duration scatter data.
    Only M/C DOWN. Exclude machines with < 2 events to reduce noise.
    """
    return f"""
        SELECT
            [{mid}] AS machine_id,
            [{ac}] AS area,
            COUNT(*) AS freq,
            ROUND(AVG(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) * 1.0, 1) AS avg_dur_min,
            ROUND(SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) / 60.0, 1) AS total_hours
        FROM {view} {where}
        AND [{sc}] = 'M/C DOWN'
        AND [{tech_tc}] IS NOT NULL
        AND [{ec}] > [{tech_tc}]
        GROUP BY [{mid}], [{ac}]
        HAVING COUNT(*) >= 2
        ORDER BY total_hours DESC
    """


def util_kpi_prev_period(view, opr_tc, tech_tc, ec, sc, start_date, end_date):
    """Same as util_kpi_totals but for the previous period of equal length.
    Previous period = [start - duration, start - 1 day].
    No area/shift filters — compare apples-to-apples on the same machines.
    """
    return f"""
        DECLARE @start DATE = :start_date
        DECLARE @end   DATE = :end_date
        DECLARE @days  INT  = DATEDIFF(DAY, @start, @end) + 1
        DECLARE @prev_start DATE = DATEADD(DAY, -@days, @start)
        DECLARE @prev_end   DATE = DATEADD(DAY, -1,     @start)

        SELECT [{sc}] AS job_type,
               SUM(DATEDIFF(MINUTE, [{tech_tc}], [{ec}])) AS total_min,
               SUM(ISNULL(Waiting_time, 0))                AS wait_min
        FROM {view}
        WHERE [{ec}] > [{opr_tc}]
          AND [{opr_tc}] >= @prev_start
          AND [{opr_tc}] <  @start
        GROUP BY [{sc}]
    """


def util_machine_count(view, ac, mid, where):
    """Count distinct machines per area within the filter period."""
    return f"""
        SELECT [{ac}] AS area,
               COUNT(DISTINCT [{mid}]) AS machine_count
        FROM {view} {where}
        GROUP BY [{ac}]
    """


def util_total_machine_count(view, mid, where):
    """Count all distinct machines across all selected areas."""
    return f"""
        SELECT COUNT(DISTINCT [{mid}]) AS machine_count
        FROM {view} {where}
    """


def distinct_machines(area_filter=None):
    """Get distinct machine IDs, optionally filtered by area."""
    mid = _col('machine_id')
    mname = _col('machine_name')
    area = _col('machine_area')
    where = f"WHERE [{area}] = :area" if area_filter else ""
    return f"""
        SELECT DISTINCT [{mid}] AS machine_id,
               [{mname}] AS machine_name
        FROM {VIEW_NAME}
        {where}
        ORDER BY [{mid}]
    """


# ── Machine master data queries ───────────────────────────────────────────────
def machine_master_info():
    """Single machine metadata from dbo.machine."""
    from config import MACHINE_TABLE
    return f"""
        SELECT code_machine, des_machine, sn, mfg, model,
               id_operation, short_name, date_install,
               flag_downtime, flag_pm, flag_automotive, flag_gold, flag_key,
               remark, ods_name, id_group, id_area
        FROM {MACHINE_TABLE}
        WHERE RTRIM(LTRIM([code_machine])) = :machine_id
    """


def distinct_areas_from_master():
    """Areas with friendly names from machine master table."""
    from config import MACHINE_TABLE
    return f"""
        SELECT DISTINCT [id_operation] AS area, [short_name]
        FROM {MACHINE_TABLE}
        WHERE [id_operation] IS NOT NULL AND [id_operation] != ''
        ORDER BY [id_operation]
    """


def distinct_machines_from_master(area_filter=None, key_only=False):
    """Machines with descriptions from master table."""
    from config import MACHINE_TABLE
    clauses = []
    if area_filter:
        clauses.append("[id_operation] = :area")
    if key_only:
        clauses.append("[flag_key] = 1")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return f"""
        SELECT [code_machine] AS machine_id, [des_machine],
               [id_operation] AS area, [short_name] AS area_name
        FROM {MACHINE_TABLE}
        {where}
        ORDER BY [id_operation], [code_machine]
    """


def machine_downtime_kpis():
    """Aggregate downtime KPIs for a single machine."""
    sc  = _col('status')
    otc = _col('opr_start_time')
    ttc = _col('tech_start_time')
    ec  = _col('end_time')
    mid = _col('machine_id')
    return f"""
        SELECT COUNT(*) AS total_events,
               SUM(CASE WHEN [{sc}] = 'M/C DOWN' THEN 1 ELSE 0 END) AS down_events,
               ROUND(AVG(CASE WHEN [{sc}] = 'M/C DOWN'
                    THEN DATEDIFF(MINUTE, [{ttc}], [{ec}]) * 1.0 END), 0) AS avg_mttr_min,
               ROUND(SUM(CASE WHEN [{sc}] = 'M/C DOWN'
                    THEN DATEDIFF(MINUTE, [{otc}], [{ec}]) / 60.0 END), 1) AS total_down_hrs,
               ROUND(AVG(CASE WHEN [{sc}] = 'M/C DOWN'
                    THEN ISNULL(Waiting_time, 0) * 1.0 END), 0) AS avg_wait_min
        FROM {VIEW_NAME}
        WHERE [{mid}] = :machine_id
          AND [{ec}] > [{otc}]
    """


# ── Technician Performance queries ─────────────────────────────────────────────
def build_tech_where(start_date, end_date, areas, shift, job_type):
    """WHERE clause for technician performance queries (closed jobs only)."""
    # Strip Oracle-only areas
    sql_areas = [a for a in areas if a not in ORACLE_ONLY_AREAS] if areas else areas
    if areas and not sql_areas:
        return "WHERE 1=0", {}

    clauses = [
        "[date_close] IS NOT NULL",
        "[date_ack] IS NOT NULL",
        "[date_close] > [date_ack]",
        "ISNULL(by_perform, by_ack) IS NOT NULL",
        "ISNULL(by_perform, by_ack) != ''",
    ]
    params = {}
    if start_date:
        clauses.append("[datex] >= :start_date")
        params['start_date'] = start_date
    if end_date:
        clauses.append("[datex] < DATEADD(DAY, 1, CAST(:end_date AS DATE))")
        params['end_date'] = end_date
    if sql_areas:
        phs = ', '.join(f":area_{i}" for i in range(len(sql_areas)))
        clauses.append(f"[id_operation] IN ({phs})")
        for i, a in enumerate(sql_areas):
            params[f'area_{i}'] = a
    if shift == 'DAY':
        clauses.append("DATEPART(HOUR, [datex]) BETWEEN 7 AND 18")
    elif shift == 'NIGHT':
        clauses.append("DATEPART(HOUR, [datex]) NOT BETWEEN 7 AND 18")
    if job_type:
        clauses.append("[job_type] = :job_type")
        params['job_type'] = job_type
    return "WHERE " + " AND ".join(clauses), params


def tech_score_metrics(view, where):
    """Per-technician metrics for composite scoring.

    Returns: technician, job_count, avg_response_min, avg_repair_min,
             ftfr_pct, area_count
    """
    return f"""
        WITH base AS (
            SELECT ISNULL(by_perform, by_ack) AS technician,
                   COUNT(*) AS job_count,
                   ROUND(AVG(ISNULL(Waiting_time, 0) * 1.0), 1) AS avg_response_min,
                   ROUND(AVG(DATEDIFF(MINUTE, [date_ack], [date_close]) * 1.0), 1) AS avg_repair_min,
                   COUNT(DISTINCT [id_operation]) AS area_count
            FROM {view} {where}
            GROUP BY ISNULL(by_perform, by_ack)
        ),
        mc_jobs AS (
            SELECT ISNULL(by_perform, by_ack) AS technician,
                   code_machine, date_close,
                   LEAD(datex) OVER (
                       PARTITION BY ISNULL(by_perform, by_ack), code_machine
                       ORDER BY datex
                   ) AS next_same_date
            FROM {view} {where}
              AND [job_type] = 'M/C DOWN'
        ),
        ftfr AS (
            SELECT technician,
                   COUNT(*) AS mc_total,
                   SUM(CASE WHEN next_same_date IS NULL
                            OR DATEDIFF(DAY, date_close, next_same_date) > 7
                       THEN 1 ELSE 0 END) AS first_fixes
            FROM mc_jobs
            GROUP BY technician
        )
        SELECT b.technician, b.job_count, b.avg_response_min, b.avg_repair_min,
               b.area_count,
               COALESCE(
                   ROUND(CAST(f.first_fixes AS FLOAT)
                         / NULLIF(f.mc_total, 0) * 100, 1),
                   100
               ) AS ftfr_pct
        FROM base b
        LEFT JOIN ftfr f ON b.technician = f.technician
        ORDER BY b.job_count DESC
    """


def tech_list_query():
    """All technicians from master list."""
    return """
        SELECT [Badge], [Name], [NameTH], [AERA], [Job Desc],
               [Supv], [Group]
        FROM [dbo].[TechnicianList]
    """


# ── Overview (Live) queries — from dbo.job_list ───────────────────────────────
def overview_status_matrix():
    """Status matrix: Waiting / On Process / Closed × job_type."""
    return """
        SELECT job_type,
               SUM(CASE WHEN date_ack IS NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS waiting,
               SUM(CASE WHEN date_ack IS NOT NULL AND date_close IS NULL THEN 1 ELSE 0 END) AS on_process,
               SUM(CASE WHEN date_close IS NOT NULL THEN 1 ELSE 0 END) AS closed,
               COUNT(*) AS total
        FROM [dbo].[job_list]
        WHERE code_machine IS NOT NULL AND code_machine != ''
          AND LEN(code_machine) > 3
        GROUP BY job_type
        ORDER BY total DESC
    """


def overview_open_jobs():
    """Currently open jobs (Waiting + On Process) sorted by longest wait."""
    return """
        SELECT code_machine, id_operation AS area, job_type, des_job,
               datex, date_ack, by_ack AS tech,
               CASE WHEN date_ack IS NULL
                    THEN DATEDIFF(MINUTE, datex, GETDATE())
                    ELSE DATEDIFF(MINUTE, datex, date_ack) END AS wait_min,
               CASE WHEN date_ack IS NOT NULL
                    THEN DATEDIFF(MINUTE, date_ack, GETDATE())
                    ELSE NULL END AS repair_min,
               CASE WHEN date_ack IS NULL THEN 'Waiting'
                    ELSE 'On Process' END AS status,
               [mpc] AS die_mask,
               [Die Size] AS die_size,
               [Package Type] AS package_type,
               [Wire Type] AS wire_type
        FROM [dbo].[job_list]
        WHERE date_close IS NULL
          AND code_machine IS NOT NULL AND code_machine != ''
          AND LEN(code_machine) > 3
          AND datex >= DATEADD(MONTH, -1, GETDATE())
        ORDER BY datex ASC
    """


def overview_kpi_summary():
    """Quick KPI counts from live data."""
    return """
        SELECT
            (SELECT
                -- Non-WB key machines
                (SELECT COUNT(*) FROM dbo.machine
                 WHERE id_operation IS NOT NULL AND id_operation != ''
                 AND id_operation != 'WB' AND flag_key = 1
                 AND ISNULL(flag_delete,0) != 1)
                +
                -- WB: single head key machines (no L/R children)
                (SELECT COUNT(*) FROM dbo.machine a
                 WHERE a.id_operation = 'WB' AND a.flag_key = 1
                 AND ISNULL(a.flag_delete,0) != 1
                 AND a.code_machine NOT LIKE '%[LR]'
                 AND NOT EXISTS (SELECT 1 FROM dbo.machine b
                     WHERE b.id_operation = 'WB'
                     AND (b.code_machine = a.code_machine + 'L'
                          OR b.code_machine = a.code_machine + 'R')))
                +
                -- WB: L/R heads where base is key
                (SELECT COUNT(*) FROM dbo.machine a
                 WHERE a.id_operation = 'WB'
                 AND ISNULL(a.flag_delete,0) != 1
                 AND a.code_machine LIKE '%[LR]'
                 AND EXISTS (SELECT 1 FROM dbo.machine b
                     WHERE b.id_operation = 'WB' AND b.flag_key = 1
                     AND b.code_machine = LEFT(a.code_machine, LEN(a.code_machine)-1)))
            ) AS total_key_machines,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
             AND date_ack IS NULL) AS waiting_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
             AND date_ack IS NOT NULL) AS on_process_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NULL AND code_machine != ''
             AND job_type = 'M/C DOWN') AS down_count,
            (SELECT COUNT(*) FROM [dbo].[job_list]
             WHERE date_close IS NOT NULL AND code_machine != ''
             AND LEN(code_machine) > 3
             AND date_close >= CASE
                 WHEN DATEPART(HOUR, GETDATE()) BETWEEN 7 AND 18
                 THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '07:00'
                 WHEN DATEPART(HOUR, GETDATE()) >= 19
                 THEN CAST(CAST(GETDATE() AS DATE) AS DATETIME) + '19:00'
                 ELSE CAST(DATEADD(DAY, -1, CAST(GETDATE() AS DATE)) AS DATETIME) + '19:00'
             END) AS closed_this_shift
    """


# ── Machine Inventory queries ─────────────────────────────────────────────────
def inventory_all_machines():
    """All machines from master table for inventory page."""
    from config import MACHINE_TABLE
    return f"""
        SELECT [code_machine], [des_machine], [mfg], [model], [sn],
               [id_operation], [short_name], [date_install],
               [flag_key], [flag_automotive], [flag_gold], [flag_pm],
               [flag_downtime], [remark], [ods_name], [id_group]
        FROM {MACHINE_TABLE}
        WHERE [id_operation] IS NOT NULL AND [id_operation] != ''
          AND ISNULL([flag_delete], 0) != 1
        ORDER BY [id_operation], [code_machine]
    """


def oracle_key_machine_count(areas=None):
    """Count KEY machines in Oracle-managed areas (ISO / FS) from dbo.machine.

    Oracle's V_EQDOWNTIME is an event feed (no fleet inventory), so the
    correct source for a headcount is the master machine table — same
    source used by the Inventory page and by overview_status_matrix() for
    SQL-Server areas.

    Args:
        areas: optional list of user-selected areas. The query is restricted
            to the intersection of `areas` and ORACLE_ONLY_AREAS. If None or
            empty, counts every ORACLE_ONLY_AREAS machine. If `areas` is
            provided but contains no Oracle-managed area (e.g. user filtered
            to only SQL-Server areas), returns a query that yields 0 rather
            than a syntax error.
    """
    from config import MACHINE_TABLE

    # Restrict to Oracle-managed areas only (ISO / FS)
    if areas:
        target_areas = sorted(a for a in areas if a in ORACLE_ONLY_AREAS)
    else:
        target_areas = sorted(ORACLE_ONLY_AREAS)

    if not target_areas:
        # User filtered to non-Oracle areas only — short-circuit with 0
        return "SELECT 0 AS key_machines"

    # target_areas values come from ORACLE_ONLY_AREAS (module-level constant)
    # — safe to inline, not user input
    placeholders = ', '.join(f"'{a}'" for a in target_areas)
    return f"""
        SELECT COUNT(*) AS key_machines
        FROM {MACHINE_TABLE}
        WHERE [id_operation] IN ({placeholders})
          AND [flag_key] = 1
          AND ISNULL([flag_delete], 0) != 1
    """


def inventory_machine_downtime():
    """Per-machine downtime hours (last 7 days) for treemap sizing/coloring."""
    mid = _col('machine_id')
    sc  = _col('status')
    otc = _col('opr_start_time')
    ttc = _col('tech_start_time')
    ec  = _col('end_time')
    return f"""
        SELECT [{mid}] AS code_machine,
               COUNT(*) AS down_events,
               ROUND(SUM(DATEDIFF(MINUTE, [{ttc}], [{ec}])) / 60.0, 1) AS down_hrs,
               ROUND(AVG(DATEDIFF(MINUTE, [{ttc}], [{ec}])), 0) AS avg_mttr_min
        FROM {VIEW_NAME}
        WHERE [{sc}] = 'M/C DOWN'
          AND [{ttc}] IS NOT NULL AND [{ec}] > [{ttc}]
          AND [{otc}] >= DATEADD(DAY, -7, GETDATE())
        GROUP BY [{mid}]
    """


def inventory_packages_by_area():
    """Distinct package types per area from job data."""
    from config import MACHINE_TABLE, VIEW_NAME
    return f"""
        SELECT DISTINCT m.[id_operation] AS area,
               m.[short_name],
               v.[Package Type] AS package
        FROM {MACHINE_TABLE} m
        INNER JOIN {VIEW_NAME} v
            ON RTRIM(LTRIM(m.[code_machine])) = RTRIM(LTRIM(v.[code_machine]))
        WHERE m.[id_operation] IS NOT NULL AND m.[id_operation] != ''
          AND v.[Package Type] IS NOT NULL AND v.[Package Type] != ''
        ORDER BY area, package
    """
