# Sidebar Navigation — Implementation Plan

**Status:** Approved  
**Scope:** Replace horizontal top-navbar with collapsible sidebar in `app.py` + CSS + JS  
**Zero page-file changes** — all pages work unchanged

---

## 1. Layout Change

Current:
```
[Navbar full-width top bar]
[Page content — 100vw]
```

New:
```
[Sidebar 220px | 60px collapsed] [Page content — flex-1]
```

Root `serve_layout()` returns:
```python
html.Div([
    stores + interval + location,
    html.Div([
        build_sidebar(role, is_authenticated),   # left column
        html.Div(dash.page_container,            # right column
                 id='page-content', className='page-content'),
    ], className='app-shell'),
    footer,
])
```

CSS:
```css
.app-shell   { display: flex; min-height: 100vh; }
.page-content { flex: 1; min-width: 0; overflow-x: hidden; }
```

---

## 2. Sidebar Structure

```
sidebar (id='sidebar', class='sidebar expanded|collapsed')
├── sidebar-header
│   ├── .logo-dot  (yellow circle)
│   ├── .logo-text "EMH" + "Equipment Maintenance Hub"  ← hidden when collapsed
│   └── #toggle-btn  ☰ / →
├── sidebar-nav
│   └── per nav item:
│       a.nav-item[href, data-active]
│       ├── span.nav-icon  SVG icon
│       └── span.nav-label "Overview"  ← hidden when collapsed
│                          tooltip on hover when collapsed
├── sidebar-bottom
│   ├── .nav-item#dark-mode-btn  🌙 / ☀️ + "Dark Mode"
│   └── a.nav-item[/auth/logout]  🔒 + "Logout" / "Login"
└── .sidebar-user  "Admin (admin)"  ← hidden when collapsed
```

---

## 3. Icon Map (SVG inline, 20×20)

| Page | Icon |
|------|------|
| Overview | grid/dashboard |
| Live Board | activity/pulse |
| Utilization | gauge/speedometer |
| Downtime & Setup | wrench |
| Machine Detail | cpu/chip |
| Tech Performance | bar-chart-2 |
| Inventory | package |
| Store Items | shopping-bag |
| Admin | settings/gear |

Lucide-style SVG paths — inline in Python, no external CDN needed.

---

## 4. CSS (add to `assets/styles.css`)

```css
/* ── Sidebar ── */
:root {
  --sidebar-w:      220px;
  --sidebar-w-sm:   60px;
  --sidebar-bg:     #0E3689;
  --sidebar-hover:  rgba(255,255,255,0.08);
  --sidebar-active: rgba(255,255,255,0.14);
  --sidebar-text:   rgba(255,255,255,0.85);
  --sidebar-muted:  rgba(255,255,255,0.45);
  --sidebar-accent: #FFD53A;
  --transition:     0.2s ease;
}

.app-shell { display: flex; min-height: 100vh; }
.page-content { flex: 1; min-width: 0; overflow-x: hidden; }

.sidebar {
  width: var(--sidebar-w);
  min-height: 100vh;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition);
  overflow: hidden;
  position: sticky;
  top: 0;
  height: 100vh;
}
.sidebar.collapsed { width: var(--sidebar-w-sm); }

.sidebar-header {
  display: flex;
  align-items: center;
  padding: 16px 14px;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  min-height: 60px;
}
.logo-dot {
  width: 28px; height: 28px;
  border-radius: 8px;
  background: #FFD53A;
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 13px; color: #0E3689;
  flex-shrink: 0;
}
.logo-text {
  display: flex; flex-direction: column;
  overflow: hidden; white-space: nowrap;
  transition: opacity var(--transition), width var(--transition);
}
.logo-title  { font-weight: 700; font-size: 14px; color: #fff; }
.logo-sub    { font-size: 10px; color: var(--sidebar-muted); }
.sidebar.collapsed .logo-text { opacity: 0; width: 0; }

.toggle-btn {
  margin-left: auto;
  background: none; border: none; cursor: pointer;
  color: var(--sidebar-muted); font-size: 18px;
  padding: 4px; flex-shrink: 0;
  transition: color 0.15s;
}
.toggle-btn:hover { color: #fff; }
.sidebar.collapsed .toggle-btn { margin-left: 0; }

.sidebar-nav { flex: 1; padding: 8px 0; overflow-y: auto; overflow-x: hidden; }
.sidebar-bottom { padding: 8px 0; border-top: 1px solid rgba(255,255,255,0.1); }

.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px;
  color: var(--sidebar-text);
  text-decoration: none !important;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
  border-left: 3px solid transparent;
  position: relative;
}
.nav-item:hover { background: var(--sidebar-hover); color: #fff; }
.nav-item.active {
  background: var(--sidebar-active);
  border-left-color: var(--sidebar-accent);
  color: #fff;
}
.nav-icon { width: 20px; height: 20px; flex-shrink: 0; }
.nav-label {
  font-size: 13px; font-weight: 500;
  overflow: hidden; white-space: nowrap;
  transition: opacity var(--transition), width var(--transition);
}
.sidebar.collapsed .nav-label { opacity: 0; width: 0; }

/* Tooltip when collapsed */
.sidebar.collapsed .nav-item::after {
  content: attr(data-label);
  position: absolute;
  left: calc(var(--sidebar-w-sm) + 6px);
  background: #1A2332;
  color: #fff;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0; pointer-events: none;
  transition: opacity 0.15s;
  z-index: 1000;
}
.sidebar.collapsed .nav-item:hover::after { opacity: 1; }

.sidebar-user {
  padding: 10px 16px 6px;
  font-size: 11px;
  color: var(--sidebar-muted);
  overflow: hidden; white-space: nowrap;
  transition: opacity var(--transition);
}
.sidebar.collapsed .sidebar-user { opacity: 0; }

/* Page content offset — remove old navbar spacing */
.page-container { padding-top: 0 !important; }
.filter-bar { top: 0 !important; }
```

