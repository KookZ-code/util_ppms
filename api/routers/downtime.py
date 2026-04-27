"""Downtime endpoints — events + pareto."""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_DEFAULT, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.downtime import DowntimeEventList, ParetoData
from api.services.downtime_service import get_events, get_pareto

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
