# Oracle Data Fixes — Implementation Plan

**Status:** Draft — awaiting user approval
**Author:** Architect (planner agent)
**Date:** 2026-05-05
**Target files:** `pages/downtime.py`, `pages/overview.py`, `oracle_db.py`, `utils/queries.py`

---

## 1. Summary

3 small, independent bugs cause Oracle-side (ISO / FS) data to look incomplete on the dashboard:

- **Bug A** — Downtime event detail table drops 4 columns (`action`, `package_type`, `lot_no`, `die_mask`) for Oracle rows because the `pd.concat` only keeps a 9-column subset. The columns already exist on the Oracle DataFrame — we just forgot to pass them through.
- **Bug B** — Overview "KEY Machines" count for ISO / FS is low because it counts `DISTINCT code_machine` from Oracle events in the last 1 day (via `fetch_oracle_live_status`). Machines that are running and had no events → not counted. The fix is to count the master table `dbo.machine` (same source as Inventory), matching the existing SQL-Server fleet-count logic.
- **Bug C** — `fetch_oracle_live_status` omits `TECHNICIAN_COMMENT` from its `SELECT`, so the live Overview "Open Jobs" table has no `action` column for ISO / FS.

All 3 are additive / low-risk, do not touch the API code path, and can ship together in a single commit.

---

## 2. Bug A — Downtime event detail drops Oracle columns

### Root Cause

`pages/downtime.py:872-883` (SQL Server) selects:
`machine_id, area, job_type, symptom, cause, action, event_time, tech, wait_min, repair_min, package_type, lot_no, die_mask`.

`pages/downtime.py:915-916` (Oracle branch) subsets Oracle to only 9 columns:
`['machine_id', 'area', 'job_type', 'symptom', 'cause', 'datex', 'badge', 'wait_min', 'repair_min']`.

After `pd.concat` the Oracle rows have **NaN** for `action`, `package_type`, `lot_no`, `die_mask`, so the UI shows blank.

The 4 missing columns **already exist** on the Oracle cache DataFrame — see `oracle_db.py:98-117`:
```python
df = df.rename(columns={
    ...
    'PKG': 'package_type',
    'LOT_ID': 'lot_no',
    'PRODUCT_ID': 'die_mask',
    'TECHNICIAN_COMMENT': 'action',
})
# Fill nulls so downstream consumers (emails/dashboards) show blank not NaN
for col in ('package_type', 'lot_no', 'die_mask', 'action'):
    if col in df.columns:
        df[col] = df[col].fillna('').astype(str)
```

So the fix is purely a client-side column list — **no SQL change, no new query**.

### Code Change — `pages/downtime.py`

**BEFORE (lines 914-920):**
```python
# Oracle events for detail table
ora_events = ora[['machine_id', 'area', 'job_type', 'symptom',
                  'cause', 'datex', 'badge', 'wait_min', 'repair_min']].copy()
ora_events = ora_events.rename(columns={'datex': 'event_time', 'badge': 'tech'})
ora_events['wait_min'] = ora_events['wait_min'].round(0).astype(int)
ora_events['repair_min'] = ora_events['repair_min'].round(0).astype(int)
events_df = pd.concat([events_df, ora_events], ignore_index=True)
```

**AFTER:**
```python
# Oracle events for detail table — include action/package/lot/die_mask
# so the combined detail table matches SQL Server schema (no NaN blanks).
ora_events = ora[['machine_id', 'area', 'job_type', 'symptom',
                  'cause', 'action', 'datex', 'badge',
                  'wait_min', 'repair_min',
                  'package_type', 'lot_no', 'die_mask']].copy()
ora_events = ora_events.rename(columns={'datex': 'event_time', 'badge': 'tech'})
ora_events['wait_min'] = ora_events['wait_min'].round(0).astype(int)
ora_events['repair_min'] = ora_events['repair_min'].round(0).astype(int)
events_df = pd.concat([events_df, ora_events], ignore_index=True)
```

### Defensive note

`_load_all` guarantees the 4 columns exist, but only if the raw Oracle view returns them. To harden against schema drift we could add the same `df.get(col, '')` pattern the live-status path uses — **not required** for this fix; flagged under §10 Out of Scope.

---

## 3. Bug B — Overview "KEY Machines" count incomplete for ISO / FS

### Root Cause

`pages/overview.py:289`:
```python
ora_kpi_extra['machines'] = int(ora_live['code_machine'].nunique())
```

`ora_live` comes from `fetch_oracle_live_status()` which filters `S_DATE >= TRUNC(SYSDATE) - 1` (`oracle_db.py:250`). That is a *live activity* feed — not a fleet inventory. Machines that are running with no events in the past 24h are invisible.

### Why query `dbo.machine` instead of Oracle

- `dbo.machine` **is** the master machine table. It **already has** ISO and FS rows with `id_operation IN ('ISO','FS')` and proper `flag_key` / `flag_delete` flags (confirmed by Inventory page, which queries it via `utils/queries.py:inventory_all_machines()` and uses it for the KEY count at `pages/inventory.py:301`).
- SQL Server `job_list` → `total_key_machines` is computed from `dbo.machine` exactly this way (see `utils/queries.py:552-578`). We are simply mirroring that logic for the ISO / FS subset.
- Oracle `V_EQDOWNTIME` does not expose a `flag_key` analog — there is no reliable way to count "KEY machines" from Oracle alone.
- One small SQL-Server round-trip (<10 ms, well indexed) is cheaper and more correct than scanning Oracle.

### New Helper — `utils/queries.py`

Add to the "Machine Inventory queries" block (after `inventory_all_machines`, around line 614):

```python
def oracle_key_machine_count():
    """Count KEY machines in Oracle-managed areas (ISO / FS) from dbo.machine.

    Oracle's V_EQDOWNTIME is an event feed (no fleet inventory), so the
    correct source for a headcount is the master machine table — same
    source used by the Inventory page and by overview_status_matrix() for
    SQL-Server areas. This function honours ORACLE_ONLY_AREAS.
    """
    from config import MACHINE_TABLE
    placeholders = ', '.join(f"'{a}'" for a in sorted(ORACLE_ONLY_AREAS))
    return f"""
        SELECT COUNT(*) AS key_machines
        FROM {MACHINE_TABLE}
        WHERE [id_operation] IN ({placeholders})
          AND [flag_key] = 1
          AND ISNULL([flag_delete], 0) != 1
    """
```

`ORACLE_ONLY_AREAS` is already defined at `utils/queries.py:128` as `{'ISO', 'FS'}` — we reuse it so there is a single source of truth. Hardcoded inlining of the area names is safe here because they come from a constant, not user input.

### Code Change — `pages/overview.py`

**BEFORE (line 289):**
```python
ora_kpi_extra['machines'] = int(ora_live['code_machine'].nunique())
```

**AFTER:**
```python
# Count KEY machines from dbo.machine master (same source as Inventory page)
# — NOT from Oracle live events, which only sees machines active today.
try:
    from utils.queries import oracle_key_machine_count
    _ora_key = query_df(oracle_key_machine_count())
    ora_kpi_extra['machines'] = (int(_ora_key['key_machines'].iloc[0])
                                 if not _ora_key.empty else 0)
except Exception as _mc_err:
    import logging
    logging.warning(f"Oracle KEY machine count failed: {_mc_err}")
    # Fallback to old behaviour so we never show a lower number than before
    ora_kpi_extra['machines'] = int(ora_live['code_machine'].nunique())
```

### Area-filter respect

When the user filters by a specific area (e.g. only `ISO`), the fleet count should also reflect that. Inside the `if not api_used and ORA_ENABLED:` block (already around line 258-302), we know which Oracle areas are in scope via the `selected_areas` variable. Two acceptable approaches:

| Option | Behaviour | Recommendation |
|---|---|---|
| **A.** Always count both ISO+FS | Matches today's `ora_live` behaviour which returns whatever `fetch_oracle_live_status(selected_areas)` pre-filtered | ✅ Simpler, already matches other Oracle counters (`waiting`, `on_process` come from already-filtered `ora_live`) |
| **B.** Honour `selected_areas` — filter the COUNT(*) query too | More "correct" | Defer to coder — parameterise the helper if trivial |

The Coder may pick either. **A** is the minimum viable fix; **B** is a nicety. Since `ora_live` itself is already area-filtered upstream, the other 4 KPIs (`waiting/on_process/down/closed_shift`) are naturally area-aware — only the `machines` count diverges. If we pick **A**, the count is always the full ISO+FS fleet even when the user filters to just ISO. That matches how the SQL-Server `total_key_machines` query works today (it ignores `selected_areas` too — see `utils/queries.py:555-578`). **Recommend option A.**

---

## 4. Bug C — `fetch_oracle_live_status` missing `TECHNICIAN_COMMENT`

### Root Cause

`oracle_db.py:242-252` — the live-status SQL does not `SELECT TECHNICIAN_COMMENT`, and the post-fetch mapping block (lines 298-304) maps `PKG / LOT_ID / PRODUCT_ID` → `package_type / lot_no / die_mask` but omits the comment-to-action mapping that `_load_all` has.

Result: Overview "Open Jobs" table for ISO / FS has no `action` column.

### Code Change — `oracle_db.py`

