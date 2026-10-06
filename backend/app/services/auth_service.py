"""CoreFusion-owned session/account-security logic — the core of the
Supabase Auth → CoreFusion Auth migration. No external identity provider is
consulted anywhere in this file; every decision (session validity, lockout,
rotation) is made against this application's own database.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tokens import generate_token, hash_token
from app.models.user import User
from app.models.user_session import UserSession

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)

# Account lockout (brute-force / credential-stuffing defense).
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


async def create_session(
    db: AsyncSession, user: User, ip_address: str | None, user_agent: str | None,
) -> tuple[str, str, UserSession]:
    """Issues a brand-new session at login. Returns (access_token,
    refresh_token, session) — the plaintext tokens are only ever available
    here and at rotation time; only their hashes are persisted."""
    access_token = generate_token()
    refresh_token = generate_token()
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        expires_at=now + REFRESH_TOKEN_TTL,  # the row lives as long as the refresh token can renew it
        last_used_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return access_token, refresh_token, session


async def get_session_by_access_token(db: AsyncSession, token: str) -> UserSession | None:
    token_hash = hash_token(token)
    session = (
        await db.execute(
            select(UserSession).where(UserSession.session_token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at <= datetime.now(UTC):
        return None
    return session


async def rotate_session(
    db: AsyncSession, refresh_token: str, ip_address: str | None, user_agent: str | None,
) -> tuple[str, str, UserSession] | None:
    """Validates and rotates a refresh token in place on its existing
    session row. Returns None if the token doesn't match any live session —
    the caller (routers/auth.py) is responsible for clearing cookies and
    responding 401 in that case.

    Reuse detection: if the presented token matches a session's
    *previous* (already-rotated-away) refresh hash rather than its current
    one, that's a stolen-and-replayed token — the entire session is revoked
    immediately rather than rotated, since an attacker holding an old
    refresh token is a theft signal, not a legitimate late request.
    """
    token_hash = hash_token(refresh_token)
    now = datetime.now(UTC)

    session = (
        await db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
    ).scalar_one_or_none()

    if session is not None and session.revoked_at is None and session.expires_at > now:
        new_access = generate_token()
        new_refresh = generate_token()
        session.previous_refresh_token_hash = session.refresh_token_hash
        session.session_token_hash = hash_token(new_access)
        session.refresh_token_hash = hash_token(new_refresh)
        session.expires_at = now + REFRESH_TOKEN_TTL
        session.last_used_at = now
        session.ip_address = ip_address or session.ip_address
        session.user_agent = user_agent or session.user_agent
        await db.commit()
        await db.refresh(session)
        return new_access, new_refresh, session

    # Reuse of an already-rotated token — revoke the session it belonged to.
    reused_session = (
        await db.execute(select(UserSession).where(UserSession.previous_refresh_token_hash == token_hash))
    ).scalar_one_or_none()
    if reused_session is not None and reused_session.revoked_at is None:
        reused_session.revoked_at = now
        await db.commit()

    return None


async def revoke_session(db: AsyncSession, session: UserSession) -> None:
    session.revoked_at = datetime.now(UTC)
    await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id, except_session_id=None) -> None:
    """Used by password change/reset and admin-initiated deactivation —
    every one of those must invalidate existing sessions, not just the
    credential."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    )
    for session in result.scalars().all():
        if except_session_id is not None and session.id == except_session_id:
            continue
        session.revoked_at = now
    await db.commit()


def is_account_locked(user: User) -> bool:
    """True only while `locked_until` is still in the future — a lock
    auto-expires rather than requiring manual admin intervention, matching
    a *temporary* lockout policy."""
    if not user.is_locked:
        return False
    if user.locked_until is None:
        return True
    return user.locked_until > datetime.now(UTC)


async def record_failed_login(db: AsyncSession, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.is_locked = True
        user.locked_until = datetime.now(UTC) + LOCKOUT_DURATION
    await db.commit()
    # `updated_at` has onupdate=func.now() — a server-computed value.
    # expire_on_commit=False keeps every *other* attribute intact after
    # commit, but SQLAlchemy still marks server-computed columns touched by
    # this UPDATE as needing a re-fetch; without this refresh, the next
    # access of e.g. `user.updated_at` (Pydantic serialization included)
    # lazy-loads outside the request's greenlet context and raises
    # MissingGreenlet (found via a live login drill, not assumed).
    await db.refresh(user)


async def record_successful_login(db: AsyncSession, user: User) -> None:
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)  # see record_failed_login's comment above
