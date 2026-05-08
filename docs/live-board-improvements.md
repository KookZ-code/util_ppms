# Live Production Board — Status Filter + Refresh + Tile Time Improvements

**Status**: Approved 2026-05-01 — ready to implement
**Scope**: `dashboard/pages/live_board.py` only
**Est. diff**: ~45 lines

---

## Context

The `/live` page is a shop-floor TV dashboard (+ desktop view). Today:

- **Status filter** is `dbc.RadioItems` — user can only pick ONE status at a time.
- **Auto-refresh** every 30s.
- **Tile time line** always shows `wait_min`, even for machines in On-Process state, which misrepresents how long the tech has been repairing.

User feedback: view "problem states" (M/C Down + Setup + Waiting) together as default, slower refresh, and show context-appropriate time (wait vs repair) per tile.

---

## Changes

### 1. Status filter: RadioItems → Checklist

Replace single-select with multi-select. Remove 'ALL' option (equivalent to
checking all five). Default pre-checked = problem states only.

```python
# Before
dbc.RadioItems(
    id='live-status-filter',
    options=[
        {'label': 'ALL', 'value': 'ALL'},
        {'label': 'Running', 'value': 'Running'},
        {'label': 'M/C DOWN', 'value': 'M/C DOWN'},
        {'label': 'Setup', 'value': 'Setup'},
        {'label': 'Waiting', 'value': 'Waiting'},
    ],
    value='ALL', inline=True, ...
)

# After
dbc.Checklist(
    id='live-status-filter',
    options=[
        {'label': 'M/C DOWN', 'value': 'M/C DOWN'},
        {'label': 'Setup',    'value': 'Setup'},
        {'label': 'Waiting',  'value': 'Waiting'},
        {'label': 'Running',  'value': 'Running'},
        {'label': 'PM',       'value': 'PM'},
    ],
    value=['M/C DOWN', 'Setup', 'Waiting'],  # problem states by default
    inline=True, ...
)
```

### 2. Auto-refresh interval: 30s → 60s

```python
# Before
dcc.Interval(id='live-refresh', interval=30_000, n_intervals=0)

# After
dcc.Interval(id='live-refresh', interval=60_000, n_intervals=0)
```

Subheader text: `"... Auto-refresh 30s"` → `"... Auto-refresh 60s"`.

### 3. Tile time line (NEW)

`_make_tile()` currently always appends `{wait_min} min`. Change to be
status-aware:

| Tile status | Value shown | Icon | Example |
|---|---|---|---|
| Waiting | `wait_min` | ⏳ | `⏳ 47m` |
| M/C DOWN | `repair_min` | 🔧 | `🔧 12m` |
| Setup | `repair_min` | 🔧 | `🔧 12m` |
| PM | `repair_min` | 🔧 | `🔧 12m` |
| Running | — | — | (no time line) |
| Unknown | — | — | (no time line) |

Both `wait_min` and `repair_min` are already in `open_df`; we just need
to pick the right one and format with the icon.

Implementation sketch — pass both values into `_make_tile` via sub_lines:

```python
# In the per-machine loop:
if status_key == 'Waiting':
    t_val = r.get('wait_min')
    t_icon = '⏳'
else:  # M/C DOWN, Setup, PM (On Process statuses)
    t_val = r.get('repair_min')
    t_icon = '🔧'
if t_val is not None:
    try:
        sub_lines.append(f"{t_icon} {int(t_val)}m")
    except (ValueError, TypeError):
        pass
```

Running tiles have no `entry` in `open_by_machine` so they already have
no time line — no code change for them.

### 4. Filter logic in `update_board`

Replace current string-match filter with list membership:

```python
# Before
if status_filter and status_filter != 'ALL':
    if status_filter == 'Waiting' and status_key != 'Waiting':
        continue
    elif status_filter == 'M/C DOWN' and status_key != 'M/C DOWN':
        continue
    ...

# After
status_filter = status_filter or []
if status_key not in status_filter:
    continue
```

### 5. Summary line above tile grid

New UI element between Filter row and Tile grid:

```python
ALL_STATUSES = ('M/C DOWN', 'Setup', 'Waiting', 'Running', 'PM')
hidden = [s for s in ALL_STATUSES if s not in (status_filter or [])]
summary_text = (f"Showing {len(tiles)} machines"
                + (f" — {', '.join(hidden)} hidden" if hidden else ""))
```

Rendered as small muted text directly above the tile grid container.

### 6. Empty state when no status checked

When user unchecks everything:

```python
if not status_filter:
    grid = html.Div(
        "Select at least one status to view",
        style={'textAlign': 'center', 'color': MED_GRAY,
               'padding': '60px', 'fontSize': '18px'})
```

### 7. Area filter persistence — verify

`live-area-store` is a `dcc.Store` (memory) — should already persist
across auto-refresh ticks within the same session. No code change
expected, but manual test required:

1. Select FS chip → wait 60s → confirm chip still highlighted and tiles
   still filtered to FS.
2. If it resets, investigate the chip rebuild logic in `_make_area_chips`
   (possible n_clicks=0 feedback loop in `on_chip_click`).

---

## Non-goals (explicit)

- No quick-action chips ("Problems only" / "Show all") — user declined
- No persistence across page reload / tab restart — default every session
- No changes to Area filter, Alert banner, Counter logic, backend/API

---

## Testing checklist

- [ ] Open `/live` → default shows only M/C Down, Setup, Waiting tiles
- [ ] Uncheck Waiting → waiting tiles disappear from grid
- [ ] Check Running → running tiles appear
- [ ] Uncheck everything → empty state message shows
- [ ] Select FS area → wait 60s → FS still selected, tiles still filtered
- [ ] M/C DOWN tile shows `🔧 <n>m` (repair time)
- [ ] Waiting tile shows `⏳ <n>m` (wait time)
- [ ] Running tile shows no time line
- [ ] Summary line accurately reports visible tile count + hidden statuses

---

## Rollback plan

Single-file change. If issues arise, revert the commit and the page returns
to single-select + 30s refresh + always-wait-min. No schema/API impact.
