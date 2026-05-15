# Store Inventory Usage Monitor — EMH Integration Plan

**Status:** Approved  
**Target page:** `/store-items`  
**Access:** `supervisor` + `admin` only  
**Update cadence:** Manual monthly import via CLI script  

---

## 1. Database Schema

Database: `MTHAI_ppm_db1` (existing EMH SQL Server connection via `db.py`)

### 1.1 Table: `dbo.store_item_issues`

```sql
IF OBJECT_ID('dbo.store_item_issues', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.store_item_issues (
        id              BIGINT IDENTITY(1,1) NOT NULL,
        month_key       CHAR(6)        NOT NULL,   -- '2025-01' (YYYY-MM, sortable)
        month_label     VARCHAR(8)     NOT NULL,   -- "Jan'25"  (display form)
        source          VARCHAR(16)    NOT NULL,   -- 'ASO2025' | 'SUM_ASSY'
        item_no         VARCHAR(64)    NOT NULL,
        description     NVARCHAR(400)  NULL,
        process         VARCHAR(64)    NOT NULL,
        machine_model   VARCHAR(128)   NULL,
        category        VARCHAR(32)    NOT NULL,   -- Emergency | JIT | Consumable | Consignment
        quantity        INT            NOT NULL DEFAULT 0,
        unit_cost       DECIMAL(18,4)  NOT NULL DEFAULT 0,
        total_cost      DECIMAL(18,2)  NOT NULL DEFAULT 0,
        source_file     VARCHAR(255)   NULL,
        loaded_at       DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT pk_store_item_issues PRIMARY KEY (id)
    );

    CREATE INDEX ix_sii_month       ON dbo.store_item_issues (month_key);
    CREATE INDEX ix_sii_process     ON dbo.store_item_issues (process)        INCLUDE (total_cost, quantity);
    CREATE INDEX ix_sii_category    ON dbo.store_item_issues (category)       INCLUDE (total_cost);
    CREATE INDEX ix_sii_item        ON dbo.store_item_issues (item_no)        INCLUDE (total_cost, quantity);
    CREATE INDEX ix_sii_machine     ON dbo.store_item_issues (machine_model)  INCLUDE (total_cost);
    CREATE INDEX ix_sii_month_proc  ON dbo.store_item_issues (month_key, process) INCLUDE (total_cost);
END
GO
```

### 1.2 Helper view

```sql
CREATE OR ALTER VIEW dbo.vw_store_item_monthly AS
SELECT
    month_key, month_label, process, category, machine_model,
    SUM(total_cost)         AS total_cost,
    SUM(quantity)           AS total_qty,
    COUNT(DISTINCT item_no) AS unique_items
FROM dbo.store_item_issues
GROUP BY month_key, month_label, process, category, machine_model;
GO
```

### 1.3 Re-import strategy

**Delete-then-insert by `(month_key, source)`** — re-running the same xlsx wipes stale rows for that month/source before inserting fresh ones. Safe for corrections without unique constraint.

---

## 2. Loader Refactor

Move shared loader logic out of `generate_store_item_dashboard.py` into a reusable module so both the HTML script and the DB import script can use it.

### 2.1 New file: `lib/store_item_loader.py`

Cut from `generate_store_item_dashboard.py` lines 22–236 and place here:
- Constants: `BASE`, `MONTH_ORDER`, `ASO_MONTHS`, `COL_MAP`, `TARGETS`, `PROCESS_MAP`, `CATEGORY_MAP`, `QTY_KEYS`, `SHEET_TO_MONTH`, `_MN`
- Functions: `map_cols()`, `detect_header()`, `parse_month()`, `load_aso2025()`, `load_sum_assy()`, `normalize()`

### 2.2 Update `generate_store_item_dashboard.py`

Replace the cut block with:
```python
from lib.store_item_loader import *
```
Verify HTML still generates: `python generate_store_item_dashboard.py`

---

## 3. Import Script — `scripts/import_store_items.py`

