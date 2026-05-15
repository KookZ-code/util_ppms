# Store Item Dashboard — Implementation Plan

**Status:** Approved  
**Output:** `Output/store_item_dashboard.html`  
**Script:** `generate_store_item_dashboard.py` (project root)

---

## 1. Data Sources

| File | Sheets to read | Month labels | Header row |
|------|---------------|-------------|-----------|
| `Issue cost ASO 2025.xlsx` | Jan 2025, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov | Jan'25–Nov'25 | Varies per sheet (detect dynamically) |
| `SUM ISSUED ASSY Dec'25_MTHAI_&MMT.xlsx` | MTAI | Dec'25 | Row 3 (header=2) |
| `SUM ISSUED ASSY Jan'26_MTHAI_&MMT.xlsx` | MTHAI | Jan'26 | Row 2 (header=1) |
| `SUM ISSUED ASSY Feb'26_MTHAI_&MMT.xlsx` | MTHAI | Feb'26 | Row 2 (header=1) |
| `SUM ISSUED ASSY Mar'26_MTHAI_&MMT 3.xlsx` | MTHAI | Mar'26 | Row 2 (header=1) |
| `SUM ISSUED ASSY APR'26_MTHAI_&MMT.xlsx` | MTAI | Apr'26 | Row 1 (header=0) |

**Auto-discovery rule:** Script globs `SUM ISSUED ASSY *.xlsx` in `raw/Store item/` and parses month from filename. New monthly files are picked up automatically without code changes.

**Site:** MTHAI only throughout. MMT sheets are ignored.

---

## 2. Normalized Schema

All sources are normalized to these columns after loading:

| Column | Type | Notes |
|--------|------|-------|
| `Month` | str | e.g. "Jan'25", "Apr'26" |
| `Source` | str | "ASO2025" or "SUM_ASSY" — drives scope note |
| `Item` | str | stripped, cast to str |
| `Description` | str | stripped, remove `\xa0` and `\n` |
| `Process` | str | stripped |
| `Machine_model` | str | stripped |
| `Category` | str | stripped |
| `Quantity` | int | |
| `Cost` | float | unit cost (derived if absent: Total/Qty) |
| `Total` | float | only rows where Total > 0 kept |

**Schema detection for ASO 2025:** For each sheet, scan rows 0–2 to find the row containing "Item" or "Description" — use as header. Map column names flexibly (e.g. "Amount USD" → Total, "Item (child)" → Item, "Unit price" → Cost, "QTY" → Quantity).

---

## 3. Month Order

```
Jan'25, Feb'25, Mar'25, Apr'25, May'25, Jun'25,
Jul'25, Aug'25, Sep'25, Oct'25, Nov'25,
Dec'25, Jan'26, Feb'26, Mar'26, Apr'26
```

16 months total. Stored as `pd.Categorical` with this explicit order.

---

## 4. Script Structure (`generate_store_item_dashboard.py`)

```
1. load_aso2025()        — reads 11 sheets with dynamic schema detection
2. load_sum_assy()       — auto-discovers SUM ISSUED ASSY *.xlsx, reads MTHAI/MTAI sheet
3. normalize(df)         — maps to 10-column schema, filters Total > 0
4. build_chart_data(df)  — computes all JSON needed by charts
5. render_html(data)     — returns complete HTML string with embedded JSON
6. main()                — calls 1-5, writes Output/store_item_dashboard.html
```

No shared helpers with other project scripts — standalone as per project convention.

---

## 5. Dashboard Sections

### 5.1 Header (sticky)
- Dark blue `#1B3A5C`, title + subtitle showing actual date range

### 5.2 Filter Bar (sticky, below header)
- **Month** — multi-select chips (all selected by default)
- **Process** — dropdown, "All Processes" default
- **Category** — dropdown, "All Categories" default  
- **Search** — text input, matches Item number or Description

### 5.3 KPI Cards (4)
| Card | Value | Sub-line |
|------|-------|---------|
| Total Cost | sum(Total) of filtered data | date range shown |
| Latest Month Cost | sum of most recent month in filter | month label |
| MoM Change | % vs previous month | arrow + color (red=up, green=down) |
| Unique Items | count distinct Item | filtered |

### 5.4 Scope Note Banner
Yellow info banner between filter bar and KPIs:  
> "Jan–Nov 2025 data from ASO 2025 (narrower cost scope). Dec 2025 onwards from SUM ISSUED ASSY (full scope). Direct MoM comparison across this boundary may not be accurate."

Banner hides automatically if filter excludes all ASO2025 months.

### 5.5 Monthly Cost Trend (full width)
- Bar chart, 1 bar per month
- Color: `#2E75B6` for SUM_ASSY months, `#7AB3DE` (lighter blue) for ASO2025 months
- Visual divider line between Nov'25 and Dec'25
- Tooltip shows Month, Total, Source

### 5.6 Cost by Process + Cost by Machine (50/50)
- Both horizontal bar charts, top 10 each
- Computed from filtered records
- Updates when filters change

### 5.7 Detail Table (full width)
- Columns: Item | Description | Process | Machine | Month | Qty | Total Cost
- Sortable by any column (click header)
- Paginated: 50 rows/page
- Filtered by the global filter state
- Search matches Item or Description

---

## 6. JavaScript Architecture

All data is embedded as a single JSON blob (`const DATA = {...}`) in the HTML.

```
DATA = {
  records: [...],          // all rows, normalized
  filters: {
    months, processes,
    categories
  }
}
```

**Filter state** object drives all views:
```js
state = { months: Set, processes: Set, categories: Set, search: '' }
```

`applyFilters()` → recomputes aggregations from `DATA.records` → calls `chart.update()` on each Chart.js instance → re-renders table.

Charts use `chart.data.datasets[0].data = newValues; chart.update()` pattern — no full re-init on filter change.

---

## 7. Future Web Server Migration

When migrating to Flask/FastAPI:
- Move `load_aso2025()` + `load_sum_assy()` + `normalize()` to `store_item_loader.py`
- `build_chart_data()` becomes a `/api/store-items` GET endpoint
- HTML becomes a template (`templates/store_item_dashboard.html`)
- Filter state moves from JS-only to query params (`?months=Jan'25,Feb'25&process=Mold`)
- No changes to schema or aggregation logic

---

## 8. Output

`Output/store_item_dashboard.html` — single file, ~1–2 MB with embedded JSON.  
Chart.js loaded from CDN (`cdn.jsdelivr.net`). Requires internet for first open; can swap to local copy if needed.

---

## 9. Steps to Implement

- [ ] Step 1: Write `load_aso2025()` with dynamic schema detection, test all 11 sheets
- [ ] Step 2: Write `load_sum_assy()` with auto-discovery glob + month parser
- [ ] Step 3: Write `normalize()` and validate row counts match agent report
- [ ] Step 4: Write `build_chart_data()` — produce all JSON aggregations
- [ ] Step 5: Write HTML template string with Chart.js + filter JS
- [ ] Step 6: Wire filters → `applyFilters()` → all charts + table
- [ ] Step 7: Run script, open HTML, verify all 16 months appear correctly
- [ ] Step 8: Test edge case — filter to single month, search by item number
