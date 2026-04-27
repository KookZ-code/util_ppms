"""Downtime endpoints — events + pareto."""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_DEFAULT, CACHE_TTL_MACHINES, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.downtime import DowntimeEventList, ParetoData
from api.services.downtime_service import (
    get_events, get_pareto, get_downtime_detail, get_downtime_machines,
)

router = APIRouter(prefix='/api/v1/downtime', tags=['downtime'])
limiter = Limiter(key_func=get_remote_address)


def _split(s: Optional[str]):
    if not s:
        return None
    return tuple(sorted([x.strip() for x in s.split(',') if x.strip()]))


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached_events(start, end, areas_key, job_types_key, limit):
    areas = list(areas_key) if areas_key else None
    job_types = list(job_types_key) if job_types_key else None
    return get_events(start, end, areas, job_types, limit)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached_pareto(start, end, areas_key, job_types_key, reason_col, top_n):
    areas = list(areas_key) if areas_key else None
    job_types = list(job_types_key) if job_types_key else None
    return get_pareto(start, end, areas, job_types, reason_col, top_n)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=50)
async def _cached_detail(job_types_key, start, end, areas_key,
                         machines_key, shift, reason_col):
    job_types = list(job_types_key) if job_types_key else []
    areas = list(areas_key) if areas_key else None
    machines = list(machines_key) if machines_key else None
    return get_downtime_detail(
        job_types, start, end, areas, machines, shift, reason_col)


@ttl_cache(ttl=CACHE_TTL_MACHINES, maxsize=20)
async def _cached_dt_machines(areas_key):
    areas = list(areas_key) if areas_key else None
    return get_downtime_machines(areas)


@router.get('/events', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def events(
    request: Request,
    start: str = Query(..., description='Start date YYYY-MM-DD'),
    end: str = Query(..., description='End date YYYY-MM-DD'),
    areas: Optional[str] = Query(None, description='Comma-separated area codes'),
    job_types: Optional[str] = Query(None, description="Comma-separated, default 'M/C DOWN'"),
    limit: int = Query(500, ge=1, le=5000),
    key_info: dict = Depends(require_api_key),
):
    """Event-level downtime list (SQL + Oracle merged). Cached 5 min."""
    areas_up = _split(areas.upper() if areas else None)
    jt = _split(job_types)

    t0 = time.time()
    data = await _cached_events(start, end, areas_up, jt, limit)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=DowntimeEventList(**data),
        meta=ResponseMeta(
            cached=_cached_events.last_hit,
            query_time_ms=elapsed_ms if not _cached_events.last_hit else 0,
        ),
    )


@router.get('/pareto', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def pareto(
    request: Request,
    start: str = Query(..., description='Start date YYYY-MM-DD'),
    end: str = Query(..., description='End date YYYY-MM-DD'),
    areas: Optional[str] = Query(None, description='Comma-separated area codes'),
    job_types: Optional[str] = Query(None, description="Comma-separated, default 'M/C DOWN'"),
    reason_col: str = Query('symptom', description="'symptom' or 'cause'"),
    top_n: int = Query(20, ge=1, le=100),
    key_info: dict = Depends(require_api_key),
):
    """Pareto analysis grouped by symptom or cause. Cached 5 min."""
    areas_up = _split(areas.upper() if areas else None)
    jt = _split(job_types)

    t0 = time.time()
    data = await _cached_pareto(start, end, areas_up, jt, reason_col, top_n)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=ParetoData(**data),
        meta=ResponseMeta(
            cached=_cached_pareto.last_hit,
            query_time_ms=elapsed_ms if not _cached_pareto.last_hit else 0,
        ),
    )


@router.get('/detail', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def downtime_detail(
    request: Request,
    job_types: str = Query(..., description='Comma-separated job types (e.g. "M/C DOWN" or "SETUP,SETUP BY OPERATOR")'),
    start: str = Query(..., description='YYYY-MM-DD'),
    end: str = Query(..., description='YYYY-MM-DD'),
    areas: Optional[str] = Query(None),
    machines: Optional[str] = Query(None, description='Comma-separated machine IDs'),
    shift: Optional[str] = Query(None, description="'DAY' | 'NIGHT' | None"),
    reason_col: Optional[str] = Query(None, description="'symptom' for M/C DOWN drill-down, else groups by cause"),
    key_info: dict = Depends(require_api_key),
):
    """Bundled downtime payload for the dashboard Downtime & Setup page.

    Returns 6 arrays: reason, machines_by_reason, daily_shift,
    machine_daily, symptom_cause, events. All SQL+Oracle merged.
    Cached 5 min.
    """
    jt = _split(job_types)
    areas_t = _split(areas.upper() if areas else None)
    machines_t = _split(machines)
    shift_up = shift.upper() if shift else None
    if shift_up and shift_up not in ('DAY', 'NIGHT'):
        shift_up = None

    t0 = time.time()
    data = await _cached_detail(jt, start, end, areas_t, machines_t,
                                 shift_up, reason_col)
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_detail.last_hit,
            query_time_ms=elapsed_ms if not _cached_detail.last_hit else 0,
        ),
    )


@router.get('/machines', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def downtime_machines(
    request: Request,
    areas: Optional[str] = Query(None),
    key_info: dict = Depends(require_api_key),
):
    """Machines with M/C DOWN or SETUP events (for filter dropdown).
    Cached 1 hour."""
    areas_t = _split(areas.upper() if areas else None)
    t0 = time.time()
    data = await _cached_dt_machines(areas_t)
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_dt_machines.last_hit,
            query_time_ms=elapsed_ms if not _cached_dt_machines.last_hit else 0,
        ),
    )
