"""Social login (Google, GitHub) — entirely optional, gated behind
settings.oauth_enabled (see core/config.py) plus each provider's own
client_id/secret/redirect_uri being configured (core/oauth_providers.py).

Unlike every other router in this app, these two endpoints are consumed by a
full-page browser navigation, not a fetch()/XHR call — the provider redirects
the user's browser here directly. That's why both return RedirectResponse
(302) rather than the usual `{success, data, message}` JSON envelope: there's
no JavaScript on the return trip to read a JSON body, only a browser
following redirects and carrying cookies.
"""
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import SECURE_COOKIES, set_session_cookies
from app.core.database import get_db
from app.core.dependencies import get_client_ip
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.core.logger import logger
from app.core.oauth_providers import get_provider
from app.core.password import hash_password
from app.core.tokens import hash_token
from app.models.mfa_challenge import MfaChallenge
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services.auth_service import create_session, record_successful_login

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])

OAUTH_STATE_COOKIE = "cf_oauth_state"
MFA_PENDING_COOKIE = "cf_mfa_pending_token"  # kept identical to routers/auth.py's constant
_STATE_COOKIE_MAX_AGE = 600  # 10 minutes — plenty for a consent-screen round trip
_HTTP_TIMEOUT = 10.0


def _require_oauth_enabled() -> None:
    if not settings.oauth_enabled:
        raise ApiError.not_found("OAuth login is not available")


def _success_redirect_url() -> str:
    return settings.oauth_success_redirect_url or settings.client_url


def _failure_redirect(reason: str) -> RedirectResponse:
    base = settings.oauth_failure_redirect_url or settings.client_url
    url = f"{base}{'&' if '?' in base else '?'}oauth_error={reason}"
    resp = RedirectResponse(url, status_code=302)
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return resp


@router.get("/{provider}/login")
@limiter.limit("20/minute")
async def oauth_login(provider: str, request: Request):
    _require_oauth_enabled()
    cfg = get_provider(provider)
    if cfg is None:
        raise ApiError.not_found("Unknown or unconfigured OAuth provider")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": cfg.scope,
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"

    resp = RedirectResponse(f"{cfg.authorize_url}?{urlencode(params)}", status_code=302)
    resp.set_cookie(
        OAUTH_STATE_COOKIE, state, max_age=_STATE_COOKIE_MAX_AGE,
        httponly=True, secure=SECURE_COOKIES, samesite="lax", path="/",
    )
    return resp


async def _extract_identity(provider: str, client: httpx.AsyncClient, provider_access_token: str) -> tuple[str, str, bool, str] | None:
    """Returns (provider_account_id, email, email_verified, display_name), or
    None if the provider's userinfo response couldn't be interpreted."""
    headers = {"Authorization": f"Bearer {provider_access_token}", "Accept": "application/json"}

    if provider == "google":
        resp = await client.get(get_provider("google").userinfo_url, headers=headers)
        if resp.status_code != 200:
            return None
        info = resp.json()
        sub = info.get("sub")
        email = info.get("email")
        if not sub or not email:
            return None
        return sub, email, bool(info.get("email_verified", False)), info.get("name") or email

    if provider == "github":
        resp = await client.get(get_provider("github").userinfo_url, headers=headers)
        if resp.status_code != 200:
            return None
        info = resp.json()
        account_id = info.get("id")
        if not account_id:
            return None
        # GitHub's /user endpoint returns the profile email (if public) with
        # no verification status attached — only the dedicated /user/emails
        # endpoint confirms whether an address is actually verified, so it's
        # always consulted rather than trusting /user's email field.
        email = None
        email_verified = False
        emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
        if emails_resp.status_code == 200:
            for entry in emails_resp.json():
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    email_verified = True
                    break
        if not email:
            return None
        name = info.get("name") or info.get("login") or email
        return str(account_id), email, email_verified, name

    return None


@router.get("/{provider}/callback")
@limiter.limit("20/minute")
async def oauth_callback(
    provider: str, request: Request,
    code: str | None = None, state: str | None = None, error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    _require_oauth_enabled()
    cfg = get_provider(provider)
    if cfg is None:
        raise ApiError.not_found("Unknown or unconfigured OAuth provider")

    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if error or not code or not state or not cookie_state or not secrets.compare_digest(state, cookie_state):
        logger.warning("OAuth callback rejected for provider=%s: error=%s state_match=%s", provider, error, state == cookie_state)
        return _failure_redirect("invalid_state")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        token_resp = await client.post(
            cfg.token_url,
            data={
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "code": code,
                "redirect_uri": cfg.redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            logger.warning("OAuth token exchange failed for provider=%s: %s", provider, token_resp.text[:500])
            return _failure_redirect("token_exchange_failed")

        provider_access_token = token_resp.json().get("access_token")
        if not provider_access_token:
            return _failure_redirect("token_exchange_failed")

        identity = await _extract_identity(provider, client, provider_access_token)

    if identity is None:
        return _failure_redirect("userinfo_failed")

    provider_account_id, email, email_verified, name = identity
    now = datetime.now(UTC)

    oauth_account = (
        await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
    ).scalar_one_or_none()

    if oauth_account is not None:
        user = await db.get(User, oauth_account.user_id)
    else:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            # Brand-new account — the password is a random value nobody
            # knows and can never be typed; this user authenticates via
            # OAuth only, unless they later use forgot-password to set a
            # real one.
            user = User(
                id=uuid.uuid4(), name=name, email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role="client", is_active=True,
                is_email_verified=email_verified,
                email_verified_at=now if email_verified else None,
            )
            db.add(user)
            await db.flush()
        elif email_verified and not user.is_email_verified:
            # Linking to a pre-existing account only trusts the provider's
            # own verified-email claim — an unverified email is never good
            # enough to silently claim someone else's existing account.
            user.is_email_verified = True
            user.email_verified_at = now

        oauth_account = OAuthAccount(user_id=user.id, provider=provider, provider_account_id=provider_account_id, email=email)
        db.add(oauth_account)
        await db.commit()
        await db.refresh(user)

    if user is None or not user.is_active:
        return _failure_redirect("account_unavailable")

    if settings.mfa_enabled and user.mfa_enabled:
        # OAuth bypasses the password step but not a second factor the
        # account owner explicitly turned on — same MFA-challenge handoff as
        # the password-login path, just delivered via cookie instead of a
        # JSON body since this is a full-page redirect.
        mfa_token = secrets.token_urlsafe(32)
        db.add(MfaChallenge(user_id=user.id, token_hash=hash_token(mfa_token), expires_at=now + timedelta(minutes=5)))
        await db.commit()
        resp = RedirectResponse(f"{_success_redirect_url()}?mfa_required=1", status_code=302)
        resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        resp.set_cookie(
            MFA_PENDING_COOKIE, mfa_token, max_age=300,
            httponly=True, secure=SECURE_COOKIES, samesite="lax", path="/",
        )
        return resp

    await record_successful_login(db, user)
    access_token, refresh_token, _session = await create_session(
        db, user, get_client_ip(request), request.headers.get("user-agent"),
    )
    resp = RedirectResponse(_success_redirect_url(), status_code=302)
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    set_session_cookies(resp, access_token, refresh_token, csrf_token=secrets.token_urlsafe(32))
    return resp