```
Usage:
  python scripts/import_store_items.py                     # full reload all months
  python scripts/import_store_items.py --month "Apr'26"    # single month
  python scripts/import_store_items.py --dry-run           # parse only, no DB writes
```

**Structure:**
1. `sys.path` setup to import from project root + `dashboard/` (for `db.py`)
2. Import `load_aso2025`, `load_sum_assy`, `normalize`, `MONTH_ORDER` from `lib.store_item_loader`
3. Import `engine` from `dashboard/db.py`
4. `MONTH_LABEL_TO_KEY` dict: maps `"Jan'25"` → `"2025-01"`, etc.
5. `to_db_rows(df)` — maps normalized DataFrame to exact DB columns
6. `write_to_db(rows, scope_months)` — delete-then-bulk-insert via SQLAlchemy
7. `main()` — argparse for `--month` and `--dry-run`

**Column mapping in `to_db_rows()`:**

| Loader column  | DB column      | Transform                  |
|---------------|----------------|----------------------------|
| `Month`       | `month_key`    | map via `MONTH_LABEL_TO_KEY` |
| `Month`       | `month_label`  | as-is string               |
| `Source`      | `source`       | as-is                      |
| `Item`        | `item_no`      | strip, slice 64            |
| `Description` | `description`  | slice 400                  |
| `Process`     | `process`      | slice 64                   |
| `Machine_model`| `machine_model`| slice 128, '' → None       |
| `Category`    | `category`     | slice 32                   |
| `Quantity`    | `quantity`     | int                        |
| `Cost`        | `unit_cost`    | round 4dp                  |
| `Total`       | `total_cost`   | round 2dp                  |

---

## 4. Changes to Existing Dashboard Files

### 4.1 `dashboard/auth.py` — PAGE_ACCESS

Add `/store-items` to `admin` and `supervisor` only:

```python
PAGE_ACCESS = {
    'admin':      {...existing..., '/store-items', '/admin'},
    'supervisor': {...existing..., '/store-items'},
    'viewer':     {...existing...},   # no /store-items
}
```

### 4.2 `dashboard/app.py` — NAV_LINKS

Insert before Admin entry:
```python
('Store Items', '/store-items'),
```
`build_navbar()` already filters by role — no other change needed.

---

## 5. Page — `dashboard/pages/store_items.py`

### 5.1 Registration

```python
dash.register_page(__name__, path='/store-items', name='Store Items')
```

### 5.2 Layout structure

```
make_page_header("Store Inventory Usage Monitor")
├── Filter bar (sticky)
│   ├── From Month dropdown     id=si-from-month
│   ├── To Month dropdown       id=si-to-month   (default: last 12 months)
│   ├── Process multi-dropdown  id=si-filter-process
│   ├── Category multi-dropdown id=si-filter-category
│   ├── Search input (debounce) id=si-search
│   └── Reset button            id=si-reset
├── KPI row                     id=si-kpi-row
│   ├── Total Cost   (PRIMARY_BLUE)
│   ├── Latest Month (LIGHT_BLUE)
│   ├── MoM Change   (RED/GREEN)
│   └── Unique Items (GREEN)
├── Monthly Cost Trend          id=si-trend-chart
│   └── go.Bar, x=month_label, y=total_cost, text=fmtK labels, marker_color=PRIMARY_BLUE
├── 2-column row
│   ├── Cost by Process         id=si-process-chart
│   │   └── go.Bar stacked horizontal, top 10 process × CAT_ORDER, CAT_COLORS
│   └── Cost by Machine         id=si-machine-chart
│       └── go.Bar horizontal, top 10 machine_model, marker_color=ORANGE
├── Detail Table
│   ├── Export CSV button       id=btn-si-export
│   ├── dcc.Download            id=si-download
│   └── dash_table.DataTable    id=si-table (50/page, sortable, filterable)
└── dcc.Store(id=si-data-cache, storage_type='memory')
```

### 5.3 Callbacks

