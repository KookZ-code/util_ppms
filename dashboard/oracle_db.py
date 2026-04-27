"""Oracle database connection for ISO / FS area data.

Strategy: load ALL Oracle data in a background thread on startup,
cache the full DataFrame, and filter in Python per request.
The Oracle view is slow (~20s) so we never block the UI.
"""
import time
import logging
import threading
import pandas as pd

log = logging.getLogger(__name__)

ORACLE_AREA_MAP = {'ISO': 'ISOLATE', 'FS': 'FORM_SING'}
AREA_REVERSE = {v: k for k, v in ORACLE_AREA_MAP.items()}

_client_initialized = False
_lock = threading.Lock()

# Full dataset cache — loaded in background, refreshed periodically
_store = {'df': None, 'ts': 0, 'loading': False}
REFRESH_INTERVAL = 600  # seconds (10 min)


def _init_client():
    global _client_initialized
    if _client_initialized:
        return
    import oracledb
    from config import ORA_CLIENT_LIB
    if ORA_CLIENT_LIB:
        oracledb.init_oracle_client(lib_dir=ORA_CLIENT_LIB)
    _client_initialized = True


def _get_connection():
    import oracledb
    from config import ORA_USER, ORA_PASSWORD, ORA_DSN
    _init_client()
    return oracledb.connect(user=ORA_USER, password=ORA_PASSWORD, dsn=ORA_DSN)


def _load_all():
    """Load ALL Oracle data (2025+) into memory. Runs in background thread."""
    from config import ORA_VIEW
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.prefetchrows = 5000
        cur.arraysize = 5000

        sql = f"""
            SELECT EQUIPMENT_TYPE, EQUIPMENT_ID, S_DATE, P_START, P_STOP,
                   JOB_TYPE, CAUSE, CRITERIA, DOWNTIME, WAIT_TECH, BADGE_NO, SHIFT
            FROM {ORA_VIEW}
            WHERE P_START IS NOT NULL AND P_STOP IS NOT NULL
              AND P_STOP > P_START
        """
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()

        if not rows:
            with _lock:
                _store.update({'df': None, 'ts': time.time(), 'loading': False})
            return

        df = pd.DataFrame(rows, columns=cols)
        df = df.rename(columns={
            'EQUIPMENT_ID': 'machine_id',
            'S_DATE': 'datex',
            'P_START': 'date_ack',
            'P_STOP': 'date_close',
            'JOB_TYPE': 'job_type',
            'CAUSE': 'cause',
            'CRITERIA': 'symptom',
            'DOWNTIME': 'repair_min',
            'WAIT_TECH': 'wait_min',
            'BADGE_NO': 'badge',
        })
        df['area'] = df['EQUIPMENT_TYPE'].map(AREA_REVERSE)
        df.drop(columns=['EQUIPMENT_TYPE'], inplace=True)
        df['repair_min'] = pd.to_numeric(df['repair_min'], errors='coerce').fillna(0)
        df['wait_min'] = pd.to_numeric(df['wait_min'], errors='coerce').fillna(0)
        df['datex'] = pd.to_datetime(df['datex'], errors='coerce')

        with _lock:
            _store.update({'df': df, 'ts': time.time(), 'loading': False})
        log.info("Oracle data loaded: %d rows", len(df))

    except Exception as e:
        log.warning("Oracle background load failed: %s", e)
        with _lock:
            _store['loading'] = False


def _ensure_loaded():
    """Trigger background load if stale or not yet loaded."""
    now = time.time()
    with _lock:
        if _store['loading']:
            return  # already loading
        if _store['df'] is not None and (now - _store['ts']) < REFRESH_INTERVAL:
            return  # still fresh
        _store['loading'] = True

    t = threading.Thread(target=_load_all, daemon=True)
    t.start()


def fetch_oracle_data(start_date, end_date, areas=None, shift=None):
    """Return filtered Oracle data from in-memory cache.

    Non-blocking: returns None if data not yet loaded.
    Triggers background refresh if stale.
    """
    from config import ORA_ENABLED
    if not ORA_ENABLED:
        return None

    # Determine which Oracle areas are requested
    if areas:
        ora_areas = [a for a in areas if a in ORACLE_AREA_MAP]
        if not ora_areas:
            return None
    else:
        ora_areas = list(ORACLE_AREA_MAP.keys())

    # Trigger background load if needed
    _ensure_loaded()

    # Return from cache (non-blocking)
    with _lock:
        full_df = _store['df']

    if full_df is None:
        return None

    # Filter in Python (fast — full dataset is ~30K rows)
    df = full_df.copy()

    # Area filter
    df = df[df['area'].isin(ora_areas)]

    # Date filter
    if start_date:
        df = df[df['datex'] >= pd.Timestamp(str(start_date)[:10])]
    if end_date:
        end_ts = pd.Timestamp(str(end_date)[:10]) + pd.Timedelta(days=1)
        df = df[df['datex'] < end_ts]

    # Shift filter
    if shift == 'DAY':
        df = df[df['SHIFT'] == 'D']
    elif shift == 'NIGHT':
        df = df[df['SHIFT'] == 'N']

    # Rename SHIFT to shift_code (D/N) for downstream use
    df = df.rename(columns={'SHIFT': 'shift_code'})

    return df if not df.empty else None


