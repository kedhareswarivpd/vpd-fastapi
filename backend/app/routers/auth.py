import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    clear_session_cookies,
    set_session_cookies,
)
from app.core.database import get_db
from app.core.dependencies import get_client_ip, get_current_user
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.core.logger import logger
from app.core.mfa import decrypt_secret, encrypt_secret, generate_totp_secret, provisioning_uri, verify_totp_code
from app.core.password import hash_password, needs_rehash, verify_password
from app.core.tokens import generate_token, hash_token
from app.models.email_verification_token import EmailVerificationToken
from app.models.mfa_backup_code import MfaBackupCode
from app.models.mfa_challenge import MfaChallenge
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MfaChallengeResponse,
    MfaDisableRequest,
    MfaEnableRequest,
    MfaEnableResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    MfaVerifyLoginRequest,
    RegenerateBackupCodesRequest,
    RegenerateBackupCodesResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionOut,
    UserRead,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    create_session,
    get_session_by_access_token,
    is_account_locked,
    record_failed_login,
    record_successful_login,
    revoke_all_sessions,
    revoke_session,
    rotate_session,
)
from app.services.email_service import (
    send_mfa_disabled_notification,
    send_mfa_enabled_notification,
    send_password_changed_notification,
    send_password_reset_email,
    send_verification_email,
)
from app.utils.responses import success_response

# Fixed dummy hash for the login timing-safety comparison below — computed
# once at import time (not per-request; argon2 hashing is deliberately slow)
# via the real `hash_password()` so it always tracks whatever cost params
# `app.core.password` is configured with. A literal hash string here would
# silently drift out of sync if those params ever changed, subtly weakening
# the timing-equalization it exists for.
_DUMMY_PASSWORD_HASH = hash_password("dummy")

router = APIRouter(prefix="/auth", tags=["Auth"])

EMAIL_VERIFICATION_TOKEN_TTL = timedelta(hours=24)
PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)
MFA_CHALLENGE_TTL = timedelta(minutes=5)
MFA_PENDING_COOKIE = "cf_mfa_pending_token"
MFA_BACKUP_CODE_COUNT = 10


def _require_mfa_enabled() -> None:
    """The global kill switch (core/config.py's MFA_ENABLED) — when off,
    every /auth/mfa/* route 404s regardless of any per-account state, so the
    feature is invisible end-to-end rather than just "always declining"."""
    if not settings.mfa_enabled:
        raise ApiError.not_found("MFA is not available")


async def _issue_mfa_challenge(db: AsyncSession, user: User) -> str:
    token = generate_token()
    db.add(MfaChallenge(
        user_id=user.id, token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + MFA_CHALLENGE_TTL,
    ))
    await db.commit()
    return token


async def _resolve_mfa_challenge(db: AsyncSession, token: str) -> tuple[MfaChallenge, User] | None:
    """Looks up the challenge WITHOUT consuming it — a wrong code on the
    first attempt must not burn the challenge and force a fresh login just
    for a typo. Only the caller, after a successful code check, marks it
    used (see mfa_verify_login below). The challenge still naturally expires
    after MFA_CHALLENGE_TTL and account lockout still applies to repeated
    wrong codes via record_failed_login, so this doesn't allow unlimited
    unthrottled guessing."""
    token_hash = hash_token(token)
    challenge = (
        await db.execute(select(MfaChallenge).where(MfaChallenge.token_hash == token_hash))
    ).scalar_one_or_none()
    if (
        challenge is None
        or challenge.used_at is not None
        or challenge.expires_at <= datetime.now(UTC)
    ):
        return None
    user = await db.get(User, challenge.user_id)
    if user is None or not user.is_active or not user.mfa_enabled:
        return None
    return challenge, user


async def _verify_mfa_code(db: AsyncSession, user: User, code: str) -> bool:
    """Tries the code as a TOTP first, then as a single-use backup code."""
    code = (code or "").strip()
    if code.isdigit() and user.mfa_secret_encrypted and verify_totp_code(decrypt_secret(user.mfa_secret_encrypted), code):
        return True

    code_hash = hash_token(code.lower())
    backup = (
        await db.execute(
            select(MfaBackupCode).where(
                MfaBackupCode.user_id == user.id,
                MfaBackupCode.code_hash == code_hash,
                MfaBackupCode.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if backup is not None:
        backup.used_at = datetime.now(UTC)
        await db.commit()
        return True

    return False


def _generate_backup_codes() -> list[str]:
    return [secrets.token_hex(5) for _ in range(MFA_BACKUP_CODE_COUNT)]

# Generic response for forgot-password regardless of whether the email
# exists — never lets a caller use this endpoint to enumerate accounts.
_FORGOT_PASSWORD_GENERIC_MESSAGE = "If an account with that email exists, a password-reset link has been sent."


async def _issue_verification_email(db: AsyncSession, user: User) -> None:
    # Invalidate any earlier outstanding tokens for this user before issuing
    # a new one — only the most recent link should ever work.
    await db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    token = generate_token()
    db.add(EmailVerificationToken(
        user_id=user.id, token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + EMAIL_VERIFICATION_TOKEN_TTL,
    ))
    await db.commit()
    verify_url = f"{settings.client_url.rstrip('/')}/verify-email?token={token}"
    try:
        await send_verification_email(user.name, user.email, verify_url)
    except Exception as exc:  # noqa: BLE001 — account creation must not fail over email delivery
        logger.warning("Failed to send verification email to %s: %s", user.email, exc)


@router.post("/register", response_model=dict, status_code=201)
@limiter.limit("10/hour")
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Public self-serve signup — always creates a Client account. Employee/Admin
    accounts must be created by an authenticated Admin/HR user via POST /users."""
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise ApiError.conflict("An account with this email already exists")

    user = User(
        id=uuid.uuid4(),
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone=payload.phone,
        role="client",
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _issue_verification_email(db, user)

    return success_response(data=UserRead.model_validate(user), message="Account created successfully", status_code=201)


@router.post("/login", response_model=dict)
@limiter.limit("10/minute")
async def login(request: Request, response: Response, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()

    # Always run the hash comparison, even on a not-found user, against a
    # fixed dummy hash — otherwise "no such user" returns faster than "wrong
    # password", which is a timing side-channel for email enumeration.
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_PASSWORD_HASH)

    if user is None or not password_ok:
        if user is not None:
            await record_failed_login(db, user)
        raise ApiError.unauthorized("Invalid email or password")

    if not user.is_active:
        raise ApiError.forbidden("Your account has been deactivated")

    if is_account_locked(user):
        raise ApiError.forbidden("Account temporarily locked due to repeated failed login attempts. Try again later.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    if settings.mfa_enabled and user.mfa_enabled:
        # Password is correct, but the session doesn't exist yet — no
        # cookies are set until the second factor is also confirmed via
        # POST /auth/mfa/verify-login. Deliberately does NOT call
        # record_successful_login yet (that only happens once MFA passes
        # too), so failed-login-attempt tracking still reflects genuine
        # login failures, not "password ok, MFA pending".
        await db.commit()
        mfa_token = await _issue_mfa_challenge(db, user)
        return success_response(
            data=MfaChallengeResponse(mfa_token=mfa_token),
            message="MFA verification required",
        )

    await record_successful_login(db, user)

    access_token, refresh_token, _session = await create_session(
        db, user, get_client_ip(request), request.headers.get("user-agent"),
    )
    set_session_cookies(response, access_token, refresh_token, csrf_token=secrets.token_urlsafe(32))
    return success_response(data=LoginResponse(user=UserRead.model_validate(user)), message="Logged in successfully")


@router.post("/mfa/verify-login", response_model=dict)
@limiter.limit("10/minute")
async def mfa_verify_login(request: Request, response: Response, payload: MfaVerifyLoginRequest, db: AsyncSession = Depends(get_db)):
    """Completes a login that POST /auth/login paused for MFA. Accepts the
    mfa_token from the request body (password-login flow, which received it
    in a JSON response) or falls back to the cf_mfa_pending_token cookie (the
    OAuth-callback flow, which can only set a cookie on its browser redirect,
    not return JSON)."""
    _require_mfa_enabled()

    mfa_token = payload.mfa_token or request.cookies.get(MFA_PENDING_COOKIE)
    if not mfa_token:
        raise ApiError.unauthorized("No pending MFA challenge")

    resolved = await _resolve_mfa_challenge(db, mfa_token)
    if resolved is None:
        raise ApiError.unauthorized("Invalid or expired MFA challenge — please log in again")
    challenge, user = resolved

    if is_account_locked(user):
        raise ApiError.forbidden("Account temporarily locked due to repeated failed login attempts. Try again later.")

    if not await _verify_mfa_code(db, user, payload.code):
        await record_failed_login(db, user)
        raise ApiError.unauthorized("Invalid authentication code")

    challenge.used_at = datetime.now(UTC)
    await record_successful_login(db, user)
    access_token, refresh_token, _session = await create_session(
        db, user, get_client_ip(request), request.headers.get("user-agent"),
    )
    set_session_cookies(response, access_token, refresh_token, csrf_token=secrets.token_urlsafe(32))
    response.delete_cookie(MFA_PENDING_COOKIE, path="/")
    return success_response(data=LoginResponse(user=UserRead.model_validate(user)), message="Logged in successfully")


@router.post("/refresh", response_model=dict)
@limiter.limit("30/minute")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Silently renews the session using the httpOnly refresh-token cookie —
    called by the frontend when a request comes back 401 due to access-token
    expiry, without ever exposing either token to page JavaScript."""
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token:
        raise ApiError.unauthorized("No active session to refresh")

    result = await rotate_session(db, refresh_token, get_client_ip(request), request.headers.get("user-agent"))
    if result is None:
        clear_session_cookies(response)
        raise ApiError.unauthorized("Session expired — please log in again")

    new_access, new_refresh, session = result
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        clear_session_cookies(response)
        raise ApiError.unauthorized("User no longer exists or is deactivated")

    set_session_cookies(response, new_access, new_refresh, csrf_token=secrets.token_urlsafe(32))
    return success_response(data=UserRead.model_validate(user), message="Session refreshed")


@router.post("/logout", response_model=dict)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Requires a valid session cookie so a caller can only revoke their own
    session (CF-AUD-005)."""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        session = await get_session_by_access_token(db, token)
        if session is not None:
            await revoke_session(db, session)
    clear_session_cookies(response)
    return success_response(message="Logged out successfully")


@router.post("/logout-all", response_model=dict)
async def logout_all(response: Response, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Revokes every session for the current user, including the one making
    this request — used for "sign out everywhere" (e.g. after suspecting a
    device was compromised)."""
    await revoke_all_sessions(db, current_user.id)
    clear_session_cookies(response)
    return success_response(message="Logged out of all sessions")


@router.get("/me", response_model=dict)
async def me(current_user: User = Depends(get_current_user)):
    return success_response(data=UserRead.model_validate(current_user), message="Current user fetched")


@router.post("/forgot-password", response_model=dict)
@limiter.limit("5/minute")
async def forgot_password(request: Request, payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is not None:
        # Invalidate earlier outstanding reset tokens first.
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        token = generate_token()
        db.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + PASSWORD_RESET_TOKEN_TTL,
        ))
        await db.commit()
        reset_url = f"{settings.client_url.rstrip('/')}/reset-password?token={token}"
        try:
            await send_password_reset_email(user.name, user.email, reset_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send password-reset email to %s: %s", user.email, exc)
    # Same message whether or not the account exists — never lets this
    # endpoint be used to enumerate registered emails.
    return success_response(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)


@router.post("/reset-password", response_model=dict)
@limiter.limit("10/hour")
async def reset_password(request: Request, payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    reset_token = (
        await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at <= datetime.now(UTC)
    ):
        raise ApiError.bad_request("This password-reset link is invalid or has expired")

    user = await db.get(User, reset_token.user_id)
    if user is None:
        raise ApiError.bad_request("This password-reset link is invalid or has expired")

    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.now(UTC)
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    reset_token.used_at = datetime.now(UTC)
    await db.commit()

    # Resetting the password invalidates every existing session — if an
    # attacker was already inside the account, this locks them out too.
    await revoke_all_sessions(db, user.id)

    try:
        await send_password_changed_notification(user.name, user.email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send password-changed notification to %s: %s", user.email, exc)

    return success_response(message="Password reset successfully — please log in with your new password")


@router.post("/verify-email", response_model=dict)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    verification = (
        await db.execute(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if (
        verification is None
        or verification.used_at is not None
        or verification.expires_at <= datetime.now(UTC)
    ):
        raise ApiError.bad_request("This verification link is invalid or has expired")

    user = await db.get(User, verification.user_id)
    if user is None:
        raise ApiError.bad_request("This verification link is invalid or has expired")

    user.is_email_verified = True
    user.email_verified_at = datetime.now(UTC)
    verification.used_at = datetime.now(UTC)
    await db.commit()

    return success_response(message="Email verified successfully")


@router.post("/resend-verification", response_model=dict)
@limiter.limit("5/minute")
async def resend_verification(request: Request, payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    # Same generic response whether or not the account exists / is already
    # verified — avoids both email enumeration and confirming verification state.
    if user is not None and not user.is_email_verified:
        await _issue_verification_email(db, user)
    return success_response(message="If the account exists and is not yet verified, a new verification email has been sent.")


@router.post("/change-password", response_model=dict)
async def change_password(payload: ChangePasswordRequest, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise ApiError.unauthorized("Current password is incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.now(UTC)
    await db.commit()

    # Keep the session making this request alive; revoke every other one —
    # a password change is exactly the moment to kick out anyone else.
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    current_session_id = None
    if token:
        session = await get_session_by_access_token(db, token)
        current_session_id = session.id if session else None
    await revoke_all_sessions(db, current_user.id, except_session_id=current_session_id)

    try:
        await send_password_changed_notification(current_user.name, current_user.email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send password-changed notification to %s: %s", current_user.email, exc)

    return success_response(message="Password changed successfully")


@router.get("/sessions", response_model=dict)
async def list_sessions(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    current_hash = hash_token(current_token) if current_token else None

    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_used_at.desc())
    )
    sessions = result.scalars().all()
    data = [
        SessionOut(
            id=s.id, ip_address=s.ip_address, user_agent=s.user_agent,
            created_at=s.created_at, last_used_at=s.last_used_at,
            is_current=(s.session_token_hash == current_hash),
        )
        for s in sessions
    ]
    return success_response(data=data, message="Active sessions fetched")


@router.delete("/sessions/{session_id}", response_model=dict)
async def revoke_one_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = await db.get(UserSession, session_id)
    if session is None or session.user_id != current_user.id:
        # Same 404 whether the session doesn't exist or belongs to someone
        # else — never confirms another user's session ID is valid (IDOR).
        raise ApiError.not_found("Session not found")
    await revoke_session(db, session)
    return success_response(message="Session revoked")


# ==================== MFA / 2FA (TOTP) ====================
# Every route below 404s outright when settings.mfa_enabled is False (the
# global switch — see core/config.py) via _require_mfa_enabled(), regardless
# of any per-user state. Individually, each account's MFA stays off until
# that account's own owner opts in through setup -> enable below.

@router.get("/mfa/status", response_model=dict)
async def mfa_status(current_user: User = Depends(get_current_user)):
    return success_response(data=MfaStatusResponse(
        available=settings.mfa_enabled,
        enabled=current_user.mfa_enabled,
        enabled_at=current_user.mfa_enabled_at,
    ), message="MFA status fetched")


@router.post("/mfa/setup", response_model=dict)
@limiter.limit("5/minute")
async def mfa_setup(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generates a new TOTP secret and stores it (encrypted) against the
    account, but does NOT turn MFA on yet — `mfa_enabled` only flips to True
    once POST /auth/mfa/enable proves the user actually captured the secret
    in a real authenticator app by producing a valid code from it. Calling
    this again before /enable simply replaces the pending secret."""
    _require_mfa_enabled()
    if current_user.mfa_enabled:
        raise ApiError.conflict("MFA is already enabled on this account")

    secret = generate_totp_secret()
    current_user.mfa_secret_encrypted = encrypt_secret(secret)
    await db.commit()

    return success_response(
        data=MfaSetupResponse(secret=secret, otpauth_url=provisioning_uri(secret, current_user.email)),
        message="Scan the QR code (or enter the secret manually) in your authenticator app, then confirm with POST /auth/mfa/enable",
    )


@router.post("/mfa/enable", response_model=dict)
@limiter.limit("10/minute")
async def mfa_enable(request: Request, payload: MfaEnableRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_mfa_enabled()
    if current_user.mfa_enabled:
        raise ApiError.conflict("MFA is already enabled on this account")
    if not current_user.mfa_secret_encrypted:
        raise ApiError.bad_request("Call POST /auth/mfa/setup first")

    if not verify_totp_code(decrypt_secret(current_user.mfa_secret_encrypted), payload.code):
        raise ApiError.unauthorized("Invalid authentication code")

    current_user.mfa_enabled = True
    current_user.mfa_enabled_at = datetime.now(UTC)

    backup_codes = _generate_backup_codes()
    for code in backup_codes:
        db.add(MfaBackupCode(user_id=current_user.id, code_hash=hash_token(code.lower())))
    await db.commit()

    try:
        await send_mfa_enabled_notification(current_user.name, current_user.email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send MFA-enabled notification to %s: %s", current_user.email, exc)

    return success_response(
        data=MfaEnableResponse(backup_codes=backup_codes),
        message="MFA enabled — store these backup codes somewhere safe, they will not be shown again",
    )


@router.post("/mfa/disable", response_model=dict)
async def mfa_disable(payload: MfaDisableRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_mfa_enabled()
    if not current_user.mfa_enabled:
        raise ApiError.conflict("MFA is not enabled on this account")
    if not verify_password(payload.password, current_user.password_hash):
        raise ApiError.unauthorized("Current password is incorrect")

    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_enabled_at = None
    await db.execute(
        update(MfaBackupCode)
        .where(MfaBackupCode.user_id == current_user.id, MfaBackupCode.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    await db.commit()

    try:
        await send_mfa_disabled_notification(current_user.name, current_user.email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send MFA-disabled notification to %s: %s", current_user.email, exc)

    return success_response(message="MFA disabled")


@router.post("/mfa/backup-codes/regenerate", response_model=dict)
@limiter.limit("5/minute")
async def mfa_regenerate_backup_codes(request: Request, payload: RegenerateBackupCodesRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_mfa_enabled()
    if not current_user.mfa_enabled:
        raise ApiError.conflict("MFA is not enabled on this account")
    if not verify_password(payload.password, current_user.password_hash):
        raise ApiError.unauthorized("Current password is incorrect")

    # Invalidate every previously-issued unused code — regenerating means the
    # old list is no longer trustworthy (e.g. the user suspects it leaked).
    await db.execute(
        update(MfaBackupCode)
        .where(MfaBackupCode.user_id == current_user.id, MfaBackupCode.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    backup_codes = _generate_backup_codes()
    for code in backup_codes:
        db.add(MfaBackupCode(user_id=current_user.id, code_hash=hash_token(code.lower())))
    await db.commit()

    return success_response(
        data=RegenerateBackupCodesResponse(backup_codes=backup_codes),
        message="New backup codes generated — the old ones no longer work",
    )
