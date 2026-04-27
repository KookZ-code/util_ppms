"""Pandas aggregation functions for Oracle data.

Each function takes a raw Oracle DataFrame (from oracle_db.fetch_oracle_data)
and returns a DataFrame matching the equivalent SQL Server query output shape.
Returns empty DataFrame with correct columns if input is None/empty.
"""
import pandas as pd
import numpy as np


def _empty(cols):
    return pd.DataFrame(columns=cols)


def _safe(df, cols):
    """Return empty df if input is None or empty."""
    if df is None or df.empty:
        return _empty(cols)
    return df


# ── Utilization queries ───────────────────────────────────────────────────────

def ora_kpi_totals(df):
    """Match util_kpi_totals: job_type, total_min, wait_min."""
    cols = ['job_type', 'total_min', 'wait_min']
    df = _safe(df, cols)
    if df.empty:
        return df
    return df.groupby('job_type').agg(
        total_min=('repair_min', 'sum'),
        wait_min=('wait_min', 'sum'),
    ).reset_index()


def ora_monthly(df):
    """Match util_monthly_composition: ym, job_type, total_min, wait_min."""
    cols = ['ym', 'job_type', 'total_min', 'wait_min']
    df = _safe(df, cols)
    if df.empty:
        return df
    tmp = df.copy()
    tmp['ym'] = pd.to_datetime(tmp['datex']).dt.strftime('%Y-%m')
    return tmp.groupby(['ym', 'job_type']).agg(
        total_min=('repair_min', 'sum'),
        wait_min=('wait_min', 'sum'),
    ).reset_index()


def ora_by_area(df):
    """Match util_by_area: area, job_type, total_min, wait_min."""
    cols = ['area', 'job_type', 'total_min', 'wait_min']
    df = _safe(df, cols)
    if df.empty:
        return df
    return df.groupby(['area', 'job_type']).agg(
        total_min=('repair_min', 'sum'),
        wait_min=('wait_min', 'sum'),
    ).reset_index()


def ora_machine_count(df):
    """Match util_machine_count: area, machine_count."""
    cols = ['area', 'machine_count']
    df = _safe(df, cols)
    if df.empty:
        return df
    return df.groupby('area')['machine_id'].nunique().reset_index(
    ).rename(columns={'machine_id': 'machine_count'})


def ora_total_machine_count(df):
    """Match util_total_machine_count: machine_count (scalar)."""
    cols = ['machine_count']
    df = _safe(df, cols)
    if df.empty:
        return df
    return pd.DataFrame({'machine_count': [df['machine_id'].nunique()]})


def ora_by_machine(df):
    """Match util_by_machine: machine_id, area, job_type, total_min, wait_min."""
    cols = ['machine_id', 'area', 'job_type', 'total_min', 'wait_min']
    df = _safe(df, cols)
    if df.empty:
        return df
    return df.groupby(['machine_id', 'area', 'job_type']).agg(
        total_min=('repair_min', 'sum'),
        wait_min=('wait_min', 'sum'),
    ).reset_index()


def ora_freq_vs_duration(df):
    """Match util_freq_vs_duration: machine_id, area, freq, avg_dur_min, total_hours."""
    cols = ['machine_id', 'area', 'freq', 'avg_dur_min', 'total_hours']
    df = _safe(df, cols)
    if df.empty:
        return df
    mc = df[df['job_type'] == 'M/C DOWN'].copy()
    if mc.empty:
        return _empty(cols)
    agg = mc.groupby(['machine_id', 'area']).agg(
        freq=('repair_min', 'count'),
        avg_dur_min=('repair_min', 'mean'),
        total_hours=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
    ).reset_index()
    agg['avg_dur_min'] = agg['avg_dur_min'].round(1)
    return agg[agg['freq'] >= 2]