**BEFORE (lines 242-252):**
```python
sql = f"""
    SELECT EQUIPMENT_TYPE, EQUIPMENT_ID, CAUSE, CRITERIA,
           P_START, P_STOP, STATUS, BADGE_NO, NAME,
           NVL(WAIT_TECH, 0) AS WAIT_TECH,
           NVL(DOWNTIME, 0) AS DOWNTIME,
           S_DATE, PKG, LOT_ID, PRODUCT_ID
    FROM EQ_USER.V_EQDOWNTIME
    WHERE EQUIPMENT_TYPE IN ({placeholders})
      AND S_DATE >= TRUNC(SYSDATE) - 1
    ORDER BY P_START DESC
"""
```

**AFTER:**
```python
sql = f"""
    SELECT EQUIPMENT_TYPE, EQUIPMENT_ID, CAUSE, CRITERIA,
           P_START, P_STOP, STATUS, BADGE_NO, NAME,
           NVL(WAIT_TECH, 0) AS WAIT_TECH,
           NVL(DOWNTIME, 0) AS DOWNTIME,
           S_DATE, PKG, LOT_ID, PRODUCT_ID, TECHNICIAN_COMMENT
    FROM EQ_USER.V_EQDOWNTIME
    WHERE EQUIPMENT_TYPE IN ({placeholders})
      AND S_DATE >= TRUNC(SYSDATE) - 1
    ORDER BY P_START DESC
"""
```

**BEFORE (lines 298-304):**
```python
# Map Oracle product/lot/die columns into the same shape used by SQL
# Server (so downstream Overview / Downtime pages render them)
df['package_type'] = df.get('PKG', pd.Series(dtype=str)).fillna('').astype(str)
df['lot_no'] = df.get('LOT_ID', pd.Series(dtype=str)).fillna('').astype(str)
df['die_mask'] = df.get('PRODUCT_ID', pd.Series(dtype=str)).fillna('').astype(str)
df['mpc'] = df['die_mask']  # alias used by some SQL-Server-style views
df['wire_type'] = ''
```

**AFTER:**
```python
# Map Oracle product/lot/die columns into the same shape used by SQL
# Server (so downstream Overview / Downtime pages render them)
df['package_type'] = df.get('PKG', pd.Series(dtype=str)).fillna('').astype(str)
df['lot_no'] = df.get('LOT_ID', pd.Series(dtype=str)).fillna('').astype(str)
df['die_mask'] = df.get('PRODUCT_ID', pd.Series(dtype=str)).fillna('').astype(str)
df['action'] = df.get('TECHNICIAN_COMMENT', pd.Series(dtype=str)).fillna('').astype(str)
df['mpc'] = df['die_mask']  # alias used by some SQL-Server-style views
df['wire_type'] = ''
```

### Cache note

The function caches the DataFrame at `_live_cache` (line 307) with a 5-minute TTL (`LIVE_CACHE_TTL = 300`). A dashboard restart clears the cache, and any deployment touching this file will trigger a restart → **no manual cache invalidation needed**. Worst case: one user gets up to 5 minutes of stale cache after deploy.

---

## 5. Files Touched

| File | Change | Lines affected | Type |
|------|--------|----------------|------|
| `pages/downtime.py` | Expand Oracle subset list (add 4 columns) | 914-916 → ~917-922 | additive |
| `utils/queries.py` | Add `oracle_key_machine_count()` helper | new function after line 614 | new |
| `pages/overview.py` | Replace `ora_live.nunique()` with master-table count + fallback | 289 → ~289-299 | replacement |
| `oracle_db.py` | Add `TECHNICIAN_COMMENT` to SELECT + action column mapping | 247, 301 | additive |
| `.env` / `.env.example` | **no change** | 0 | — |
| `config.py` | **no change** | 0 | — |
| `api_client.py` | **no change** | 0 | — |

---

## 6. API-path Safety

The API path (`USE_API=1` → `api_used=True` branch in `pages/overview.py:155-163`) is **not** touched by any of these fixes:

- **Bug A** is in `pages/downtime.py` inside the non-API `query_df(...)` block — `pages/downtime.py` does not have an API fast-path today, so there is no alternate code path to worry about here. The change lives entirely inside the existing `fetch_oracle_data` merge block.
- **Bug B**: the new `oracle_key_machine_count()` call is **guarded by the existing `if not api_used` block** (line 258). When `api_used=True`, `ora_kpi_extra` is initialised to zeros at line 161-162, and the whole Oracle merge block is skipped — untouched. API consumers already have the correct per-area counts from the middleware (commit `1a56666`).
- **Bug C**: `fetch_oracle_live_status` is only called from the direct-DB branch of `pages/overview.py` and from `shift_email.py`. The API middleware computes its own open-jobs list upstream and does not call this function on the dashboard side.

