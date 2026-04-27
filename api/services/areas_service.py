"""Areas service — unified SQL + Oracle area list."""
import logging
import pandas as pd

log = logging.getLogger(__name__)


def get_areas() -> dict:
    """Return list of areas with short_name and source (sql/oracle)."""
    from db import query_df
    from utils.queries import distinct_areas_from_master

    # Dedupe: one row per id_operation, pick MAX(short_name) to get a non-null
    df = query_df("""
        SELECT id_operation AS area,
               MAX(short_name) AS short_name,
               COUNT(*) AS machine_count
        FROM dbo.machine
        WHERE id_operation IS NOT NULL AND id_operation != ''
          AND LEN(id_operation) BETWEEN 2 AND 20
          AND ISNULL(flag_delete, 0) != 1
        GROUP BY id_operation
        ORDER BY id_operation
    """)

    areas = []
    for _, r in df.iterrows():
        a = str(r.get('area', '') or '').strip()
        if not a or a.isdigit():
            continue
        areas.append({
            'area': a,
            'short_name': str(r.get('short_name') or '') or None,
            'source': 'sql',
            'machine_count': int(r.get('machine_count') or 0),
        })

    # Add Oracle ISO/FS
    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import fetch_oracle_live_status
            odf = fetch_oracle_live_status()
            if odf is not None and not odf.empty:
                for a in sorted(odf['area'].dropna().unique()):
                    mc = int(odf[odf['area'] == a]['code_machine'].nunique())
                    areas.append({
                        'area': str(a),
                        'short_name': str(a),
                        'source': 'oracle',
                        'machine_count': mc,
                    })
    except Exception as e:
        log.warning(f"Oracle areas fetch failed: {e}")

    areas.sort(key=lambda x: x['area'])
    return {'areas': areas, 'total': len(areas)}
