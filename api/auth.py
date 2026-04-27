"""API Key authentication — bcrypt hashed keys stored in SQL Server."""
import secrets
import logging
from fastapi import HTTPException, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy import text

from api.config import API_KEY_HEADER, REQUIRE_AUTH

log = logging.getLogger(__name__)

api_key_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _hash_key(key: str) -> str:
    """Hash an API key with bcrypt."""
    import bcrypt
    return bcrypt.hashpw(key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its bcrypt hash."""
    import bcrypt
    try:
        return bcrypt.checkpw(key.encode('utf-8'), key_hash.encode('utf-8'))
    except Exception:
        return False


def generate_api_key(prefix: str = 'mch') -> str:
    """Generate a new API key. Format: mch_<32 url-safe chars>."""
    token = secrets.token_urlsafe(24)
    return f"{prefix}_{token}"


def ensure_api_keys_table():
    """Create dbo.api_keys table if not exists."""
    from db import engine
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME = 'api_keys'"
        ))
        if result.scalar() == 0:
            conn.execute(text("""
                CREATE TABLE dbo.api_keys (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    key_hash NVARCHAR(200) NOT NULL,
                    name NVARCHAR(100) NOT NULL,
                    scopes NVARCHAR(500) DEFAULT '*',
                    rate_limit_per_min INT DEFAULT 100,
                    enabled BIT DEFAULT 1,
                    created_at DATETIME DEFAULT GETDATE(),
                    last_used_at DATETIME NULL
                )
            """))
            # Insert default dev key
            dev_key = 'mch_dev_12345'
            conn.execute(text(
                "INSERT INTO dbo.api_keys (key_hash, name, scopes) "
                "VALUES (:hash, :name, :scopes)"
            ), {'hash': _hash_key(dev_key), 'name': 'Development', 'scopes': '*'})
            conn.commit()
            print(f"Created api_keys table with default dev key: {dev_key}")


def lookup_api_key(provided_key: str):
    """Find a matching API key in DB. Returns dict or None."""
    if not provided_key:
        return None
    from db import query_df
    # Bcrypt verify is slow — fetch all enabled keys and loop
    df = query_df(
        "SELECT id, key_hash, name, scopes, rate_limit_per_min "
        "FROM dbo.api_keys WHERE enabled = 1"
    )
    if df.empty:
        return None
    for _, row in df.iterrows():
        if _verify_key(provided_key, row['key_hash']):
            return dict(row)
    return None


async def require_api_key(api_key: str = Depends(api_key_scheme)):
    """FastAPI dependency: validate API key, return key info."""
    if not REQUIRE_AUTH:
        return {'id': 0, 'name': 'dev-no-auth', 'scopes': '*', 'rate_limit_per_min': 1000}

    if not api_key:
        raise HTTPException(status_code=401, detail={
            'code': 'MISSING_API_KEY',
            'message': f'Provide API key in {API_KEY_HEADER} header'
        })

    key_info = lookup_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail={
            'code': 'INVALID_API_KEY',
            'message': 'API key is invalid or disabled'
        })

    # Update last_used_at (fire-and-forget)
    try:
        from db import engine
        with engine.connect() as conn:
            conn.execute(text("UPDATE dbo.api_keys SET last_used_at = GETDATE() WHERE id = :id"),
                         {'id': key_info['id']})
            conn.commit()
    except Exception as e:
        log.warning(f"Failed to update last_used_at: {e}")

    return key_info
