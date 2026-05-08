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

---

# Addendum (2026-05-01): Priority-based tile sorting

**Status**: Approved — ready to implement
**Additional diff**: ~15 lines

## Intent

On the shop floor, a supervisor scanning the board wants to see which
machines need attention *now*, not in whatever order dbo.machine happens
to list them. Sort the tile grid so the most-urgent cases are on top.

## Rules

Two-group sort, no visual divider (tile colors separate the groups
naturally — Yellow vs Red/Orange/Purple).

| Group | Tiles | Sort within |
|---|---|---|
| 1 | Waiting (no tech assigned yet) | `wait_min` desc |
| 2 | M/C DOWN, Setup, PM (tech working) | `repair_min` desc |
| 3 | Running / Unknown | unchanged (inventory/Oracle store order) |

Longest-waiting / longest-running tile appears first in each group,
Group 1 appears before Group 2 because a machine with *no tech* is a
higher operational priority than one already being worked on.

## Implementation sketch

Today the per-machine loop emits `_make_tile(...)` directly into a
`tiles` list. Change the loop to emit a small tuple instead:

```python
tile_records.append({
    'status_key': status_key,
    'sort_val':   int(t_val) if t_val is not None else 0,
    'machine_id': mid,
    'tile':       _make_tile(mid, status_key, sub_lines),
})
```

After the loop, bucket + sort:

```python
waiting_tiles = sorted(
    (r for r in tile_records if r['status_key'] == 'Waiting'),
    key=lambda r: -r['sort_val'],
)
active_tiles = sorted(
    (r for r in tile_records
     if r['status_key'] in ('M/C DOWN', 'Setup', 'PM')),
    key=lambda r: -r['sort_val'],
)
other_tiles = [r for r in tile_records
               if r['status_key'] not in ('Waiting', 'M/C DOWN',
                                          'Setup', 'PM')]
tiles = [r['tile'] for r in (waiting_tiles + active_tiles + other_tiles)]
```

## Edge cases

- Tile with missing time (e.g. repair_min is None) → `sort_val = 0` →
  appears at the bottom of its group. Acceptable (no time data = not
  actionable priority).
- When only Running is checked → all tiles in Group 3 → unchanged order.
- Status filter removes a whole group → other groups render uninterrupted.

## Testing

- [ ] Select `[M/C DOWN, Setup, Waiting]` (default) →
      First visible row is the Waiting tile with largest `⏳` value
- [ ] Continue down → all Waiting tiles finish before the first M/C DOWN
- [ ] Within on-process block, largest `🔧` value appears first
- [ ] Check Running → Running tiles appear AFTER the active block
- [ ] No tile left behind (total tile count matches summary line)

## Non-goals

- No priority score combining wait + repair (straightforward sort only)
- Sort stable within equal time values (pandas/python natural order)

---

# Addendum 2 (2026-05-01): Sectioned layout

**Status**: Approved — ready to implement
**Additional diff**: ~30 lines

## Intent

Make the priority groups visually distinct with header bars so a supervisor
scanning from a distance can tell at a glance whether there are any
"Waiting for tech" cases — without reading tile colors.

## Section blocks

Three sections, each with a small header bar above the grid:

| Section | Label | Accent stripe | Light tint bg | Shown when |
|---|---|---|---|---|
| 1 | WAITING FOR TECH · N machines | YELLOW | #FFF9E0 | any Waiting tile visible |
| 2 | ON PROCESS · N machines | RED | #FFF0F0 | any M/C DOWN / Setup / PM tile visible |
| 3 | RUNNING · N machines | GREEN | #F0FBF0 | any Running tile visible |

Sections with zero tiles are omitted (not shown as empty headers).

## Header style

- 4px left stripe in accent color
- Very light tinted background
- Text: bold uppercase title + subtle "· N machines" count
- Compact padding (6-10px)

## Implementation sketch

Add helper:

```python
def _render_section(title, accent_color, bg_tint, tiles):
    if not tiles:
        return None
    header = html.Div([
        html.Span(title, style={...bold uppercase...}),
        html.Span(f"  ·  {len(tiles)} machines", style={...muted...}),
    ], style={
        'background': bg_tint,
        'borderLeft': f'4px solid {accent_color}',
        'padding': '6px 14px',
        'marginTop': '12px', 'marginBottom': '8px',
        'borderRadius': '3px',
    })
    grid = html.Div(tiles, style={'display':'grid', ...existing grid style})
    return html.Div([header, grid])
```

In `update_board`, replace the single `grid = html.Div(tiles, ...)` block
with stacked sections:

```python
sections = []
if waiting_group:
    sections.append(_render_section('WAITING FOR TECH', YELLOW,
                                     '#FFF9E0',
                                     [r['tile'] for r in waiting_group]))
if active_group:
    sections.append(_render_section('ON PROCESS', RED,
                                     '#FFF0F0',
                                     [r['tile'] for r in active_group]))
if other_group:
    sections.append(_render_section('RUNNING', GREEN,
                                     '#F0FBF0',
                                     [r['tile'] for r in other_group]))

if not status_filter:
    grid = <"Select at least one status" message>
elif not sections:
    grid = <"No machines match current filters" message>
else:
    grid = html.Div([s for s in sections if s])
```

## Non-goals

- No collapsible/accordion sections (overkill for TV)
- No divider lines between tiles within a group (grid gap is enough)
- No animation when section counts change (auto-refresh is enough feedback)

