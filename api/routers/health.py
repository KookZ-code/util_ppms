"""Health check endpoint — no auth required."""
from datetime import datetime
from fastapi import APIRouter

router = APIRouter(prefix='/api/v1', tags=['health'])


@router.get('/health')
async def health():
    """Basic health check. Returns API status and DB connectivity."""
    sql_ok = False
    oracle_ok = False
    try:
        from db import query_df
        df = query_df("SELECT 1 AS ok")
        sql_ok = not df.empty
    except Exception:
        sql_ok = False

    try:
        from oracle_db import _store
        oracle_ok = _store.get('df') is not None
    except Exception:
        oracle_ok = False

    return {
        'status': 'ok',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'databases': {
            'sql_server': 'ok' if sql_ok else 'down',
            'oracle': 'ok' if oracle_ok else 'loading_or_down',
        },
    }
