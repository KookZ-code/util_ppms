"""Run migration_store_item_issues.sql against MTHAI_ppm_db1."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dashboard'))

from sqlalchemy import text
from db import engine

SQL_FILE = os.path.join(os.path.dirname(__file__), 'migration_store_item_issues.sql')

def run():
    sql = open(SQL_FILE, encoding='utf-8').read()
    # Split on GO statements (T-SQL batch separator)
    batches = [b.strip() for b in sql.split('\nGO') if b.strip()]

    with engine.begin() as conn:
        for batch in batches:
            # Skip pure comment blocks
            lines = [l for l in batch.splitlines() if not l.strip().startswith('--')]
            if not any(lines):
                continue
            try:
                result = conn.execute(text(batch))
                # Print any PRINT output via rowcount hint
                print(f"  OK: {batch[:60].replace(chr(10),' ')!r}...")
            except Exception as e:
                print(f"  ERROR: {e}")
                raise

    print("\nVerifying table exists...")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT COUNT(*) AS n FROM information_schema.tables "
            "WHERE table_schema='dbo' AND table_name='store_item_issues'"
        )).fetchone()
        if row and row[0] == 1:
            print("  dbo.store_item_issues — EXISTS")
        else:
            print("  dbo.store_item_issues — NOT FOUND (check permissions)")

        row2 = conn.execute(text(
            "SELECT COUNT(*) AS n FROM information_schema.views "
            "WHERE table_schema='dbo' AND table_name='vw_store_item_monthly'"
        )).fetchone()
        if row2 and row2[0] == 1:
            print("  dbo.vw_store_item_monthly — EXISTS")
        else:
            print("  dbo.vw_store_item_monthly — NOT FOUND")

    print("\nMigration complete.")

if __name__ == '__main__':
    run()
