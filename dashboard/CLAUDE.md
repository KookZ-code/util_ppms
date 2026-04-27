# CLAUDE.md — Machine Utilization & Downtime Dashboard

This file defines the design system, architecture, and conventions for the Dash web dashboard.
Follow these rules exactly when adding pages, components, or modifying the UI.

---

## Project Structure

```
dashboard/
├── app.py                  # Dash app, navbar, global callbacks
├── config.py               # Loads .env → DB_CONFIG, COLUMN_MAP, settings
├── db.py                   # SQLAlchemy engine, query_df(), test_connection()
├── schema_discovery.py     # One-time tool to discover DB column names
├── assets/
│   ├── styles.css          # Global CSS (only file — no inline styles for layout)
│   └── microchip_logo.jpg
├── components/
│   ├── data_table.py       # make_data_table()
│   ├── filters.py          # make_filter_bar()
│   ├── header.py           # make_page_header()
│   └── kpi_card.py         # make_kpi_card()
├── pages/
│   ├── overview.py         # / — KPI cards, donut, gauge, area bar
│   ├── utilization.py      # /utilization — gauges, trend, top causes
│   ├── downtime.py         # /downtime — pareto, by-machine, table
│   ├── machine_detail.py   # /machine-detail — drill-down per machine
│   └── timeline.py         # /timeline — swimlane Gantt chart
└── utils/
    ├── colors.py           # Color constants (SINGLE SOURCE OF TRUTH)
    ├── queries.py          # SQL query builder functions
    └── transforms.py       # Pandas aggregation helpers
```

---

## Color Palette (`utils/colors.py`)

Always import colors from `utils/colors.py`. Never hardcode hex values in page or component files.

| Constant        | Hex       | Usage                                      |
|-----------------|-----------|--------------------------------------------|
| `PRIMARY_BLUE`  | `#0E3689` | Navbar, headers, primary actions           |
| `LIGHT_BLUE`    | `#1D9CE4` | Secondary charts, SETUP job type           |
| `GREEN`         | `#5EBF33` | Running/good status, utilization bars      |
| `ORANGE`        | `#FD7F20` | Warning, idle, FACILITY DOWN, lost time    |
| `RED`           | `#CC0000` | Down/critical, M/C DOWN, ENGINEERING DOWN  |
| `PURPLE`        | `#702076` | PM, planned maintenance                    |
| `YELLOW`        | `#FFD53A` | CONVERT job type, highlights               |
| `WHITE`         | `#FFFFFF` | Card backgrounds, chart backgrounds        |
| `BG_GRAY`       | `#F7F7F7` | Page background, alternating table rows    |
| `MED_GRAY`      | `#8A8A8A` | Subtitle text, empty state messages        |
| `LIGHT_GRAY`    | `#D9D9D9` | Borders, dividers                          |

### Job Type Color Mapping (`JOB_TYPE_COLORS`)

Maps `job_type` column values from `vw_job_nokey` to display colors:

| job_type              | Color         |
|-----------------------|---------------|
| `M/C DOWN`            | RED           |
| `ENGINEERING DOWN`    | `#990000`     |
| `FACILITY DOWN`       | ORANGE        |
| `PM`                  | PURPLE        |
| `SETUP`               | LIGHT_BLUE    |
| `SETUP BY OPERATOR`   | `#17A2B8`     |
| `CONVERT`             | YELLOW        |
| `CLEAN MOLD`          | GREEN         |
| `CHANGE CAP`          | MED_GRAY      |

### Job Type Groupings (utilization.py)

```python
DOWN_TYPES = ('M/C DOWN',)
PM_TYPES   = ('PM',)
LOST_TYPES = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD', 'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN')
# Utilization % = 100 - DOWN% - PM% - LOST%
```

**Utilization Formula (Calendar-Based)**
```
available_min = machine_count × days_in_range × hours_per_day × 60
  - hours_per_day = 12 for Day/Night shift, 24 for All Shifts
  - machine_count = COUNT(DISTINCT code_machine) from vw_job_nokey in the period

down_min = SUM DATEDIFF(datex, date_close) for M/C DOWN         ← repair time only
pm_min   = SUM DATEDIFF(datex, date_close) for PM
lost_min = SUM DATEDIFF(datex, date_close) for LOST_TYPES
         + SUM(Waiting_time) for ALL records                     ← waiting for tech → Lost

util_pct = (available_min − down_min − pm_min − lost_min) / available_min × 100
```

**Waiting_time** (int column, minutes) = `DATEDIFF(date_act, datex)` = time waiting for technician.
Added to **Lost Time** (not Downtime), because machine is waiting but not being repaired.

### Shift Definition

| Shift | Hours | Example for "Apr 16" |
|---|---|---|
| Day   | 07:00 – 18:59 | Apr 16 07:00 → Apr 16 18:59 |
| Night | 19:00 – 06:59 | Apr 15 19:00 → Apr 16 06:59 |

