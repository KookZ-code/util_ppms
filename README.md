# EMH — Equipment Maintenance Hub

A real-time equipment performance & maintenance intelligence platform for a semiconductor assembly & test facility. Combines a Dash-based operations dashboard, a FastAPI middleware layer, and automated reporting — all unified across SQL Server and Oracle backends.

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Dash Dashboard  │   │   3rd-party App  │   │ PowerApps / BI   │
│   (Overview,     │   │  (mobile / web)  │   │     Tools        │
│   Utilization,   │   └────────┬─────────┘   └─────────┬────────┘
│   Downtime, …)   │            │                       │
└────────┬─────────┘            │                       │
         │              X-API-Key + rate limit          │
         └──────────────────────┼───────────────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │   FastAPI Middleware Layer  │
                 │    /api/v1/*  •  Swagger    │
                 │  cache (60-300s) • bcrypt   │
                 └──────┬─────────────────┬────┘
                        │                 │
                ┌───────▼──────┐   ┌──────▼──────┐
                │  SQL Server  │   │  Oracle DB  │
                │ vw_job_nokey │   │ V_EQDOWNTIME│
                │ dbo.machine  │   │ (ISO / FS)  │
                └──────────────┘   └─────────────┘
```

---

## Features

### Dashboard (Dash 3.1)

- **Overview** — live plant status, KPI cards, job-type status matrix, open-jobs list (SQL + Oracle merged)
- **Utilization Analysis** — % utilization / downtime / lost-time per area, monthly trend, frequency-vs-duration scatter, top causes, previous-period comparison, click-to-drill-down monthly filtering
- **Downtime & Setup Analysis** — Pareto by symptom/cause, event detail table with Package/Lot/Die Mask columns, filter by job type, machine, symptom, cause, technician
- **Tech Performance** — composite scoring across 5 metrics (MTTR 30%, Response 20%, FTFR 25%, Volume 15%, Versatility 10%) with A/B/C/D grading
- **Machine Inventory & Detail** — master data browser + per-machine KPIs and recent events
- **Admin Panel** — full CRUD for user accounts and role-based page access

### API Middleware (FastAPI)

10 REST endpoints exposing SQL + Oracle data to third-party integrations with API-key auth, TTL caching, and rate limiting. Full OpenAPI / Swagger UI at `/docs`.

| Endpoint | Cache | Purpose |
|---|---|---|
| `GET /api/v1/health` | — | health check (no auth) |
| `GET /api/v1/overview` | 60s | live plant KPI + status matrix |
| `GET /api/v1/overview/open-jobs` | 60s | currently open jobs (Waiting + On Process) |
| `GET /api/v1/utilization` | 5m | % utilization KPI + per-area breakdown |
| `GET /api/v1/utilization/detail` | 5m | full payload: KPI + trend + scatter + top causes + prev period |
| `GET /api/v1/utilization/by-machine` | 5m | per-machine utilization rows |
| `GET /api/v1/utilization/attention` | 5m | top-10 machines needing attention |
| `GET /api/v1/downtime/events` | 5m | event-level downtime list |
| `GET /api/v1/downtime/pareto` | 5m | Pareto grouped by symptom or cause |
| `GET /api/v1/machines` | 1h | machine master list |
| `GET /api/v1/machines/{id}` | 5m | machine detail + recent events |
| `GET /api/v1/tech-performance` | 5m | technician composite scoring |
| `GET /api/v1/areas` | 1h | areas merged from SQL + Oracle |

### Automated Email Reporting

- **Shift summaries** — per-area KPIs, Top-3 machines, Event Detail. Sent automatically at Day 19:05 and Night 07:05 via APScheduler + SMTP.
- **Daily morning report** — plant-wide 24-hour summary with Executive Summary, Key Actions, Still Down, Recently Resolved, Per-Area Breakdown, Long-Term Down. Sent 07:30 before the 08:15 meeting.
- Supports area groups (`EOL = MARK + TF + ISO + FS`, `BSDA = BG + SAW + DA`) and `ALL:email` wildcard for managers receiving all areas.

### PPT Report Generators

Python (`python-pptx`) and Node (`pptxgenjs`) scripts producing Microchip-styled presentations from Excel data: die-attach turn-on status, Wire Bond turn-on, headcount/wave planning, BOI assembly analysis, wire-spool tracking, machine-loading calculators.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Dashboard | Dash 3.1 + dash-bootstrap-components 2.0 + Plotly 6.0 | Multi-page app, server-side callbacks |
| API | FastAPI + Uvicorn + slowapi + cachetools | OpenAPI 3.1, async endpoints |
| Database (primary) | SQL Server (pyodbc + SQLAlchemy 2.0) | `vw_job_nokey`, `dbo.job_list`, `dbo.machine`, `dbo.TechnicianList`, `dbo.api_keys`, `dbo.dashboard_users` |
| Database (Oracle) | `oracledb` thick mode | `V_Asodowntime_2025on` (cached 10 min background loader), `EQ_USER.V_EQDOWNTIME` (live status) |
| Auth | flask-login + bcrypt (dashboard), API keys bcrypt-hashed (API) | Page-level RBAC via `PAGE_ACCESS` dict |
| Scheduling | APScheduler | cron-style triggers for email jobs |
| Email | smtplib — internal relay, no TLS | `mx.microchip.com:25` |
| PPT | python-pptx + pptxgenjs | Corporate slide templates |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Oracle Instant Client 11.2+ (for ISO/FS areas) installed at a known path
- Access to SQL Server (for internal data) and SMTP relay (for email reports)

### Setup

```bash
# Clone
git clone <repo-url> && cd Project

# Install Python deps
python -m pip install -r dashboard/requirements.txt
python -m pip install fastapi uvicorn slowapi cachetools bcrypt pydantic requests

# Install Node deps (for PPT JS scripts)
npm install

# Configure environment
cp dashboard/.env.example dashboard/.env
# Edit dashboard/.env with your DB credentials, SMTP settings, Oracle client path
```

### Run the dashboard

```bash
cd dashboard
python app.py                 # dev server on :8050
# or
waitress-serve --listen=0.0.0.0:8050 app:server    # production
```

Visit `http://localhost:8050/` → login.

### Run the API middleware

```bash
# From project root
uvicorn api.main:app --reload --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

Default dev API key (created on first startup): `mch_dev_12345`

```bash
curl -H "X-API-Key: mch_dev_12345" http://localhost:8000/api/v1/overview
```

### Enable API-backed dashboard (Phase 3)

In `dashboard/.env`:

```ini
USE_API=1
API_BASE_URL=http://127.0.0.1:8000
API_KEY=mch_dev_12345
API_TIMEOUT=60
```

The dashboard will route through the middleware instead of hitting the DB directly. If the API is unreachable, it falls back automatically to direct DB.

---

## Project Structure

```
Project/
├── api/                            FastAPI middleware layer
│   ├── main.py                     app entry + CORS + lifespan + routers
│   ├── auth.py                     API-key bcrypt + dbo.api_keys bootstrap
│   ├── cache.py                    TTL cache decorator (cachetools)
│   ├── config.py                   loads dashboard/.env, CORS, rate limits
│   ├── routers/                    health, overview, utilization, downtime,
│   │                               machines, tech, areas
│   ├── schemas/                    Pydantic models per domain
│   ├── services/                   business logic (reuses dashboard/utils)
│   └── static/                     offline Swagger UI assets
│
├── dashboard/                      Dash application
│   ├── app.py                      server + login + page registry
│   ├── api_client.py               HTTP wrapper (USE_API feature flag)
│   ├── auth.py                     flask-login + page RBAC
│   ├── config.py                   DB / Oracle / shift config
│   ├── db.py                       SQLAlchemy engine + query_df()
│   ├── oracle_db.py                Oracle thick-mode + background loader
│   ├── daily_report.py             07:30 plant-wide morning summary
│   ├── shift_email.py              shift-end area summaries
│   ├── email_scheduler.py          APScheduler cron triggers
│   ├── pages/                      Dash pages (overview, utilization,
│   │                               downtime, timeline, inventory,
│   │                               machine_detail, admin, login)
│   ├── components/                 reusable UI (headers, KPI cards, tables)
│   ├── utils/                      queries.py, oracle_agg.py, colors.py
│   └── .env                        secrets (gitignored)
│
├── raw/                            Excel source data (gitignored)
├── Output/                         Generated PPT files (gitignored)
├── create_*.py  gen_*.js           PPT generator scripts
└── CLAUDE.md                       project-specific AI assistant instructions
```

---

## Key Design Decisions

### SQL + Oracle unification

ISO and FS areas live on Oracle; everything else on SQL Server. The dashboard — and now the API — merges the two transparently: SQL queries strip Oracle-only areas from their `WHERE` clause (`ORACLE_ONLY_AREAS = {'ISO', 'FS'}`), while Oracle data is loaded once in a background thread (30K rows, 10-minute refresh) and filtered in-memory.

### Shift semantics

Day shift: `07:00–18:59`. Night shift: `19:00–06:59`. Night-shift summaries are dated as the *next* day (i.e., a night shift starting Monday 19:00 is labelled "Tuesday Night"). The `SHIFT` column on Oracle is used as-is rather than recomputed from the operator-start hour, because Oracle `S_DATE` is midnight-aligned.

### Job-type categorization

```python
DOWN_TYPES = ('M/C DOWN',)
PM_TYPES   = ('PM',)
LOST_TYPES = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'CLEAN MOLD',
              'CHANGE CAP', 'FACILITY DOWN', 'ENGINEERING DOWN')
```

For DA specifically, "Unclosed Jobs" in email reports means `action = 'waiting for repair to continue'`.

### API reuses dashboard queries

API services call into `dashboard/utils/queries.py` and `dashboard/utils/oracle_agg.py` rather than re-implementing SQL. `api/config.py` prepends `dashboard/` to `sys.path` to make this possible. This keeps a single source of truth and avoids SQL drift.

### Phase 3 dashboard migration

Each page's callback checks `USE_API`; if true it calls the API client, if false (or on failure) it uses direct DB. Migrated pages so far:

- Overview (1 callback) — complete
- Utilization (3 callbacks) — complete
- Downtime, Timeline, Machine Detail, Inventory — pending

The feature flag lets you roll back per-environment without code changes.

---

## Security Checklist

- [x] API keys bcrypt-hashed, never plaintext in DB
- [x] HTTPS expected behind nginx in production
- [x] Rate limiting via `slowapi` (default 100 req/min)
- [x] All SQL queries use parameterized `:name` placeholders
- [x] CORS whitelist configured via `API_CORS_ORIGINS`
- [x] Secrets kept out of git via `.gitignore` and `.env`
- [ ] Separate read-only DB user for API (Phase 4 deploy)
- [ ] Key rotation policy (90-day)
- [ ] HTTPS / reverse proxy (Phase 4 deploy)

---

## Development

### Running tests

```bash
pytest dashboard/tests -v       # when present
pytest api/tests -v             # API integration tests
```

### Adding a new API endpoint

1. Add the Pydantic schema in `api/schemas/<domain>.py`
2. Add the service function in `api/services/<domain>_service.py` (reuse dashboard queries where possible)
3. Add the router in `api/routers/<domain>.py` with `@ttl_cache`, `@limiter.limit`, and `Depends(require_api_key)`
4. Register the router in `api/main.py`
5. Restart `uvicorn` — Swagger UI picks it up automatically

### Regenerating the codemap / docs

See `CLAUDE.md` for project conventions and AI-assistant guidance when working on this repo with Claude Code.

---

## Configuration Reference

Key `dashboard/.env` variables (see `.env.example` for full list):

| Variable | Purpose | Example |
|---|---|---|
| `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | SQL Server connection | `mth-cl-mthsql` / `1433` / … |
| `VIEW_NAME` | main fact view | `vw_job_nokey` |
| `MACHINE_TABLE` | master table | `dbo.machine` |
| `ORA_USER`, `ORA_PASSWORD`, `ORA_DSN`, `ORA_CLIENT_LIB`, `ORA_ENABLED` | Oracle connection | `C:\OracleX64\product\11.2.0\client_1\bin` |
| `ORA_VIEW` | cached Oracle fact view | `Vw_Asodowntime_2025on` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | outbound email | `mx.microchip.com:25`, TLS off |
| `SHIFT_EMAIL_RECIPIENTS` | per-area shift summary routing | `EOL:a@x.com,BSDA:b@x.com,ALL:mgr@x.com` |
| `DAILY_REPORT_RECIPIENTS`, `DAILY_REPORT_ENABLED` | 07:30 morning summary | `mgr@x.com` |
| `AREA_TARGETS` | per-area utilization target %  | `BG:85,DA:80,WB:85` |
| `EXCLUDED_MACHINES` | machines ignored in all metrics | `BG Barcode Scanner Jacket,…` |
| `USE_API`, `API_BASE_URL`, `API_KEY`, `API_TIMEOUT` | Phase 3 API routing | `1 / http://127.0.0.1:8000 / mch_dev_12345 / 60` |

---

## Roadmap

- **Phase 1** (done) — API skeleton, auth, 2 endpoints, Swagger
- **Phase 2** (done) — 8 more endpoints, caching, Pydantic validation
- **Phase 3** (in progress) — dashboard pages migrated to API. 2 of 6 pages complete.
- **Phase 4** (planned) — nginx reverse proxy, HTTPS, per-key rate limits, onboard first external consumer, production monitoring dashboard
- **Phase 5** (planned) — alerting (downtime > N minutes, utilization below target), anomaly detection for machine attention scoring

---

## License

Internal use only — proprietary to Microchip Technology.

---

## Acknowledgements

Built collaboratively with Claude Code (Anthropic). Design conversations, code review, and iterative migrations captured in `CLAUDE.md` and local agent memory.