Explicit invariant after the fix:
```
api_used == True  →  behaviour identical to pre-fix (no new code executed)
api_used == False →  behaviour matches SQL-Server parity for Oracle rows
```

---

## 7. Testing Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | `python -m py_compile pages/downtime.py pages/overview.py oracle_db.py utils/queries.py` | no syntax errors |
| 2 | Start app (`python app.py`) and open `/` (Overview) | loads without error; check logs for "Oracle KEY machine count failed" (should NOT appear) |
| 3 | Overview → KEY Machines KPI | count = SQL-Server KEY count + ISO+FS count from `dbo.machine` (e.g. if Inventory shows 12 KEY machines for ISO and 8 for FS, KEY Machines should be `sql_count + 20`) |
| 4 | Compare KEY Machines number with Inventory page: `/inventory` filtered to area = ISO, toggle KEY flag | ISO count must match the ISO portion of Overview KPI delta (same for FS) |
| 5 | Overview → "Open Jobs" table for an ISO/FS row from today | `Action` column populated (not blank) — assuming TECHNICIAN_COMMENT is filled in Oracle |
| 6 | `/downtime` with date range covering today, area filter = ISO (or FS, or all) | combined events table shows `Action`, `Package Type`, `Lot`, `Die Mask` for Oracle rows (not blank/NaN) |
| 7 | `/downtime` with area filter excluding ISO/FS (e.g. only DA) | Oracle merge block skipped; no regression to SQL-Server events |
| 8 | Toggle `USE_API=1` in `.env` (if API available) and reload Overview | numbers unchanged from pre-fix (API path untouched) |
| 9 | Set `ORA_ENABLED=0` and reload | Overview and Downtime work normally; no Oracle calls attempted |
| 10 | Watch logs for 5+ minutes | no new WARN/ERROR from Oracle-related modules |

---

## 8. Rollback Plan

```bash
git log --oneline -3       # find the commit hash for this change
git revert <commit-hash>   # safe revert; preserves history
# restart the dashboard
```

All 3 fixes ship in 1 commit → one revert undoes everything. If only one of the three misbehaves, prefer a targeted follow-up commit rather than reverting all three.

---

## 9. Risk Assessment

| Bug | Risk | Reason |
|-----|------|--------|
| **A** — downtime detail columns | 🟢 Low | Pure column-list expansion. Columns are guaranteed to exist on the Oracle DataFrame by `_load_all`'s `.fillna('').astype(str)`. No SQL change, no schema coupling. |
| **B** — KEY Machines count | 🟢 Low | One new SELECT against `dbo.machine` (well-indexed, same pattern Inventory uses). Fallback to old behaviour inside `try/except` means worst case = pre-fix behaviour. No new dependency. |
| **C** — TECHNICIAN_COMMENT | 🟢 Low | Pure additive SELECT column + one mapping line. `df.get(..., Series)` pattern is already used for the other 3 columns. If Oracle column is NULL → `''`. |
| **Overall** | 🟢 **Low** | All 3 are additive / guarded. No API path change. No schema migration. No new dependencies. One-commit revert restores previous state. |

Performance:
- Bug B adds one small SQL query per Overview callback (COUNT(*) on ~a few thousand rows with `flag_key` index). Negligible vs the existing Overview queries.
- Bug C adds one column to an already-running Oracle SELECT → negligible.

---

## 10. Out of Scope

- ❌ Oracle connection pooling / thick-vs-thin mode (covered by `oracle_auto_detect_plan.md`).
- ❌ API middleware code (`api_client.py`, FastAPI server). Bugs B and C in API land were already fixed in commit `1a56666`.
- ❌ Utilization page merges (unaffected — does not use the dropped columns).
- ❌ Cache TTL tuning (`LIVE_CACHE_TTL=300`, `REFRESH_INTERVAL` in `_load_all`) — leave as is.
- ❌ Renaming `ora_kpi_extra['machines']` to `['key_machines']` or similar — cosmetic, skip.
- ❌ Defensive `df.get(col, pd.Series(dtype=str)).fillna('')` in `pages/downtime.py` Oracle subset — nice-to-have hardening; current `_load_all` already guarantees the columns. Skip unless Coder sees value.
- ❌ Option B under Bug B (area-filtered COUNT in `oracle_key_machine_count`) — defer; Option A is sufficient and matches SQL Server's `total_key_machines` behaviour.
- ❌ `shift_email.py` — it imports `fetch_oracle_live_status` but doesn't surface an `action` column in its email output today; no change needed.

---

## 11. Approval

- [ ] User reviewed plan
- [ ] User approved → proceed to Coder step

Execution order after approval:
**Coder (implement all 3 in one commit) → Reviewer (python-reviewer) → fix review comments → Git commit (do not push)**
