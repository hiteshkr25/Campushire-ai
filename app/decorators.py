from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.models.enums import UserRole


def role_required(*roles):
    """Restrict a route to one or more UserRole values."""
    allowed = {role if isinstance(role, UserRole) else UserRole(role) for role in roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            from flask import current_app

            # Enforce authentication similar to `login_required`.
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()

            if current_user.role not in allowed:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def anonymous_required(view_func):
    """Redirect authenticated users away from public auth pages."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated:
            from app.auth.services import AuthService

            return redirect(AuthService.get_dashboard_url(current_user))
        return view_func(*args, **kwargs)

    return wrapped


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr
