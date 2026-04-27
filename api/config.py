"""API config — reuses dashboard .env + adds API-specific settings."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add dashboard/ to path so we can reuse its modules
_DASHBOARD = Path(__file__).parent.parent / 'dashboard'
sys.path.insert(0, str(_DASHBOARD))

load_dotenv(_DASHBOARD / '.env')

# API-specific settings
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))
API_TITLE = 'Machine Dashboard API'
API_VERSION = '1.0.0'
API_DESCRIPTION = 'Unified API for SQL Server + Oracle manufacturing data'

# Auth
API_KEY_HEADER = 'X-API-Key'
REQUIRE_AUTH = os.getenv('API_REQUIRE_AUTH', '1') == '1'

# CORS
CORS_ORIGINS = [o.strip() for o in os.getenv(
    'API_CORS_ORIGINS', 'http://localhost:8050,http://10.50.21.96:8050'
).split(',') if o.strip()]

# Rate limiting
DEFAULT_RATE_LIMIT = os.getenv('API_DEFAULT_RATE_LIMIT', '100/minute')

# Cache TTLs (seconds)
CACHE_TTL_OVERVIEW = 60
CACHE_TTL_DEFAULT = 300
CACHE_TTL_MACHINES = 3600
