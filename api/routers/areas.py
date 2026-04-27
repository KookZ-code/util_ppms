"""Areas endpoint — list of areas merged from SQL + Oracle."""
import time
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import require_api_key
from api.cache import ttl_cache
from api.config import CACHE_TTL_MACHINES, DEFAULT_RATE_LIMIT
from api.schemas.common import APIResponse, ResponseMeta
from api.schemas.area import AreaListData
from api.services.areas_service import get_areas

router = APIRouter(prefix='/api/v1', tags=['areas'])
limiter = Limiter(key_func=get_remote_address)


@ttl_cache(ttl=CACHE_TTL_MACHINES, maxsize=5)
async def _cached():
    return get_areas()


@router.get('/areas', response_model=APIResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def areas(request: Request, key_info: dict = Depends(require_api_key)):
    """List all areas (SQL + Oracle merged). Cached 1 hour."""
    t0 = time.time()
    data = await _cached()
    elapsed_ms = int((time.time() - t0) * 1000)

    return APIResponse(
        data=AreaListData(**data),
        meta=ResponseMeta(
            cached=_cached.last_hit,
            query_time_ms=elapsed_ms if not _cached.last_hit else 0,
        ),
    )
