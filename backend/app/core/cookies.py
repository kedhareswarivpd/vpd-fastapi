"""Session cookie constants and helpers.

Auth is httpOnly-cookie-based, not Authorization-header Bearer tokens, and
the session itself is CoreFusion-owned (app/services/auth_service.py) — an
opaque, database-backed token, not a third-party-issued JWT. An httpOnly
cookie is never readable by page JavaScript, closing the XSS-token-theft
exposure that comes with keeping a token in memory/localStorage for a
header-based scheme. The cost cookies bring back is CSRF, which
core/csrf.py's double-submit check (the CSRF_COOKIE below, paired with the
CSRF_HEADER a same-origin script can read and echo back) exists specifically
to close.
"""
from fastapi import Response

from app.core.config import settings
from app.services.auth_service import ACCESS_TOKEN_TTL, REFRESH_TOKEN_TTL

ACCESS_TOKEN_COOKIE = "cf_access_token"
REFRESH_TOKEN_COOKIE = "cf_refresh_token"
CSRF_COOKIE = "cf_csrf_token"
CSRF_HEADER = "X-CSRF-Token"

_ACCESS_COOKIE_MAX_AGE = int(ACCESS_TOKEN_TTL.total_seconds())
_REFRESH_COOKIE_MAX_AGE = int(REFRESH_TOKEN_TTL.total_seconds())

# Same non-local/non-test convention already used for TLS pinning in
# core/database.py — cookies marked Secure require HTTPS, which a plain
# `docker compose up` local-dev/CI run over http://localhost doesn't have.
# Exported (not underscore-prefixed) so other cookie-setting code (e.g. the
# OAuth state cookie in routers/oauth.py) shares the exact same rule rather
# than recomputing it.
SECURE_COOKIES = settings.env.lower() not in {"development", "test", "local"}
_SECURE_COOKIES = SECURE_COOKIES


def set_session_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE, access_token, max_age=_ACCESS_COOKIE_MAX_AGE,
        httponly=True, secure=_SECURE_COOKIES, samesite="lax", path="/",
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE, refresh_token, max_age=_REFRESH_COOKIE_MAX_AGE,
        httponly=True, secure=_SECURE_COOKIES, samesite="lax", path="/",
    )
    # Deliberately NOT httponly: same-origin frontend JS must be able to read
    # this and echo it back as the X-CSRF-Token header (double-submit
    # pattern) — an httpOnly CSRF cookie would defeat the whole mechanism,
    # since the point is proving the request came from a script that can
    # read this origin's cookies, not from a cross-site form/img/fetch.
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=_REFRESH_COOKIE_MAX_AGE,
        httponly=False, secure=_SECURE_COOKIES, samesite="lax", path="/",
    )


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")