| # | Inputs | Outputs | Purpose |
|---|--------|---------|---------|
| 1 | `auto-refresh` (Interval) | filter dropdown `options`+`value` | Populate month/process/category options on load |
| 2 | `si-from-month`, `si-to-month`, `si-filter-process`, `si-filter-category`, `si-search` | KPI row, 3 charts, table data, `si-data-cache` | Main filter → rebuild everything |
| 3 | `si-reset` (n_clicks) | reset all filter values to default | Reset to last 12 months |
| 4 | `btn-si-export` (n_clicks) + `si-data-cache` | `si-download` | CSV export of current filtered data |

### 5.4 Category colors (mirrors HTML dashboard)

```python
CAT_COLORS = {
    'Emergency':   RED,        # #C0392B
    'JIT':         ORANGE,     # #E67E22
    'Consumable':  LIGHT_BLUE, # #2E75B6
    'Consignment': GREEN,      # #2D8E4E
}
CAT_ORDER = ['Emergency', 'JIT', 'Consumable', 'Consignment']
```

---

## 6. Implementation Checklist

### Phase A — Database
- [ ] Run `CREATE TABLE dbo.store_item_issues` (section 1.1) on `MTHAI_ppm_db1`
- [ ] Run `CREATE VIEW dbo.vw_store_item_monthly` (section 1.2)
- [ ] Grant `SELECT` to dashboard SQL login; `INSERT, DELETE` to import login
- [ ] Verify indexes: `sp_helpindex 'dbo.store_item_issues'`

### Phase B — Loader refactor
- [ ] Create `D:\claude\Project\lib\__init__.py` (empty)
- [ ] Create `D:\claude\Project\lib\store_item_loader.py` (move code from generator)
- [ ] Update `generate_store_item_dashboard.py` → `from lib.store_item_loader import *`
- [ ] Verify: `python generate_store_item_dashboard.py` still works

### Phase C — Import script
- [ ] Create `D:\claude\Project\scripts\__init__.py` (empty)
- [ ] Create `D:\claude\Project\scripts\import_store_items.py` (section 3)
- [ ] Test dry-run: `python scripts\import_store_items.py --dry-run`
- [ ] Full load: `python scripts\import_store_items.py`
- [ ] Verify in DB: `SELECT month_key, source, COUNT(*), SUM(total_cost) FROM dbo.store_item_issues GROUP BY month_key, source ORDER BY 1,2`

### Phase D — Auth & navigation
- [ ] Edit `dashboard/auth.py` — add `/store-items` to admin + supervisor PAGE_ACCESS
- [ ] Edit `dashboard/app.py` — insert `('Store Items', '/store-items')` in NAV_LINKS

### Phase E — Dash page
- [ ] Create `dashboard/pages/store_items.py` (section 5)
- [ ] Smoke test: `python dashboard\app.py`, login as supervisor → `/store-items`
- [ ] Verify nav link hidden for viewer role
- [ ] Verify redirect to `/` for anonymous/viewer hitting `/store-items` directly
- [ ] Test all 4 KPI cards, 3 charts, table pagination, Reset, Export CSV

### Phase F — Monthly refresh workflow
- [ ] Drop new `SUM ISSUED ASSY <Mon>'<YY>_*.xlsx` into `raw/Store item/`
- [ ] Run: `python scripts\import_store_items.py --month "<Mon>'<YY>"`
- [ ] Verify new month appears in `/store-items` dropdown and KPIs update

---

## 7. Risk & Trade-offs

| Item | Note |
|------|------|
| **Query performance** | Re-query on every callback is fine at ~200K rows. If table grows >1M, add TTL cache in `_load_store_items()` keyed on `MAX(loaded_at)` |
| **`month_key` vs `month_label`** | Both stored intentionally — `month_key` sorts correctly in SQL, `month_label` matches existing HTML dashboard display for visual continuity |
| **Idempotency** | Delete-by-(month_key, source) before insert — re-running same month is safe |
| **Access control** | Both `PAGE_ACCESS` dict (nav hide) and `before_request` hook (server redirect) enforce gating — defense in depth |
| **`generate_store_item_dashboard.py`** | HTML script continues to work after loader refactor; standalone HTML still useful for ad-hoc sharing |
