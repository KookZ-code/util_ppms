import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Database connection
DB_CONFIG = {
    'server': os.getenv('DB_SERVER', 'localhost'),
    'port': os.getenv('DB_PORT', '1433'),
    'database': os.getenv('DB_NAME', ''),
    'username': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'driver': os.getenv('DB_DRIVER', 'SQL Server'),
}

# Column mapping for vw_job_nokey
# opr_start_time : date_act   — Operator opens job (machine reported down)
# tech_start_time: datex      — Technician acknowledges & starts repair
# end_time       : date_close — Job closed (repair done)
# waiting_time   = DATEDIFF(MINUTE, date_act, datex)   (wait for tech)
# repair_time    = DATEDIFF(MINUTE, datex, date_close)  (actual repair)
COLUMN_MAP = {
    'machine_id':      os.getenv('COL_MACHINE_ID',       ''),
    'machine_name':    os.getenv('COL_MACHINE_NAME',     ''),
    'machine_area':    os.getenv('COL_MACHINE_AREA',     ''),
    'status':          os.getenv('COL_STATUS',           ''),
    'downtime_reason': os.getenv('COL_DOWNTIME_REASON',  ''),
    'symptom':         os.getenv('COL_SYMPTOM',           ''),
    'downtime_code':   os.getenv('COL_DOWNTIME_CODE',    ''),
    'opr_start_time':  os.getenv('COL_OPR_START_TIME',   ''),   # Operator start
    'tech_start_time': os.getenv('COL_TECH_START_TIME',  ''),   # Tech start (was start_time)
    'end_time':        os.getenv('COL_END_TIME',         ''),
    'job_id':          os.getenv('COL_JOB_ID',           ''),
}

# Dashboard settings
REFRESH_MINUTES = int(os.getenv('REFRESH_MINUTES', '5'))

MACHINE_AREAS = [a.strip() for a in os.getenv('MACHINE_AREAS', 'Die Attach,SAW,Wire Bond').split(',')]

EXCLUDED_MACHINES = [m.strip() for m in os.getenv('EXCLUDED_MACHINES', '').split(',') if m.strip()]

# Per-area utilization targets  e.g. "BG:85,DA:80,WB:85"
def _parse_targets(raw: str, default: int = 85) -> dict:
    targets = {}
    for part in raw.split(','):
        part = part.strip()
        if ':' in part:
            area, val = part.split(':', 1)
            try:
                targets[area.strip()] = int(val.strip())
            except ValueError:
                pass
    return targets

AREA_TARGETS: dict = _parse_targets(
    os.getenv('AREA_TARGETS', ''), default=85
)

DASH_HOST = os.getenv('DASH_HOST', '0.0.0.0')
DASH_PORT = int(os.getenv('DASH_PORT', '8050'))

# Main SQL view
VIEW_NAME = os.getenv('VIEW_NAME', 'vw_job_nokey')
MACHINE_TABLE = os.getenv('MACHINE_TABLE', 'dbo.machine')

# Oracle connection (ISO / FS areas)
ORA_USER = os.getenv('ORA_USER', '')
ORA_PASSWORD = os.getenv('ORA_PASSWORD', '')
ORA_DSN = os.getenv('ORA_DSN', '')
ORA_CLIENT_LIB = os.getenv('ORA_CLIENT_LIB', '')
ORA_VIEW = os.getenv('ORA_VIEW', 'Vw_Asodowntime_2025on')
ORA_ENABLED = os.getenv('ORA_ENABLED', '0') == '1'