**Shift date assignment** (night shift spans midnight):
```sql
-- shift_date: which "shift day" this event belongs to
CASE WHEN DATEPART(HOUR, datex) >= 19
     THEN DATEADD(DAY, 1, CAST(datex AS DATE))  -- evening → next day's night shift
     ELSE CAST(datex AS DATE)                     -- morning/day → same day
END

-- shift_name
CASE WHEN DATEPART(HOUR, datex) BETWEEN 7 AND 18
     THEN 'Day' ELSE 'Night'
END
```

**Filter condition** (for WHERE clause):
```sql
-- Day shift filter
DATEPART(HOUR, datex) BETWEEN 7 AND 18
-- Night shift filter
DATEPART(HOUR, datex) NOT BETWEEN 7 AND 18
```

---

## Page Layout Pattern

Every page follows this structure:

```python
layout = html.Div([
    make_page_header("Page Title", subtitle="Optional subtitle"),

    make_filter_bar(show_machine=False),   # optional — include on pages with filters

    # Row 1: KPI gauges or KPI cards (dbc.Row with id for callback output)
    dbc.Row(id='page-kpi-row', className='g-3 mb-4'),

    # Row 2+: Charts in dbc.Row > dbc.Col layout
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div("Chart Title", className='chart-title'),
                dcc.Graph(id='chart-id', config={'displayModeBar': False}),
            ], className='chart-card'),
        ], lg=7, md=12),
        dbc.Col([...], lg=5, md=12),
    ]),

], className='page-container')
```

### CSS Classes (defined in `assets/styles.css`)

| Class             | Element                              |
|-------------------|--------------------------------------|
| `.page-container` | Outermost `html.Div` of every page   |
| `.page-header`    | Output of `make_page_header()`       |
| `.chart-card`     | White card wrapping a chart or table |
| `.chart-title`    | `html.Div` title inside chart-card   |
| `.filter-bar`     | Output of `make_filter_bar()`        |
| `.kpi-card`       | Output of `make_kpi_card()`          |
| `.kpi-accent`     | Colored top bar of KPI card (5px)    |
| `.kpi-value`      | Large number in KPI card (32px bold) |
| `.kpi-label`      | Label text under value (13px)        |
| `.refresh-info`   | Timestamp text, bottom-right         |

**Do not add new CSS classes without adding them to `assets/styles.css` first.**

---

## Components

### `make_page_header(title, subtitle=None)`
Dark blue (`#0E3689`) header bar at top of every page.

### `make_filter_bar(show_date=True, show_area=True, show_machine=True)`
Creates filter bar with Date Range picker, Area dropdown, Machine dropdown.
- Component IDs: `filter-date-range`, `filter-area`, `filter-machine`
- **`filter-area` options are loaded by a single global callback in `app.py`** — do not add another `Output('filter-area', 'options')` callback in any page file (causes Duplicate callback error).
- Default date range: last 30 days

### `make_kpi_card(value, label, accent_color, subtitle=None)`
White card with colored top accent bar. Use for numeric KPIs in a `dbc.Row`.

### `make_data_table(df, table_id, page_size=15, status_col=None)`
Styled `dash_table.DataTable` with blue header, sortable, filterable.

---

## Plotly Chart Conventions

All charts must use these layout settings:

```python
fig.update_layout(
    template='plotly_white',
    paper_bgcolor=WHITE,
    plot_bgcolor=WHITE,
    font=dict(family='Calibri, Segoe UI, sans-serif'),
    margin=dict(t=10, b=40, l=50, r=10),
    height=320,   # adjust per chart type
)
```

### Chart Heights by Type

| Chart type              | Height  |
|-------------------------|---------|
| KPI Gauge               | 190 px  |
| Donut / Pie             | 320 px  |
| Bar (horizontal)        | 220 px  |
| Bar (vertical, monthly) | 350 px  |
| Heatmap                 | 300 px  |
| Swimlane / Gantt        | dynamic (`machines × 28 + 120`, min 420) |
| Timeline scatter        | 200 px  |

### Gauge KPI (`go.Indicator`)

```python
go.Indicator(
    mode='gauge+number',
    value=value,
    number={'suffix': '%', 'font': {'size': 28, 'color': color, 'family': '...'}},
    gauge={
        'axis': {'range': [0, max_val]},
        'bar': {'color': color, 'thickness': 0.3},
        'bgcolor': WHITE,
        'borderwidth': 0,
        'steps': [{'range': [0, max_val], 'color': '#F0F0F0'}],
    },
)
```

Scale ranges: Utilization=100, Downtime=20, PM=10, LostTime=30

---

## Database

### Connection
Configured via `.env` → `config.py` → `db.py`. Uses SQLAlchemy with connection pooling (pool_size=5).

