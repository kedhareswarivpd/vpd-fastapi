"""Router-level tests for social login (app/routers/oauth.py) — mocked DB and
mocked httpx calls to the provider (no real network), same pattern as
test_cookie_auth.py/test_mfa_auth_flow.py. Covers: the global/per-provider
kill switches, CSRF state-mismatch rejection, new-account creation, linking
an OAuth identity to a pre-existing account by email, and the MFA handoff for
an OAuth login when the account has MFA enabled.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.errors import ApiError
from app.core.password import hash_password
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.routers.oauth import OAUTH_STATE_COOKIE, oauth_callback, oauth_login


def _mock_request(cookies: dict | None = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    request.headers = {}
    request.client = None
    return request


def _make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(), name="Jane", email="jane@example.com",
        password_hash=hash_password("whatever"),
        role="client", is_active=True, is_email_verified=False,
        mfa_enabled=False, mfa_secret_encrypted=None,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return User(**defaults)


def _mock_httpx_client(token_json: dict, userinfo_json: dict, emails_json: list | None = None):
    """Builds a mock for `async with httpx.AsyncClient(...) as client:` whose
    .post() (token exchange) and .get() (userinfo / github emails) calls
    return canned responses, keyed by URL."""

    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = token_json

    userinfo_resp = MagicMock(status_code=200)
    userinfo_resp.json.return_value = userinfo_json

    emails_resp = MagicMock(status_code=200)
    emails_resp.json.return_value = emails_json or []

    client = AsyncMock()
    client.post.return_value = token_resp

    async def _get(url, **kwargs):
        if "user/emails" in url:
            return emails_resp
        return userinfo_resp

    client.get.side_effect = _get

    @asynccontextmanager
    async def _factory(*args, **kwargs):
        yield client

    return _factory


@pytest.fixture(autouse=True)
def _oauth_globally_on(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", True)
    monkeypatch.setattr(settings, "oauth_google_client_id", "gid")
    monkeypatch.setattr(settings, "oauth_google_client_secret", "gsecret")
    monkeypatch.setattr(settings, "oauth_google_redirect_uri", "https://api.example.com/api/v1/auth/oauth/google/callback")
    yield


class TestGlobalAndProviderSwitches:
    @pytest.mark.asyncio
    async def test_login_404s_when_globally_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "oauth_enabled", False)
        with pytest.raises(ApiError) as exc_info:
            await oauth_login("google", _mock_request())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_login_404s_for_unconfigured_provider(self):
        with pytest.raises(ApiError) as exc_info:
            await oauth_login("github", _mock_request())  # github client id/secret not set in this fixture
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_login_redirects_to_google_with_state_cookie(self):
        result = await oauth_login("google", _mock_request())
        assert result.status_code == 302
        assert "accounts.google.com" in result.headers["location"]
        assert "client_id=gid" in result.headers["location"]
        assert OAUTH_STATE_COOKIE in " ".join(result.headers.getlist("set-cookie"))


class TestCallbackStateValidation:
    @pytest.mark.asyncio
    async def test_missing_state_cookie_redirects_to_failure(self):
        result = await oauth_callback("google", _mock_request(), code="abc", state="xyz", db=AsyncMock())
        assert result.status_code == 302
        assert "oauth_error" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_mismatched_state_redirects_to_failure(self):
        request = _mock_request({OAUTH_STATE_COOKIE: "cookie-value"})
        result = await oauth_callback("google", request, code="abc", state="different-value", db=AsyncMock())
        assert result.status_code == 302
        assert "oauth_error" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_provider_error_param_redirects_to_failure(self):
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        result = await oauth_callback("google", request, code=None, state="s", error="access_denied", db=AsyncMock())
        assert result.status_code == 302
        assert "oauth_error" in result.headers["location"]


class TestCallbackAccountCreationAndLinking:
    @pytest.mark.asyncio
    async def test_new_google_identity_creates_a_new_local_user(self):
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        no_existing_oauth = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        no_existing_user = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.side_effect = [no_existing_oauth, no_existing_user]

        client_factory = _mock_httpx_client(
            token_json={"access_token": "provider-access-token"},
            userinfo_json={"sub": "google-123", "email": "new@example.com", "email_verified": True, "name": "New User"},
        )
        with patch("app.routers.oauth.httpx.AsyncClient", client_factory):
            result = await oauth_callback("google", request, code="abc", state="s", db=mock_db)

        assert result.status_code == 302
        assert f"{ACCESS_TOKEN_COOKIE}=" in " ".join(result.headers.getlist("set-cookie"))
        added_objects = [c.args[0] for c in mock_db.add.call_args_list]
        created_user = next(o for o in added_objects if isinstance(o, User))
        created_link = next(o for o in added_objects if isinstance(o, OAuthAccount))
        assert created_user.email == "new@example.com"
        assert created_user.is_email_verified is True  # Google's email_verified claim trusted
        assert created_link.provider == "google"
        assert created_link.provider_account_id == "google-123"

    @pytest.mark.asyncio
    async def test_existing_user_by_email_gets_linked_not_duplicated(self):
        existing_user = _make_user(email="existing@example.com", is_email_verified=False)
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        no_existing_oauth = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        found_user = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user))
        mock_db.execute.side_effect = [no_existing_oauth, found_user]

        client_factory = _mock_httpx_client(
            token_json={"access_token": "provider-access-token"},
            userinfo_json={"sub": "google-999", "email": "existing@example.com", "email_verified": True, "name": "Existing"},
        )
        with patch("app.routers.oauth.httpx.AsyncClient", client_factory):
            result = await oauth_callback("google", request, code="abc", state="s", db=mock_db)

        assert result.status_code == 302
        # Linked to the pre-existing user, not a freshly-created one.
        added_objects = [c.args[0] for c in mock_db.add.call_args_list]
        assert not any(isinstance(o, User) for o in added_objects)
        created_link = next(o for o in added_objects if isinstance(o, OAuthAccount))
        assert created_link.user_id == existing_user.id
        # Google's verified claim upgrades the existing account's verification state.
        assert existing_user.is_email_verified is True

    @pytest.mark.asyncio
    async def test_already_linked_identity_reuses_the_same_user_without_creating_anything(self):
        user = _make_user()
        link = OAuthAccount(id=uuid.uuid4(), user_id=user.id, provider="google", provider_account_id="google-1", email=user.email)
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        found_link = MagicMock(scalar_one_or_none=MagicMock(return_value=link))
        mock_db.execute.return_value = found_link
        mock_db.get.return_value = user

        client_factory = _mock_httpx_client(
            token_json={"access_token": "provider-access-token"},
            userinfo_json={"sub": "google-1", "email": user.email, "email_verified": True, "name": user.name},
        )
        with patch("app.routers.oauth.httpx.AsyncClient", client_factory):
            result = await oauth_callback("google", request, code="abc", state="s", db=mock_db)

        assert result.status_code == 302
        assert f"{ACCESS_TOKEN_COOKIE}=" in " ".join(result.headers.getlist("set-cookie"))
        # A new session is created for the login itself (expected), but no
        # new User or OAuthAccount — this is a pure lookup + login, no
        # account creation or re-linking.
        added_objects = [c.args[0] for c in mock_db.add.call_args_list]
        assert not any(isinstance(o, (User, OAuthAccount)) for o in added_objects)

    @pytest.mark.asyncio
    async def test_mfa_enabled_account_gets_challenge_cookie_instead_of_session(self):
        from cryptography.fernet import Fernet

        from app.core.mfa import encrypt_secret, generate_totp_secret

        settings.mfa_enabled = True
        settings.mfa_encryption_key = Fernet.generate_key().decode()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(generate_totp_secret()))
        link = OAuthAccount(id=uuid.uuid4(), user_id=user.id, provider="google", provider_account_id="google-1", email=user.email)
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        found_link = MagicMock(scalar_one_or_none=MagicMock(return_value=link))
        mock_db.execute.return_value = found_link
        mock_db.get.return_value = user

        client_factory = _mock_httpx_client(
            token_json={"access_token": "provider-access-token"},
            userinfo_json={"sub": "google-1", "email": user.email, "email_verified": True, "name": user.name},
        )
        try:
            with patch("app.routers.oauth.httpx.AsyncClient", client_factory):
                result = await oauth_callback("google", request, code="abc", state="s", db=mock_db)
        finally:
            settings.mfa_enabled = False

        assert result.status_code == 302
        assert "mfa_required=1" in result.headers["location"]
        assert ACCESS_TOKEN_COOKIE not in " ".join(result.headers.getlist("set-cookie"))
        assert "cf_mfa_pending_token" in " ".join(result.headers.getlist("set-cookie"))

    @pytest.mark.asyncio
    async def test_token_exchange_failure_redirects_to_failure_not_500(self):
        request = _mock_request({OAUTH_STATE_COOKIE: "s"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        failed_token_resp = MagicMock(status_code=400, text="invalid_grant")

        @asynccontextmanager
        async def _factory(*args, **kwargs):
            client = AsyncMock()
            client.post.return_value = failed_token_resp
            yield client

        with patch("app.routers.oauth.httpx.AsyncClient", _factory):
            result = await oauth_callback("google", request, code="abc", state="s", db=mock_db)

        assert result.status_code == 302
        assert "oauth_error" in result.headers["location"]
