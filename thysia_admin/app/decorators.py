from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in roles:
                flash('You do not have permission to access that page.', 'error')
                return redirect(url_for('admin.overview'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role not in ('admin', 'super_admin'):
            flash('You do not have permission to access that page.', 'error')
            return redirect(url_for('admin.overview'))
        return f(*args, **kwargs)
    return decorated_function


# super_admin_required now behaves identically to admin_required
# (superadmin role is no longer used)
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role not in ('admin', 'super_admin'):
            flash('You do not have permission to access that page.', 'error')
            return redirect(url_for('admin.overview'))
        return f(*args, **kwargs)
    return decorated_function


def log_action(action, entity_type=None, entity_id=None, details=None):
    from app.models import AuditLog
    from app.extensions import db
    from flask import request
    try:
        log = AuditLog(
            account_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