def ora_attention_machines(df):
    """Match util_attention_machines: machine_id, area, down_hours, event_count, avg_mttr_min, score."""
    cols = ['machine_id', 'area', 'down_hours', 'event_count', 'avg_mttr_min', 'score']
    df = _safe(df, cols)
    if df.empty:
        return df
    mc = df[df['job_type'] == 'M/C DOWN'].copy()
    if mc.empty:
        return _empty(cols)
    agg = mc.groupby(['machine_id', 'area']).agg(
        down_hours=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        event_count=('repair_min', 'count'),
        avg_mttr_min=('repair_min', lambda x: round(x.mean(), 0)),
    ).reset_index()
    agg['score'] = (agg['down_hours'] * 2 + agg['event_count']
                    + agg['avg_mttr_min'] / 10).round(1)
    return agg.nlargest(10, 'score')


# ── Top causes ────────────────────────────────────────────────────────────────

def ora_top_symptoms(df, n=5):
    """Top N symptoms (des_job) by repair hours for M/C DOWN."""
    cols = ['cause', 'hours']
    df = _safe(df, cols)
    if df.empty:
        return df
    mc = df[df['job_type'] == 'M/C DOWN'].copy()
    if mc.empty:
        return _empty(cols)
    agg = mc.groupby('symptom').agg(
        hours=('repair_min', lambda x: round(x.sum() / 60.0, 1))
    ).reset_index().rename(columns={'symptom': 'cause'})
    return agg.nlargest(n, 'hours')


def ora_top_lost_causes(df, lost_types, n=5):
    """Top N lost-time causes (by symptom/criteria) by repair+wait hours."""
    cols = ['cause', 'hours']
    df = _safe(df, cols)
    if df.empty:
        return df
    lost = df[df['job_type'].isin(lost_types)].copy()
    if lost.empty:
        return _empty(cols)
    lost['total_hrs'] = (lost['repair_min'] + lost['wait_min']) / 60.0
    agg = lost.groupby('symptom').agg(
        hours=('total_hrs', lambda x: round(x.sum(), 1))
    ).reset_index().rename(columns={'symptom': 'cause'})
    return agg.nlargest(n, 'hours')


def ora_machines_per_cause(df):
    """Top 3 machines per cause for hover tooltips."""
    cols = ['cause', 'machine_id', 'hrs']
    df = _safe(df, cols)
    if df.empty:
        return df
    mc = df[df['job_type'] == 'M/C DOWN'].copy()
    if mc.empty:
        return _empty(cols)
    mc['hrs'] = mc['repair_min'] / 60.0
    agg = mc.groupby(['symptom', 'machine_id']).agg(
        hrs=('hrs', 'sum')
    ).reset_index().rename(columns={'symptom': 'cause'})
    # Top 3 per cause
    top3 = (agg.sort_values(['cause', 'hrs'], ascending=[True, False])
            .groupby('cause').head(3))
    top3['hrs'] = top3['hrs'].round(1)
    return top3[cols]


# ── Downtime page aggregations ────────────────────────────────────────────────

def _filter_jobs(df, job_types):
    """Filter df to given job_types, return copy or empty."""
    if df is None or df.empty:
        return pd.DataFrame()
    return df[df['job_type'].isin(job_types)].copy()


def ora_dt_reason(df, job_types, reason_col='symptom'):
    """Pareto by reason: reason, events, repair_hrs, wait_hrs, total_hrs, avg_repair_min, avg_wait_min, max_wait_min."""
    cols = ['reason', 'events', 'repair_hrs', 'wait_hrs', 'total_hrs',
            'avg_repair_min', 'avg_wait_min', 'max_wait_min']
    sub = _filter_jobs(df, job_types)
    if sub.empty:
        return _empty(cols)
    sub = sub[sub[reason_col].notna() & (sub[reason_col] != '')]
    if sub.empty:
        return _empty(cols)
    agg = sub.groupby(reason_col).agg(
        events=('repair_min', 'count'),
        repair_hrs=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        wait_hrs=('wait_min', lambda x: round(x.sum() / 60.0, 1)),
        avg_repair_min=('repair_min', 'mean'),
        avg_wait_min=('wait_min', 'mean'),
        max_wait_min=('wait_min', 'max'),
    ).reset_index().rename(columns={reason_col: 'reason'})
    agg['total_hrs'] = (agg['repair_hrs'] + agg['wait_hrs']).round(1)
    agg['avg_repair_min'] = agg['avg_repair_min'].round(0)
    agg['avg_wait_min'] = agg['avg_wait_min'].round(0)
    agg['max_wait_min'] = agg['max_wait_min'].round(0)
    return agg.sort_values('total_hrs', ascending=False).reset_index(drop=True)


