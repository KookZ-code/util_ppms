"""Inventory endpoints — shaped machine list + per-machine downtime KPIs."""
import time
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_MACHINES, CACHE_TTL_DEFAULT, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.services.inventory_service import (
    get_inventory_machines, get_inventory_downtime,
)

router = APIRouter(prefix='/api/v1/inventory', tags=['inventory'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_MACHINES, maxsize=5)
async def _cached_machines():
    return get_inventory_machines()


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=5)
async def _cached_downtime():
    return get_inventory_downtime()


@router.get('/machines', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def inventory_machines(
    request: Request,
    key_info: dict = Depends(require_api_key),
):
    """Shaped machine inventory (WB L/R heads replace bases, MOLD sub-machines
    filtered out, model names normalized). Cached 1 hour."""
    t0 = time.time()
    data = await _cached_machines()
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_machines.last_hit,
            query_time_ms=elapsed_ms if not _cached_machines.last_hit else 0,
        ),
    )


@router.get('/downtime', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def inventory_downtime(
    request: Request,
    key_info: dict = Depends(require_api_key),
):
    """Per-machine 7-day downtime KPIs for the treemap. Cached 5 min."""
    t0 = time.time()
    data = await _cached_downtime()
    elapsed_ms = int((time.time() - t0) * 1000)
    return APIResponse(
        data=data,
        meta=ResponseMeta(
            cached=_cached_downtime.last_hit,
            query_time_ms=elapsed_ms if not _cached_downtime.last_hit else 0,
        ),
    )