---

## 5. JS (add to `assets/sidebar.js`)

```javascript
// Persist sidebar state across page loads
(function() {
  const STORE_KEY = 'emh-sidebar';

  function applyState(collapsed) {
    const sb = document.getElementById('sidebar');
    if (!sb) return;
    if (collapsed) sb.classList.add('collapsed');
    else sb.classList.remove('collapsed');
  }

  // Apply saved state immediately on load
  const saved = localStorage.getItem(STORE_KEY);
  document.addEventListener('DOMContentLoaded', () => {
    applyState(saved === 'collapsed');
    setActiveLink();
  });

  // Toggle button
  document.addEventListener('click', (e) => {
    if (e.target.closest('#toggle-btn')) {
      const sb = document.getElementById('sidebar');
      if (!sb) return;
      const isCollapsed = sb.classList.toggle('collapsed');
      localStorage.setItem(STORE_KEY, isCollapsed ? 'collapsed' : 'expanded');
    }
  });

  // Highlight active nav link on location change
  function setActiveLink() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item[href]').forEach(a => {
      const isActive = a.getAttribute('href') === path ||
                       (a.getAttribute('href') === '/' && path === '/');
      a.classList.toggle('active', isActive);
    });
  }

  // Dash re-renders on page change — re-run active link detection
  const observer = new MutationObserver(setActiveLink);
  document.addEventListener('DOMContentLoaded', () => {
    const content = document.getElementById('page-content');
    if (content) observer.observe(content, { childList: true, subtree: false });
  });
})();
```

---

## 6. Changes to `app.py`

### 6.1 Replace `build_navbar()` with `build_sidebar()`

```python
ICONS = {
    '/':              '<svg>...dashboard...</svg>',
    '/live':          '<svg>...activity...</svg>',
    '/utilization':   '<svg>...gauge...</svg>',
    '/downtime':      '<svg>...wrench...</svg>',
    '/machine-detail':'<svg>...cpu...</svg>',
    '/timeline':      '<svg>...bar-chart...</svg>',
    '/inventory':     '<svg>...package...</svg>',
    '/store-items':   '<svg>...shopping-bag...</svg>',
    '/admin':         '<svg>...settings...</svg>',
}

def build_sidebar(role, is_authenticated=True):
    from auth import PAGE_ACCESS
    allowed = PAGE_ACCESS.get(role, set())
    nav_items = [
        html.A([
            html.Span(dangerously_allow_html=True,
                      children=ICONS.get(href, ''), className='nav-icon'),
            html.Span(label, className='nav-label'),
        ], href=href, className='nav-item', **{'data-label': label})
        for label, href in NAV_LINKS
        if href in allowed
    ]
    # ... header, bottom section, user label
    return html.Div(id='sidebar', className='sidebar', children=[...])
```

### 6.2 Update `serve_layout()`

Replace:
```python
build_navbar(role),
html.Div(dash.page_container, style={'minHeight': 'calc(100vh - 52px)'}),
```

With:
```python
html.Div([
    build_sidebar(role, is_authenticated),
    html.Div(dash.page_container, id='page-content', className='page-content'),
], className='app-shell'),
```

Remove `dbc.Navbar` import (no longer needed).

---

## 7. Implementation Checklist

- [ ] Step 1: Add CSS block (section 4) to `assets/styles.css`
- [ ] Step 2: Create `assets/sidebar.js` (section 5)
- [ ] Step 3: Define `ICONS` dict and `build_sidebar()` in `app.py`
- [ ] Step 4: Update both `serve_layout()` branches (authenticated + guest) to use `app-shell` layout
- [ ] Step 5: Remove `build_navbar()` function and `dbc.Navbar` usage
- [ ] Step 6: Restart app, verify sidebar renders and toggle works
- [ ] Step 7: Verify active link highlights on navigation
- [ ] Step 8: Verify dark mode still works
- [ ] Step 9: Verify role-based link visibility (viewer should not see Store Items / Admin)
- [ ] Step 10: Verify `filter-bar` sticky position still works (now `top: 0` instead of `top: 52px`)