def ora_dt_machine(df, job_types, reason_col='symptom'):
    """Machine breakdown: machine_id, reason, event_count, total_hours."""
    cols = ['machine_id', 'reason', 'event_count', 'total_hours']
    sub = _filter_jobs(df, job_types)
    if sub.empty:
        return _empty(cols)
    sub = sub[sub[reason_col].notna() & (sub[reason_col] != '')]
    if sub.empty:
        return _empty(cols)
    agg = sub.groupby(['machine_id', reason_col]).agg(
        event_count=('repair_min', 'count'),
        total_hours=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
    ).reset_index().rename(columns={reason_col: 'reason'})
    return agg.sort_values('total_hours', ascending=False).reset_index(drop=True)


def ora_dt_daily_shift(df, job_types):
    """Daily shift trend: day, shift_name, events, repair_hrs, wait_hrs."""
    cols = ['day', 'shift_name', 'events', 'repair_hrs', 'wait_hrs']
    sub = _filter_jobs(df, job_types)
    if sub.empty:
        return _empty(cols)
    sub['datex'] = pd.to_datetime(sub['datex'], errors='coerce')
    sub['day'] = sub['datex'].dt.normalize()
    # Use Oracle SHIFT column (D/N) if available, else compute from date_ack hour
    if 'shift_code' in sub.columns:
        sub['shift_name'] = sub['shift_code'].map({'D': 'Day', 'N': 'Night'}).fillna('Day')
    else:
        sub['hour'] = pd.to_datetime(sub['date_ack'], errors='coerce').dt.hour
        sub['shift_name'] = np.where(sub['hour'].between(7, 18), 'Day', 'Night')
        mask_evening = sub['hour'] >= 19
        sub.loc[mask_evening, 'day'] = sub.loc[mask_evening, 'day'] + pd.Timedelta(days=1)
    agg = sub.groupby(['day', 'shift_name']).agg(
        events=('repair_min', 'count'),
        repair_hrs=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        wait_hrs=('wait_min', lambda x: round(x.sum() / 60.0, 1)),
    ).reset_index()
    return agg.sort_values(['day', 'shift_name']).reset_index(drop=True)


def ora_dt_machine_daily(df, job_types, reason_col='symptom'):
    """Per-machine per-day per-shift per-reason for drill-down."""
    cols = ['machine_id', 'reason', 'day', 'shift_name', 'events',
            'total_hours', 'wait_hrs']
    sub = _filter_jobs(df, job_types)
    if sub.empty:
        return _empty(cols)
    sub = sub[sub[reason_col].notna() & (sub[reason_col] != '')]
    if sub.empty:
        return _empty(cols)
    sub['datex'] = pd.to_datetime(sub['datex'], errors='coerce')
    sub['day'] = sub['datex'].dt.normalize()
    # Use Oracle SHIFT column (D/N) if available
    if 'shift_code' in sub.columns:
        sub['shift_name'] = sub['shift_code'].map({'D': 'Day', 'N': 'Night'}).fillna('Day')
    else:
        sub['hour'] = pd.to_datetime(sub['date_ack'], errors='coerce').dt.hour
        sub['shift_name'] = np.where(sub['hour'].between(7, 18), 'Day', 'Night')
        mask_evening = sub['hour'] >= 19
        sub.loc[mask_evening, 'day'] = sub.loc[mask_evening, 'day'] + pd.Timedelta(days=1)
    agg = sub.groupby(['machine_id', reason_col, 'day', 'shift_name']).agg(
        events=('repair_min', 'count'),
        total_hours=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        wait_hrs=('wait_min', lambda x: round(x.sum() / 60.0, 1)),
    ).reset_index().rename(columns={reason_col: 'reason'})
    return agg


