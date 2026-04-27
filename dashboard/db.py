import pandas as pd
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus
from config import DB_CONFIG

_connection_string = (
    f"mssql+pyodbc://{DB_CONFIG['username']}:{quote_plus(DB_CONFIG['password'])}"
    f"@{DB_CONFIG['server']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?driver={quote_plus(DB_CONFIG['driver'])}"
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