_live_cache = {'data': None, 'ts': 0}
LIVE_CACHE_TTL = 300  # 5 minutes — balance between freshness and Oracle load


def fetch_oracle_live_status(selected_areas=None):
    """Query live ISO/FS jobs from EQ_USER.V_EQDOWNTIME for Overview page.

    Returns DataFrame with columns matching dbo.job_list format, or None.
    Cached for 60 seconds to avoid slow Oracle queries on every refresh.
    """
    from config import ORA_ENABLED
    if not ORA_ENABLED:
        return None

    # Only fetch if ISO/FS areas are requested (or no filter = all)
    if selected_areas:
        ora_areas = [a for a in selected_areas if a in ORACLE_AREA_MAP]
        if not ora_areas:
            return None
    else:
        ora_areas = list(ORACLE_AREA_MAP.keys())

    ora_types = [ORACLE_AREA_MAP[a] for a in ora_areas]

    # Check cache
    now = time.time()
    if _live_cache['data'] is not None and (now - _live_cache['ts']) < LIVE_CACHE_TTL:
        cached = _live_cache['data']
        filtered = cached[cached['area'].isin(ora_areas)]
        return filtered if not filtered.empty else None

    try:
        _init_client()
        conn = _get_connection()
        cur = conn.cursor()
        cur.prefetchrows = 500
        cur.arraysize = 500

        placeholders = ', '.join(f":et{i}" for i in range(len(ora_types)))
        bind = {f'et{i}': t for i, t in enumerate(ora_types)}

        sql = f"""
            SELECT EQUIPMENT_TYPE, EQUIPMENT_ID, CAUSE, CRITERIA,
                   P_START, P_STOP, STATUS, BADGE_NO, NAME,
                   NVL(WAIT_TECH, 0) AS WAIT_TECH,
                   NVL(DOWNTIME, 0) AS DOWNTIME,
                   S_DATE, PKG
            FROM EQ_USER.V_EQDOWNTIME
            WHERE EQUIPMENT_TYPE IN ({placeholders})
              AND S_DATE >= TRUNC(SYSDATE) - 1
            ORDER BY P_START DESC
        """

        cur.execute(sql, bind)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return None

        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)

        # Map to Overview-compatible columns
        df['area'] = df['EQUIPMENT_TYPE'].map(AREA_REVERSE)
        df['code_machine'] = df['EQUIPMENT_ID']
        df['job_type'] = 'M/C DOWN'  # Default; refine from CAUSE
        # Map CAUSE to job_type
        setup_keywords = ['SETUP', 'SET UP', 'SET D/V', 'CHANGE']
        pm_keywords = ['PM', 'PREVENTIVE']
        for idx, row in df.iterrows():
            cause = str(row.get('CAUSE', '') or '').upper()
            criteria = str(row.get('CRITERIA', '') or '').upper()
            if any(k in criteria for k in setup_keywords):
                df.at[idx, 'job_type'] = 'SETUP'
            elif any(k in cause for k in pm_keywords):
                df.at[idx, 'job_type'] = 'PM'

        df['des_job'] = df['CRITERIA']
        df['datex'] = df['P_START']
        df['date_ack'] = df['P_START']
        df['date_close'] = df['P_STOP']
        df['tech'] = df['BADGE_NO']
        df['by_ack'] = df['BADGE_NO']
        df['wait_min'] = pd.to_numeric(df['WAIT_TECH'], errors='coerce').fillna(0).astype(int)
        df['repair_min'] = pd.to_numeric(df['DOWNTIME'], errors='coerce').fillna(0).astype(int)

        # Map STATUS to overview status
        df['status'] = df['STATUS'].map({
            'Working': 'On Process',
            'Waiting Approval': 'On Process',
            'Completed': 'Closed',
        }).fillna('Waiting')
        # Override: if P_STOP is NULL → On Process (tech working)
        df.loc[df['P_STOP'].isna() & df['P_START'].notna(), 'status'] = 'On Process'

        df['mpc'] = ''
        df['die_mask'] = ''
        df['package_type'] = df['PKG'].fillna('')
        df['wire_type'] = ''

        # Cache result
        _live_cache.update({'data': df, 'ts': time.time()})

        # Filter to requested areas
        filtered = df[df['area'].isin(ora_areas)]
        return filtered if not filtered.empty else None

    except Exception as e:
        log.warning("Oracle live status fetch failed: %s", e)
        return None


# ── Auto-start background load on import ──────────────────────────────────────
try:
    from config import ORA_ENABLED as _OE
    if _OE:
        _ensure_loaded()
except Exception:
    pass
