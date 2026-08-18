"""
utils/auth.py — upgraded to use database teacher accounts.
"""

import secrets
from fastapi import Request
from fastapi.responses import RedirectResponse
from database.setup import SessionLocal
from models.teacher import Teacher

# Session store: token → {"username": ..., "course": ..., "full_name": ...}
active_sessions: dict[str, dict] = {}


def create_session(teacher: Teacher) -> str:
    """Creates a session token storing teacher info."""
    token = secrets.token_urlsafe(32)
    active_sessions[token] = {
        "username":  teacher.username,
        "full_name": teacher.full_name,
        "course":    teacher.course,
    }
    return token


def get_current_user(request: Request) -> dict | None:
    """Returns session dict if logged in, None if not."""
    token = request.cookies.get("session")
    if not token:
        return None
    return active_sessions.get(token)


def require_login(request: Request):
    """
    Returns session dict if logged in.
    Returns RedirectResponse to /login if not.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user


def check_credentials(username: str, password: str):
    """
    Checks username and password against the database.
    Returns the Teacher object if valid, None if not.
    """
    db = SessionLocal()
    try:
        teacher = db.query(Teacher).filter(
            Teacher.username == username
        ).first()
        if teacher and teacher.check_password(password):
            return teacher
        return None
    finally:
        db.close()