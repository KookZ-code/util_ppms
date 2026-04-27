"""Technician performance endpoint."""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_DEFAULT, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.tech import TechPerformanceData
from api.services.tech_service import get_tech_performance

router = APIRouter(prefix='/api/v1', tags=['tech'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached(start, end, areas_key, shift, job_type, top_n):
    areas = list(areas_key) if areas_key else None
    return get_tech_performance(start, end, areas, shift, job_type, top_n)


@router.get('/tech-performance', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def tech_performance(
    request: Request,
    start: str = Query(..., description='Start date YYYY-MM-DD'),
    end: str = Query(..., description='End date YYYY-MM-DD'),
    areas: Optional[str] = Query(None, description='Comma-separated area codes'),
    shift: Optional[str] = Query(None, description="'DAY' | 'NIGHT' | None"),
    job_type: Optional[str] = Query(None, description="Filter by job_type, e.g. 'M/C DOWN'"),
    top_n: int = Query(50, ge=1, le=500),
    key_info: dict = Depends(require_api_key),
):
    """Tech composite scoring (5 metrics: MTTR 30%, Response 20%, FTFR 25%, Volume 15%, Versatility 10%).

    Cached 5 min.
    """
    area_tuple = None
    if areas:
        area_tuple = tuple(sorted([a.strip().upper() for a in areas.split(',') if a.strip()]))
    shift_up = shift.upper() if shift else None
    if shift_up and shift_up not in ('DAY', 'NIGHT'):
        shift_up = None

    t0 = time.time()
    data = await _cached(start, end, area_tuple, shift_up, job_type, top_n)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=TechPerformanceData(**data),
        meta=ResponseMeta(
            cached=_cached.last_hit,
            query_time_ms=elapsed_ms if not _cached.last_hit else 0,
        ),
    )
