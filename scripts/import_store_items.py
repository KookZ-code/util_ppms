"""Monthly importer: Excel → dbo.store_item_issues (MTHAI_ppm_db1)

Usage:
  python scripts/import_store_items.py                   # full reload all months
  python scripts/import_store_items.py --month "Apr'26"  # single month only
  python scripts/import_store_items.py --dry-run         # parse only, no DB writes
"""
import sys, io, os, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'dashboard'))

import pandas as pd
from sqlalchemy import text
from lib.store_item_loader import load_aso2025, load_sum_assy, normalize, MONTH_ORDER
from db import engine

# month_label → month_key (YYYY-MM, sortable)
MONTH_LABEL_TO_KEY = {}
for yy in ('25', '26'):
    for n, m in enumerate(['Jan','Feb','Mar','Apr','May','Jun',
                           'Jul','Aug','Sep','Oct','Nov','Dec'], 1):
        MONTH_LABEL_TO_KEY[f"{m}'{yy}"] = f"20{yy}-{n:02d}"


def to_db_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        'month_key':     df['Month'].astype(str).map(MONTH_LABEL_TO_KEY),
        'month_label':   df['Month'].astype(str),
        'source':        df['Source'].astype(str),
        'item_no':       df['Item'].astype(str).str.strip().str[:64],
        'description':   df['Description'].astype(str).str[:400],
        'process':       df['Process'].astype(str).str[:64],
        'machine_model': df['Machine_model'].astype(str).str[:128].replace('', None),
        'category':      df['Category'].astype(str).str[:32],
        'quantity':      df['Quantity'].fillna(0).astype(int),
        'unit_cost':     df['Cost'].fillna(0).round(4),
        'total_cost':    df['Total'].fillna(0).round(2),
        'source_file':   None,
    })
    return out.dropna(subset=['month_key'])


INSERT_SQL = text("""
    INSERT INTO dbo.store_item_issues
        (month_key, month_label, source, item_no, description, process,
         machine_model, category, quantity, unit_cost, total_cost, source_file)
    VALUES
        (:month_key, :month_label, :source, :item_no, :description, :process,
         :machine_model, :category, :quantity, :unit_cost, :total_cost, :source_file)
""")


def write_to_db(rows: pd.DataFrame, target_month_key: str | None = None):
    if rows.empty:
        print("  No rows to write.")
        return

    scope = rows if target_month_key is None else rows[rows['month_key'] == target_month_key]
    pairs = scope[['month_key','source']].drop_duplicates().itertuples(index=False)
    pairs = list(pairs)

    with engine.begin() as conn:
        total_deleted = 0
        for mk, src in pairs:
            res = conn.execute(text(
                "DELETE FROM dbo.store_item_issues "
                "WHERE month_key = :mk AND source = :src"
            ), {'mk': mk, 'src': src})
            total_deleted += res.rowcount

        # Use executemany via text() to avoid pandas.to_sql has_table() pyodbc bug
        records = scope.where(pd.notna(scope), None).to_dict(orient='records')
        conn.execute(INSERT_SQL, records)

        print(f"  Deleted {total_deleted} old rows, inserted {len(records)} new rows")


def verify(target_month_key: str | None = None):
    sql = """
        SELECT month_key, source, COUNT(*) AS rows, SUM(total_cost) AS total_cost
        FROM dbo.store_item_issues
        {where}
        GROUP BY month_key, source
        ORDER BY month_key, source
    """.format(where=f"WHERE month_key = '{target_month_key}'" if target_month_key else "")
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    print("\nDB verification:")
    print(df.to_string(index=False))
    print(f"\nTotal rows in table: {df['rows'].sum():,}  |  Total cost: ${df['total_cost'].sum():,.0f}")


def main():
    ap = argparse.ArgumentParser(description="Import store item Excel files into MTHAI_ppm_db1")
    ap.add_argument('--month',   help="Single month label e.g. \"Apr'26\"")
    ap.add_argument('--dry-run', action='store_true', help="Parse only, no DB writes")
    args = ap.parse_args()

    target_key = None
    if args.month:
        target_key = MONTH_LABEL_TO_KEY.get(args.month)
        if not target_key:
            sys.exit(f"Unknown month label: {args.month!r}. Expected format: \"Apr'26\"")
        print(f"Mode: single month  {args.month} ({target_key})")
    else:
        print("Mode: full reload (all months)")

    print("\n[1/4] Loading ASO 2025...")
    aso = load_aso2025()

    print("\n[2/4] Loading SUM ISSUED ASSY (MTHAI)...")
    sassy = load_sum_assy()

    print("\n[3/4] Normalizing...")
    df   = normalize(pd.concat([aso, sassy], ignore_index=True))
    rows = to_db_rows(df)
    print(f"  Ready: {len(rows)} rows across {rows['month_key'].nunique()} months")

    if args.dry_run:
        print("\n[DRY-RUN] First 10 rows:")
        print(rows.head(10).to_string(index=False))
        print("\nDry-run complete — no DB writes.")
        return

    print("\n[4/4] Writing to DB...")
    write_to_db(rows, target_key)
    verify(target_key)
    print("\nImport complete.")


if __name__ == '__main__':
    main()
