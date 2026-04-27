"""Machines endpoint — master list + detail."""
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_MACHINES, CACHE_TTL_DEFAULT, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.machine import MachineListData, MachineDetailData
from api.services.machines_service import get_machines, get_machine_detail

router = APIRouter(prefix='/api/v1/machines', tags=['machines'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_MACHINES, maxsize=20)
async def _cached_list(area, key_only):
    return get_machines(area, key_only)


@ttl_cache(ttl=CACHE_TTL_DEFAULT, maxsize=200)
async def _cached_detail(machine_id, recent_limit):
    return get_machine_detail(machine_id, recent_limit)


@router.get('', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def list_machines(
    request: Request,
    area: Optional[str] = Query(None, description='Filter by area code'),
    key_only: bool = Query(False, description='Only key machines (flag_key=1)'),
    key_info: dict = Depends(require_api_key),
):
    """Machine master list from dbo.machine. Cached 1 hour."""
    t0 = time.time()
    data = await _cached_list(area, key_only)
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=MachineListData(**data),
        meta=ResponseMeta(
            cached=_cached_list.last_hit,
            query_time_ms=elapsed_ms if not _cached_list.last_hit else 0,
        ),
    )


async def _build_detail_response(machine_id: str, recent_limit: int):
    t0 = time.time()
    data = await _cached_detail(machine_id, recent_limit)
    elapsed_ms = int((time.time() - t0) * 1000)
    if data is None:
        raise HTTPException(status_code=404, detail={
            'code': 'NOT_FOUND',
            'message': f"Machine '{machine_id}' not found",
        })
    return APIResponse(
        data=MachineDetailData(**data),
        meta=ResponseMeta(
            cached=_cached_detail.last_hit,
            query_time_ms=elapsed_ms if not _cached_detail.last_hit else 0,
        ),
    )


@router.get('/detail', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def machine_detail_by_query(
    request: Request,
    id: str = Query(..., description='Machine ID (supports / and # via query param)'),
    recent_limit: int = Query(20, ge=1, le=100),
    key_info: dict = Depends(require_api_key),
):
    """Alternative: machine detail via ?id=... query param (avoids URL path issues with '/' in IDs)."""
    return await _build_detail_response(id, recent_limit)


@router.get('/{machine_id:path}', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def machine_detail(
    request: Request,
    machine_id: str,
    recent_limit: int = Query(20, ge=1, le=100),
    key_info: dict = Depends(require_api_key),
):
    """Single-machine detail + recent events. Cached 5 min.

    For IDs containing '/' use GET /machines/detail?id=... instead.
    """
    return await _build_detail_response(machine_id, recent_limit)
