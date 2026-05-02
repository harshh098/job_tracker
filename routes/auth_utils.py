from functools import wraps
from flask import session, redirect, request, url_for


def login_required(f):
    """Redirect to /auth/login when no session exists."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(f"/auth/login?next={request.path}")
        return f(*args, **kwargs)
    return decorated