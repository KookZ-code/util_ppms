"""Authentication & Authorization module.

Simple DB-based login with flask-login.
Designed to be swappable to LDAP/AD later.
"""
import bcrypt
from flask import redirect, request, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from functools import wraps

login_manager = LoginManager()
login_manager.login_view = '/login'

# ── Role → Page access matrix ─────────────────────────────────────────────────
# True = allowed, missing = denied
PAGE_ACCESS = {
    'admin':      {'/', '/live', '/utilization', '/downtime', '/machine-detail',
                   '/timeline', '/inventory', '/store-items', '/admin'},
    'supervisor': {'/', '/live', '/utilization', '/downtime', '/machine-detail',
                   '/timeline', '/inventory', '/store-items'},
    'viewer':     {'/', '/live', '/utilization', '/downtime', '/machine-detail',
                   '/inventory'},
}


class User(UserMixin):
    def __init__(self, id, username, role, display_name=None):
        self.id = id
        self.username = username
        self.role = role
        self.display_name = display_name or username

    def can_access(self, path):
        allowed = PAGE_ACCESS.get(self.role, set())
        return path in allowed


@login_manager.user_loader
def load_user(user_id):
    """Load user from DB by id."""
    try:
        from db import query_df
        df = query_df(
            "SELECT id, username, role, display_name FROM dbo.dashboard_users WHERE id = :uid",
            {'uid': int(user_id)}
        )
        if df.empty:
            return None
        r = df.iloc[0]
        return User(r['id'], r['username'], r['role'], r.get('display_name'))
    except Exception:
        return None


def authenticate(username, password):
    """Verify username + password against DB. Returns User or None."""
    try:
        from db import query_df
        df = query_df(
            "SELECT id, username, password_hash, role, display_name "
            "FROM dbo.dashboard_users WHERE username = :uname",
            {'uname': username}
        )
        if df.empty:
            return None
        r = df.iloc[0]
        if bcrypt.checkpw(password.encode('utf-8'), r['password_hash'].encode('utf-8')):
            return User(r['id'], r['username'], r['role'], r.get('display_name'))
        return None
    except Exception:
        return None


def hash_password(password):
    """Generate bcrypt hash for a password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def require_login(f):
    """Decorator: redirect to /login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Decorator: check if current user has one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect('/login')
            if current_user.role not in roles:
                return redirect('/')
            return f(*args, **kwargs)
        return decorated
    return decorator


def setup_auth(app):
    """Initialize flask-login with the Dash app."""
    app.server.secret_key = app.server.config.get('SECRET_KEY', 'change-me-in-production')
    login_manager.init_app(app.server)

    @app.server.route('/auth/login', methods=['POST'])
    def do_login():
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user = authenticate(username, password)
        if user:
            login_user(user)
            next_url = request.args.get('next', '/')
            return redirect(next_url)
        return redirect('/login?error=1')

    @app.server.route('/auth/logout')
    def do_logout():
        logout_user()
        return redirect('/login')


def ensure_users_table():
    """Create dashboard_users table if not exists, with default admin."""
    from db import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME = 'dashboard_users'"
        ))
        if result.scalar() == 0:
            conn.execute(text("""
                CREATE TABLE dbo.dashboard_users (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    username NVARCHAR(50) NOT NULL UNIQUE,
                    password_hash NVARCHAR(200) NOT NULL,
                    role NVARCHAR(20) NOT NULL DEFAULT 'viewer',
                    display_name NVARCHAR(100),
                    created_at DATETIME DEFAULT GETDATE()
                )
            """))
            # Insert default admin
            admin_hash = hash_password('admin123')
            conn.execute(text(
                "INSERT INTO dbo.dashboard_users (username, password_hash, role, display_name) "
                "VALUES ('admin', :hash, 'admin', 'Administrator')"
            ), {'hash': admin_hash})
            conn.commit()
            print("Created dashboard_users table with default admin (admin/admin123)")
