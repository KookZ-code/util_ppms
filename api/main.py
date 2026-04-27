"""FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000

Or for production:
    gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.config import (
    API_TITLE, API_VERSION, API_DESCRIPTION,
    CORS_ORIGINS, DEFAULT_RATE_LIMIT,
)
from api.schemas.common import ErrorResponse, ErrorDetail

STATIC_DIR = Path(__file__).parent / 'static'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
log = logging.getLogger('api')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure API keys table exists. Shutdown: no-op."""
    log.info(f"Starting {API_TITLE} v{API_VERSION}")
    try:
        from api.auth import ensure_api_keys_table
        ensure_api_keys_table()
        log.info("api_keys table ready")
    except Exception as e:
        log.error(f"Failed to init api_keys table: {e}")

    try:
        from config import ORA_ENABLED
        if ORA_ENABLED:
            from oracle_db import _ensure_loaded
            _ensure_loaded()
            log.info("Oracle background loader triggered")
    except Exception as e:
        log.warning(f"Oracle loader not started: {e}")

    yield
    log.info("Shutting down API")


limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url=None,       # override — use offline version below
    redoc_url=None,      # override — use offline version below
    openapi_url='/openapi.json',
)

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/docs', include_in_schema=False)
async def swagger_ui_offline():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{API_TITLE} - Swagger UI",
        swagger_js_url='/static/swagger-ui-bundle.js',
        swagger_css_url='/static/swagger-ui.css',
    )


@app.get('/redoc', include_in_schema=False)
async def redoc_offline():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{API_TITLE} - ReDoc",
        redoc_js_url='/static/redoc.standalone.js',
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'DELETE'],
    allow_headers=['*'],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code='INTERNAL_ERROR',
                message=str(exc) or 'Internal server error',
            )
        ).model_dump(),
    )


# Routers
from api.routers import (
    health, overview, utilization, downtime, machines, tech, areas,
)
app.include_router(health.router)
app.include_router(overview.router)
app.include_router(utilization.router)
app.include_router(downtime.router)
app.include_router(machines.router)
app.include_router(tech.router)
app.include_router(areas.router)


@app.get('/', include_in_schema=False)
async def root():
    return {
        'name': API_TITLE,
        'version': API_VERSION,
        'docs': '/docs',
        'health': '/api/v1/health',
    }
