# Remove Login Gate — Default Guest Access

**Status**: Approved — ready to implement
**Scope**: `dashboard/app.py` only (~20 lines)
**Reason**: Diagnose server deployment issue; simplify first-visit UX

---

## Intent

Currently every unauthenticated request redirects to `/login`. This
makes it hard to tell whether server-side issues are in the app itself
or in the login/session middleware.

After this change:
- Opening the dashboard shows Overview immediately (no login wall)
- User is treated as `viewer` (guest role) by default
- Navbar shows "Guest (viewer)" label + "Login" button
- Logging in as supervisor/admin still works via the Login button
- Role-based page protection is unchanged

---

## Changes

### 1. `build_navbar(role)` — add Login / Logout conditional

Currently always shows "Logout". Change to:
- Unauthenticated (role=viewer implied) OR guest → show "Login" button (href=/login)
- Supervisor/Admin → show "Logout" button (href=/auth/logout)

Pass `is_authenticated` flag so the helper knows which to show.

```python
def build_navbar(role: str, is_authenticated: bool = False):
    ...
    right_btn = (
        html.A("Logout", href='/auth/logout', ...)
        if is_authenticated and role not in ('viewer',)
        else html.A("Login", href='/login', ...)
    )
```

### 2. `serve_layout()` — serve full layout for unauthenticated

Before: `if not current_user.is_authenticated:` returned a bare Div
(assumed user was on /login). Now return the full layout with viewer
permissions so any URL shows the real page, not a blank layout waiting
for React to redirect.

```python
def serve_layout():
    if not current_user.is_authenticated:
        # Treat as guest / viewer — full layout, no login wall
        user_label = "Guest (viewer)"
        return html.Div([
            ...,
            build_navbar('viewer', is_authenticated=False),
            html.Div(dash.page_container, ...),
            ...
        ])

    user_label = f"{current_user.display_name} ({current_user.role})"
    return html.Div([
        ...,
        build_navbar(current_user.role, is_authenticated=True),
        ...
    ])
```

### 3. `check_login()` — remove redirect, keep role protection

Before: `if not current_user.is_authenticated: return redirect('/login')`

After: unauthenticated users get viewer role implicitly. Admin-only
pages (e.g. /admin) are still protected.

```python
def check_login():
    ...
    role = current_user.role if current_user.is_authenticated else 'viewer'
    if hasattr(current_user, 'can_access'):
        if not current_user.can_access(path):
            return redirect('/')
    else:
        # unauthenticated — apply viewer page access
        from auth import PAGE_ACCESS
        allowed_pages = PAGE_ACCESS.get('viewer', set())
        page_paths = {p for p in allowed_pages}
        # Allow Dash internals + allowed viewer pages
        if not path.startswith('/_') and path not in page_paths and path != '/':
            return redirect('/')
```

---

## Testing checklist

- [ ] Open `http://localhost:8050/` without logging in → see Overview
- [ ] Navbar shows "Guest (viewer)" + "Login" button
- [ ] Try `/admin` unauthenticated → redirects to /
- [ ] Try `/timeline` unauthenticated → redirects to / (not viewer role)
- [ ] Click "Login" → see login page pre-filled with guest/guest
- [ ] Login as admin → navbar shows admin name + "Logout"
- [ ] Click "Logout" → back to /login page
- [ ] After logout, go to / → back to guest mode (no redirect to /login)

---

## Rollback

Revert `dashboard/app.py` to restore login gate. Single-file change.