def ora_dt_symptom_cause(df, job_types):
    """Symptom→Root Cause detail for M/C DOWN section."""
    cols = ['symptom', 'root_cause', 'events', 'repair_hrs', 'wait_hrs',
            'total_hrs', 'avg_repair_min', 'avg_wait_min']
    sub = _filter_jobs(df, job_types)
    if sub.empty:
        return _empty(cols)
    sub = sub[sub['cause'].notna() & (sub['cause'] != '')]
    if sub.empty:
        return _empty(cols)
    agg = sub.groupby(['symptom', 'cause']).agg(
        events=('repair_min', 'count'),
        repair_hrs=('repair_min', lambda x: round(x.sum() / 60.0, 1)),
        wait_hrs=('wait_min', lambda x: round(x.sum() / 60.0, 1)),
        avg_repair_min=('repair_min', 'mean'),
        avg_wait_min=('wait_min', 'mean'),
    ).reset_index().rename(columns={'cause': 'root_cause'})
    agg['total_hrs'] = (agg['repair_hrs'] + agg['wait_hrs']).round(1)
    agg['avg_repair_min'] = agg['avg_repair_min'].round(0)
    agg['avg_wait_min'] = agg['avg_wait_min'].round(0)
    return agg.sort_values('total_hrs', ascending=False).reset_index(drop=True)


# ── Tech Performance aggregation ──────────────────────────────────────────────

def ora_tech_score_metrics(df):
    """Compute per-technician metrics matching tech_score_metrics() SQL output.

    Returns: technician, job_count, avg_response_min, avg_repair_min, area_count, ftfr_pct
    """
    cols = ['technician', 'job_count', 'avg_response_min', 'avg_repair_min',
            'area_count', 'ftfr_pct']
    if df is None or df.empty:
        return _empty(cols)
    # Filter: valid badge, valid times
    sub = df[df['badge'].notna() & (df['badge'] != '')].copy()
    if sub.empty:
        return _empty(cols)

    # Base metrics
    base = sub.groupby('badge').agg(
        job_count=('repair_min', 'count'),
        avg_response_min=('wait_min', 'mean'),
        avg_repair_min=('repair_min', 'mean'),
        area_count=('area', 'nunique'),
    ).reset_index().rename(columns={'badge': 'technician'})
    base['avg_response_min'] = base['avg_response_min'].round(1)
    base['avg_repair_min'] = base['avg_repair_min'].round(1)

    # FTFR: same tech + same machine, no repeat M/C DOWN within 7 days
    mc = sub[sub['job_type'] == 'M/C DOWN'].copy()
    if mc.empty:
        base['ftfr_pct'] = 100.0
    else:
        mc['datex'] = pd.to_datetime(mc['datex'], errors='coerce')
        mc['date_close'] = pd.to_datetime(mc['date_close'], errors='coerce')
        mc = mc.sort_values(['badge', 'machine_id', 'datex'])
        mc['next_datex'] = mc.groupby(['badge', 'machine_id'])['datex'].shift(-1)
        mc['days_to_next'] = (mc['next_datex'] - mc['date_close']).dt.days
        mc['is_ftf'] = mc['days_to_next'].isna() | (mc['days_to_next'] > 7)

        ftfr = mc.groupby('badge').agg(
            mc_total=('is_ftf', 'count'),
            first_fixes=('is_ftf', 'sum'),
        ).reset_index()
        ftfr['ftfr_pct'] = (ftfr['first_fixes'] / ftfr['mc_total'] * 100).round(1)
        ftfr = ftfr.rename(columns={'badge': 'technician'})[['technician', 'ftfr_pct']]
        base = base.merge(ftfr, on='technician', how='left')
        base['ftfr_pct'] = base['ftfr_pct'].fillna(100.0)

    return base[cols]
