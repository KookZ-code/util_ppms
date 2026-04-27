"""Overview endpoint — live plant status (SQL Server + Oracle merged)."""
import time
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_OVERVIEW, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.overview import OverviewData, OpenJobsData
from api.services.overview_service import get_overview, get_open_jobs

router = APIRouter(prefix='/api/v1', tags=['overview'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_OVERVIEW, maxsize=50)
async def _cached_overview(areas_key: Optional[tuple]):
    areas = list(areas_key) if areas_key else None
    return get_overview(areas)


@ttl_cache(ttl=CACHE_TTL_OVERVIEW, maxsize=50)
async def _cached_open_jobs(areas_key: Optional[tuple], job_type: Optional[str]):
    areas = list(areas_key) if areas_key else None
    return get_open_jobs(areas, job_type)


@router.get('/overview', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def overview(
    request: Request,
    areas: Optional[str] = Query(
        None,
        description="Comma-separated area codes (e.g. 'WB,DA,MOLD,ISO,FS'). Omit for all.",
        examples=['WB,DA'],
    ),
    key_info: dict = Depends(require_api_key),
):
    """Live plant overview: KPI counts + job_type status matrix.

    Cached for 60 seconds. Oracle (ISO/FS) merged automatically.
    """
    area_list = None
    if areas:
        area_list = tuple(sorted([a.strip().upper() for a in areas.split(',') if a.strip()]))

    t0 = time.time()
    data = await _cached_overview(area_list)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        status='ok',
        data=OverviewData(**data),
        meta=ResponseMeta(
            cached=_cached_overview.last_hit,
            query_time_ms=elapsed_ms if not _cached_overview.last_hit else 0,
        ),
    )


@router.get('/overview/open-jobs', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def open_jobs(
    request: Request,
    areas: Optional[str] = Query(None, description="Comma-separated area codes"),
    job_type: Optional[str] = Query(None, description="Filter by job_type, or 'ALL'"),
    key_info: dict = Depends(require_api_key),
):
    """Currently open jobs (Waiting + On Process) — SQL + Oracle merged. Cached 60s."""
    area_list = None
    if areas:
        area_list = tuple(sorted([a.strip().upper() for a in areas.split(',') if a.strip()]))

    import time as _time
    t0 = _time.time()
    data = await _cached_open_jobs(area_list, job_type)
    elapsed_ms = int((_time.time() - t0) * 1000)

    return APIResponse(
        data=OpenJobsData(**data),
        meta=ResponseMeta(
            cached=_cached_open_jobs.last_hit,
            query_time_ms=elapsed_ms if not _cached_open_jobs.last_hit else 0,
        ),
    )