```python
from db import query_df
df = query_df("SELECT ...", params={'key': value})  # params = SQLAlchemy named params
```

### View: `vw_job_nokey`

Primary data source. Column mapping is configured in `.env` via `COL_*` variables.

| COLUMN_MAP key      | Actual column   | Description                                        |
|---------------------|-----------------|----------------------------------------------------|
| `machine_id`        | `code_machine`  | Human-readable machine name (D/B #001)             |
| `machine_name`      | `code_machine`  | Same as machine_id                                 |
| `machine_area`      | `id_operation`  | Operation code: DA, WB, SAW, MOLD…                |
| `status`            | `job_type`      | Activity type (M/C DOWN, SETUP, PM…)               |
| `downtime_reason`   | `cause`         | Technician-diagnosed root cause                    |
| `symptom`           | `des_job`       | Operator-reported symptom/problem (73% differs from cause for M/C DOWN) |
| `opr_start_time`    | `datex`         | Operator opens job — machine reported down         |
| `tech_start_time`   | `date_ack`      | Technician acknowledges & starts repair            |
| `end_time`          | `date_close`    | Job closed — repair complete                       |
| `job_id`            | `id_job`        | Unique job record ID                               |

**Timestamp flow:**
```
datex ──[Waiting Time]──► date_ack ──[Repair Time]──► date_close
  │                            │                           │
Operator reports            Tech starts                Job closed
machine down                repair                     (repaired)

Waiting_time (DB col) = DATEDIFF(MINUTE, datex,    date_ack)   ← waiting for tech
Repair_time  (DB col) = DATEDIFF(MINUTE, date_ack, date_close) ← actual repair
Total downtime        = DATEDIFF(MINUTE, datex,    date_close)
```

**Downtime** = `Repair_time` = `date_ack → date_close`
**Lost Time** includes `Waiting_time` = `datex → date_ack`

### Target Utilization % per Area

Configured in `.env` as `AREA_TARGETS=BG:85,DA:80,...` → parsed into `config.AREA_TARGETS` dict.

| Area | Target % |
|------|----------|
| BG, SAW, WB, MOLD, MARK, PLATE, TF, SAW_QFN | 85% |
| DA | 80% |

Color logic: ≥ target = Green, ≥ target−10 = Orange, < target−10 = Red

### id_operation Values (Machine Areas)

Process order: `BG → SAW → DA → WB → MOLD → PLATE → MARK → SAW_QFN → TF → ISO → FS`

### SQL Conventions

- Always filter `[{end_col}] > [{{start_col}]` to exclude zero/negative duration records
- Use `DATEDIFF(MINUTE, start, end) / 60.0` for hours
- Use `CONVERT(VARCHAR(7), datex, 120)` for `yyyy-MM` month grouping (faster than `FORMAT()`)
- Use named params (`:param_name`) — never string interpolation for user values
- Use `TOP N` for heavy queries (timeline: 3000, detail: 200)
- Always wrap column names in `[brackets]` for SQL Server

---

## Callback Conventions

### Global callbacks (registered in `app.py`)
- `filter-area.options` — loaded once, shared by Utilization and Downtime pages

### Page callback pattern

```python
@callback(
    Output('chart-id', 'figure'),
    Input('auto-refresh', 'n_intervals'),
    Input('filter-date-range', 'start_date'),
    Input('filter-date-range', 'end_date'),
    Input('filter-area', 'value'),
)
def update_chart(n_intervals, start_date, end_date, areas):
    from db import query_df          # lazy import inside callback
    from config import VIEW_NAME, COLUMN_MAP
    ...
```

- Import `db`, `config`, `utils` inside the callback function (lazy import) — avoids circular imports
- Always return an `empty_fig` with `template='plotly_white'` on error, never raise
- Always show a user-friendly `html.Div` error message alongside empty figures

---

## Adding a New Page

1. Create `pages/new_page.py`
2. Call `dash.register_page(__name__, path='/new-path', name='Nav Label')`
3. Add `dbc.NavLink("Nav Label", href='/new-path', active='exact', style=...)` to `app.py` navbar
4. Use `make_page_header()`, `make_filter_bar()`, `.page-container`, `.chart-card`, `.chart-title`
5. Do **not** register `Output('filter-area', 'options')` — it is already in `app.py`
6. Run `python -m py_compile pages/new_page.py` before restarting

---

## Running the Dashboard

```bash
cd dashboard
python app.py            # Development (auto-reload, http://localhost:8050)
python app.py --prod     # Production (waitress)
```

Key settings in `.env`:
- `REFRESH_MINUTES=60` — auto-refresh interval
- `VIEW_NAME=vw_job_nokey` — SQL view
- `MACHINE_AREAS=BG,SAW,DA,WB,MOLD,PLATE,MARK,SAW_QFN,TF,ISO,FS` — area order
