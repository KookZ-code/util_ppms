"""Technician performance service — composite scoring (5 metrics)."""
import logging
from typing import Optional, List
import pandas as pd

log = logging.getLogger(__name__)

# Composite weights (match dashboard/pages/timeline.py)
W_MTTR = 0.30
W_RESPONSE = 0.20
W_FTFR = 0.25
W_VOLUME = 0.15
W_VERSATILITY = 0.10


def _grade(score: float) -> str:
    if score >= 85:
        return 'A'
    if score >= 70:
        return 'B'
    if score >= 55:
        return 'C'
    return 'D'


def _normalize_inverse(series: pd.Series) -> pd.Series:
    """Lower is better — map to 0-100 where min=100, max=0."""
    s = series.fillna(series.max() if not series.empty else 0)
    if s.empty:
        return s
    hi, lo = s.max(), s.min()
    if hi == lo:
        return pd.Series([100.0] * len(s), index=s.index)
    return ((hi - s) / (hi - lo) * 100).clip(0, 100)


def _normalize_direct(series: pd.Series) -> pd.Series:
    """Higher is better — map to 0-100."""
    s = series.fillna(0)
    if s.empty:
        return s
    hi, lo = s.max(), s.min()
    if hi == lo:
        return pd.Series([100.0 if hi > 0 else 0.0] * len(s), index=s.index)
    return ((s - lo) / (hi - lo) * 100).clip(0, 100)


def get_tech_performance(
    start_date: str,
    end_date: str,
    areas: Optional[List[str]] = None,
    shift: Optional[str] = None,
    job_type: Optional[str] = None,
    top_n: int = 50,
) -> dict:
    """Return tech performance with composite score + grade."""
    from db import query_df
    from config import VIEW_NAME
    from utils.queries import build_tech_where, tech_score_metrics

    where, params = build_tech_where(start_date, end_date, areas, shift, job_type)
    sql_df = query_df(tech_score_metrics(VIEW_NAME, where), params)

    # Oracle tech metrics
    ora_df = pd.DataFrame()
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_data
            from utils.oracle_agg import ora_tech_score_metrics
            odf = fetch_oracle_data(start_date, end_date, areas, shift)
            if odf is not None and not odf.empty:
                if job_type:
                    odf = odf[odf['job_type'] == job_type]
                if not odf.empty:
                    ora_df = ora_tech_score_metrics(odf)
    except Exception as e:
        log.warning(f"Oracle tech metrics failed: {e}")

    merged = pd.concat([sql_df, ora_df], ignore_index=True)
    if merged.empty:
        return {
            'technicians': [], 'total': 0,
            'period': {'start': start_date, 'end': end_date,
                       'shift': shift or 'ALL',
                       'areas': areas or [], 'job_type': job_type},
        }

    merged = merged[merged['technician'].notna() & (merged['technician'] != '')]
    merged = merged.groupby('technician', as_index=False).agg(
        job_count=('job_count', 'sum'),
        avg_response_min=('avg_response_min', 'mean'),
        avg_repair_min=('avg_repair_min', 'mean'),
        area_count=('area_count', 'max'),
        ftfr_pct=('ftfr_pct', 'mean'),
    )

    merged['mttr_score'] = _normalize_inverse(merged['avg_repair_min']).round(1)
    merged['response_score'] = _normalize_inverse(merged['avg_response_min']).round(1)
    merged['ftfr_score'] = merged['ftfr_pct'].fillna(0).clip(0, 100).round(1)
    merged['volume_score'] = _normalize_direct(merged['job_count']).round(1)
    merged['versatility_score'] = _normalize_direct(merged['area_count']).round(1)

    merged['composite_score'] = (
        merged['mttr_score'] * W_MTTR
        + merged['response_score'] * W_RESPONSE
        + merged['ftfr_score'] * W_FTFR
        + merged['volume_score'] * W_VOLUME
        + merged['versatility_score'] * W_VERSATILITY
    ).round(1)
    merged['grade'] = merged['composite_score'].apply(_grade)

    merged = merged.sort_values('composite_score', ascending=False).head(top_n)

    techs = []
    for _, r in merged.iterrows():
        techs.append({
            'technician': str(r['technician']),
            'job_count': int(r['job_count']),
            'avg_response_min': float(round(r['avg_response_min'] or 0, 1)),
            'avg_repair_min': float(round(r['avg_repair_min'] or 0, 1)),
            'area_count': int(r['area_count'] or 0),
            'ftfr_pct': float(round(r['ftfr_pct'] or 0, 1)),
            'mttr_score': float(r['mttr_score']),
            'response_score': float(r['response_score']),
            'ftfr_score': float(r['ftfr_score']),
            'volume_score': float(r['volume_score']),
            'versatility_score': float(r['versatility_score']),
            'composite_score': float(r['composite_score']),
            'grade': str(r['grade']),
        })

    return {
        'technicians': techs,
        'total': len(techs),
        'period': {
            'start': start_date, 'end': end_date,
            'shift': shift or 'ALL',
            'areas': areas or [], 'job_type': job_type,
        },
    }
