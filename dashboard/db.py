import pandas as pd
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus
from config import DB_CONFIG


def _resolve_driver(requested: str) -> str:
    """Return the configured driver if available, else pick a best-fit
    installed Microsoft ODBC driver. Raises with a helpful message if no
    SQL Server driver is installed.
    """
    try:
        import pyodbc
        available = set(pyodbc.drivers())
    except Exception:
        return requested or 'SQL Server'

    # Exact match first
    if requested and requested in available:
        return requested

    # Try modern drivers in descending preference
    preferences = [
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server',
        'SQL Server Native Client 11.0',
        'SQL Server',
    ]
    for drv in preferences:
        if drv in available:
            return drv

    # Nothing — surface a clear error on first use
    raise RuntimeError(
        f"No Microsoft ODBC driver found. Configured driver "
        f"'{requested}' not installed. Available drivers: {sorted(available)}. "
        f"Install 'ODBC Driver 17 or 18 for SQL Server' from "
        f"https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server"
    )


_driver = _resolve_driver(DB_CONFIG.get('driver', 'SQL Server'))

# Driver 18 defaults to Encrypt=yes and validates TLS cert — append
# TrustServerCertificate=yes so we don't require an internal CA cert on
# the SQL Server host. Driver 17 defaults to Encrypt=no so no flag needed.
_extra = ''
if 'ODBC Driver 18' in _driver:
    _extra = '&TrustServerCertificate=yes&Encrypt=optional'

_connection_string = (
    f"mssql+pyodbc://{DB_CONFIG['username']}:{quote_plus(DB_CONFIG['password'])}"
    f"@{DB_CONFIG['server']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?driver={quote_plus(_driver)}{_extra}"
)

engine = create_engine(
    _connection_string,
    pool_size=15,
    max_overflow=25,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)


def query_df(sql, params=None):
    """Execute SQL and return a pandas DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def get_columns(table_name):
    """Return list of column dicts for a table/view."""
    insp = inspect(engine)
    return insp.get_columns(table_name)


def test_connection():
    """Test database connectivity. Returns True or raises."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
