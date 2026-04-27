"""Utilization endpoint."""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_DEFAULT, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.utilization import UtilizationData
from api.services.utilization_service import (
    get_utilization, get_utilization_detail,
    get_by_machine, get_attention_machines,
)

router = APIRouter(prefix='/api/v1', tags=['utilization'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached(start: str, end: str, areas_key, shift):
    areas = list(areas_key) if areas_key else None
    return get_utilization(start, end, areas, shift)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached_detail(start, end, areas_key, shift, selected_month):
    areas = list(areas_key) if areas_key else None
    return get_utilization_detail(start, end, areas, shift, selected_month)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached_by_machine(start, end, areas_key, shift):
    areas = list(areas_key) if areas_key else None
    return get_by_machine(start, end, areas, shift)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=100)
async def _cached_attention(start, end, areas_key, shift):
    areas = list(areas_key) if areas_key else None
    return get_attention_machines(start, end, areas, shift)


@router.get('/utilization', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def utilization(
    request: Request,
    start: str = Query(..., description='Start date YYYY-MM-DD'),
    end: str = Query(..., description='End date YYYY-MM-DD (inclusive)'),
    areas: Optional[str] = Query(None, description='Comma-separated area codes'),
    shift: Optional[str] = Query(None, description="'DAY' | 'NIGHT' | None"),
    key_info: dict = Depends(require_api_key),
):
    """% utilization, downtime, lost time across areas. Cached 5 min."""
    area_tuple = None
    if areas:
        area_tuple = tuple(sorted([a.strip().upper() for a in areas.split(',') if a.strip()]))
    shift_up = shift.upper() if shift else None
    if shift_up and shift_up not in ('DAY', 'NIGHT'):
        shift_up = None

    t0 = time.time()
    data = await _cached(start, end, area_tuple, shift_up)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=UtilizationData(**data),
        meta=ResponseMeta(
            cached=_cached.last_hit,
            query_time_ms=elapsed_ms if not _cached.last_hit else 0,
        ),
    )


def _areas_tuple(areas: Optional[str]):
    if not areas:
        return None
    return tuple(sorted([a.strip().upper() for a in areas.split(',') if a.strip()]))


def _shift_norm(shift: Optional[str]):
    s = shift.upper() if shift else None
    return s if s in ('DAY', 'NIGHT') else None


@router.get('/utilization/detail')
@limiter.limit(DEFAULT_RATE_LIMIT)
async def utilization_detail(
    request: Request,
    start: str = Query(..., description='Start date YYYY-MM-DD'),
    end: str = Query(..., description='End date YYYY-MM-DD (inclusive)'),
    areas: Optional[str] = Query(None, description='Comma-separated area codes'),
    shift: Optional[str] = Query(None, description="'DAY' | 'NIGHT' | None"),
    selected_month: Optional[str] = Query(None, description="YYYY-MM for drill-down"),
    key_info: dict = Depends(require_api_key),
):
    """Full utilization payload: kpi + prev_kpi + by_area + monthly_trend +
    scatter + top_down + top_lost + machines_per_cause. Cached 5 min."""
    t0 = time.time()
    data = await _cached_detail(start, end, _areas_tuple(areas),
                                 _shift_norm(shift), selected_month)
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_detail.last_hit,
            query_time_ms=elapsed_ms if not _cached_detail.last_hit else 0,
        ),
    )


@router.get('/utilization/by-machine')
@limiter.limit(DEFAULT_RATE_LIMIT)
async def by_machine(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    areas: Optional[str] = Query(None),
    shift: Optional[str] = Query(None),
    key_info: dict = Depends(require_api_key),
):
    """Per-machine util breakdown. Cached 5 min."""
    t0 = time.time()
    data = await _cached_by_machine(start, end, _areas_tuple(areas), _shift_norm(shift))
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_by_machine.last_hit,
            query_time_ms=elapsed_ms if not _cached_by_machine.last_hit else 0,
        ),
    )


@router.get('/utilization/attention')
@limiter.limit(DEFAULT_RATE_LIMIT)
async def attention(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    areas: Optional[str] = Query(None),
    shift: Optional[str] = Query(None),
    key_info: dict = Depends(require_api_key),
):
    """Top machines needing attention. Cached 5 min."""
    t0 = time.time()
    data = await _cached_attention(start, end, _areas_tuple(areas), _shift_norm(shift))
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_attention.last_hit,
            query_time_ms=elapsed_ms if not _cached_attention.last_hit else 0,
        ),
    )
