from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.logger import logger
from app.models.user import User
from app.services.auth_service import get_session_by_access_token


async def _user_from_access_token(token: str, db: AsyncSession) -> User | None:
    """Looks up the live session for this access token (CoreFusion-owned —
    no external identity provider involved) and loads its user. Returns
    None for a missing/expired/revoked session, an unknown user, or a
    deactivated account — callers decide how to report that."""
    session = await get_session_by_access_token(db, token)
    if session is None:
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise ApiError.unauthorized("Authentication token missing")

    user = await _user_from_access_token(token, db)
    if user is None:
        raise ApiError.unauthorized("Invalid or expired session")
    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None
    try:
        return await _user_from_access_token(token, db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not resolve optional user from session: %s", exc)
        return None


def require_roles(*roles: str):
    """
    Usage: Depends(require_roles("admin", "hr"))
    Returns the authenticated user so endpoints can use it directly.
    "super_admin" always bypasses the role check.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "super_admin":
            return current_user
        if current_user.role not in roles:
            raise ApiError.forbidden("You do not have permission to perform this action")
        return current_user

    return dependency


def is_staff(user: User | None, *roles: str) -> bool:
    """None-safe role-membership check for the recurring "is this caller
    staff, or the general public" pattern (e.g. content-visibility gates in
    blog.py/projects.py) — `user` may be None (get_optional_user on a public
    route), which every ad-hoc `current_user is not None and current_user.role
    in (...)` check needs to handle the same way.
    """
    return user is not None and user.role in roles


def get_client_ip(request: Request) -> str:
    """Return the client IP.

    `x-forwarded-for` is only trusted when the app is behind a known proxy
    (`TRUST_PROXY_HEADERS=true`) — otherwise an attacker could spoof the header
    and bypass IP-based rate limiting.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
