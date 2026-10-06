"""Unit tests for cookie-based auth: login/refresh/logout cookie handling,
and the CSRF double-submit middleware.

Auth is httpOnly-cookie-based (core/cookies.py, core/dependencies.py) and,
since the Supabase Auth -> CoreFusion Auth migration, session issuance and
verification are fully local (app/services/auth_service.py) — no external
identity provider is mocked here anymore, the real local logic runs against
a mocked database session.
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response

from app.core.cookies import ACCESS_TOKEN_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_TOKEN_COOKIE
from app.core.csrf import CSRFMiddleware
from app.core.errors import ApiError
from app.core.password import hash_password
from app.models.user import User
from app.models.user_session import UserSession
from app.routers.auth import login, logout, refresh
from app.schemas.auth import LoginRequest


def _mock_request(cookies: dict | None = None, method: str = "GET") -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    request.method = method
    request.headers = {}
    return request


def _make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(), name="Jane", email="jane@example.com",
        password_hash=hash_password("password123"),
        role="client", is_active=True, is_email_verified=True,
        failed_login_attempts=0, is_locked=False, locked_until=None,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return User(**defaults)


def _live_session(user_id: uuid.UUID, refresh_hash: str = "r", previous_refresh_hash: str | None = None) -> UserSession:
    return UserSession(
        id=uuid.uuid4(), user_id=user_id, session_token_hash="h", refresh_token_hash=refresh_hash,
        previous_refresh_token_hash=previous_refresh_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


class TestLoginSetsCookies:
    @pytest.mark.asyncio
    async def test_successful_login_sets_httponly_session_cookies_not_body_tokens(self):
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        payload = LoginRequest(email=user.email, password="password123")

        result = await login(_mock_request(), response, payload, mock_db)

        # Never in the body — that would defeat httpOnly's whole point.
        assert "access_token" not in result["data"].model_dump()
        assert "refresh_token" not in result["data"].model_dump()

        set_cookie_headers = response.headers.getlist("set-cookie")
        joined = " ".join(set_cookie_headers)
        assert f"{ACCESS_TOKEN_COOKIE}=" in joined
        assert f"{REFRESH_TOKEN_COOKIE}=" in joined
        assert CSRF_COOKIE in joined
        # httpOnly on the two session cookies, not on the CSRF cookie.
        access_cookie_line = next(h for h in set_cookie_headers if h.startswith(ACCESS_TOKEN_COOKIE))
        csrf_cookie_line = next(h for h in set_cookie_headers if h.startswith(CSRF_COOKIE))
        assert "httponly" in access_cookie_line.lower()
        assert "httponly" not in csrf_cookie_line.lower()

    @pytest.mark.asyncio
    async def test_wrong_password_raises_unauthorized_without_setting_cookies(self):
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        payload = LoginRequest(email=user.email, password="wrong-password")

        with pytest.raises(ApiError) as exc_info:
            await login(_mock_request(), response, payload, mock_db)

        assert exc_info.value.status_code == 401
        assert not response.headers.getlist("set-cookie")

    @pytest.mark.asyncio
    async def test_unknown_email_raises_unauthorized_same_as_wrong_password(self):
        """No email-enumeration oracle: unknown-email and wrong-password both
        surface as the identical 401."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = Response()
        payload = LoginRequest(email="nobody@example.com", password="anything")

        with pytest.raises(ApiError) as exc_info:
            await login(_mock_request(), response, payload, mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.message == "Invalid email or password"

    @pytest.mark.asyncio
    async def test_deactivated_account_rejected_after_password_check(self):
        user = _make_user(is_active=False)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        payload = LoginRequest(email=user.email, password="password123")

        with pytest.raises(ApiError) as exc_info:
            await login(_mock_request(), response, payload, mock_db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_locked_account_rejected_even_with_correct_password(self):
        user = _make_user(is_locked=True, locked_until=datetime.now(UTC) + timedelta(minutes=10))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        payload = LoginRequest(email=user.email, password="password123")

        with pytest.raises(ApiError) as exc_info:
            await login(_mock_request(), response, payload, mock_db)
        assert exc_info.value.status_code == 403
        assert "locked" in exc_info.value.message.lower()


class TestLogoutClearsCookies:
    @pytest.mark.asyncio
    async def test_clears_all_session_cookies(self):
        user_id = uuid.uuid4()
        request = _mock_request({ACCESS_TOKEN_COOKIE: "the-real-token"}, method="POST")
        response = Response()
        current_user = _make_user(id=user_id)
        session = _live_session(user_id)

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        with patch("app.routers.auth.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = session
            await logout(request, response, mock_db, current_user)

        assert session.revoked_at is not None
        joined = " ".join(response.headers.getlist("set-cookie"))
        for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_COOKIE):
            assert name in joined

    @pytest.mark.asyncio
    async def test_clears_cookies_even_when_no_matching_session_found(self):
        """A cookie for an already-expired/revoked session must still result
        in cleared cookies client-side, not an error."""
        request = _mock_request({ACCESS_TOKEN_COOKIE: "stale-token"}, method="POST")
        response = Response()
        current_user = _make_user()

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        with patch("app.routers.auth.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = None
            await logout(request, response, mock_db, current_user)  # must not raise

        assert ACCESS_TOKEN_COOKIE in " ".join(response.headers.getlist("set-cookie"))


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    async def test_no_refresh_cookie_raises_unauthorized(self):
        with pytest.raises(ApiError) as exc_info:
            await refresh(_mock_request(method="POST"), Response(), AsyncMock())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_refresh_token_issues_new_cookies(self):
        user = _make_user()
        session = _live_session(user.id, refresh_hash="hash-of-old-refresh")

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        found = MagicMock()
        found.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = found
        mock_db.get.return_value = user

        request = _mock_request({REFRESH_TOKEN_COOKIE: "old-refresh"}, method="POST")
        response = Response()

        with patch("app.services.auth_service.hash_token", return_value="hash-of-old-refresh"):
            await refresh(request, response, mock_db)

        joined = " ".join(response.headers.getlist("set-cookie"))
        assert f"{ACCESS_TOKEN_COOKIE}=" in joined
        assert f"{REFRESH_TOKEN_COOKIE}=" in joined

    @pytest.mark.asyncio
    async def test_unknown_refresh_token_clears_cookies_and_401s(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        no_match = MagicMock()
        no_match.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_match

        request = _mock_request({REFRESH_TOKEN_COOKIE: "never-issued"}, method="POST")
        response = Response()

        with pytest.raises(ApiError) as exc_info:
            await refresh(request, response, mock_db)

        assert exc_info.value.status_code == 401
        # Even on failure, stale cookies are cleared rather than left in place.
        assert ACCESS_TOKEN_COOKIE in " ".join(response.headers.getlist("set-cookie"))


class TestCSRFMiddleware:
    @pytest.mark.asyncio
    async def test_blocks_state_changing_request_with_session_cookie_but_no_csrf_header(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "token", CSRF_COOKIE: "csrf-value"}, method="POST")
        request.headers = {}
        middleware = CSRFMiddleware(app=AsyncMock())
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 403
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocks_when_csrf_header_does_not_match_cookie(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "token", CSRF_COOKIE: "csrf-value"}, method="POST")
        request.headers = {CSRF_HEADER: "wrong-value"}
        middleware = CSRFMiddleware(app=AsyncMock())
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 403
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_state_changing_request_with_matching_csrf_header(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "token", CSRF_COOKIE: "csrf-value"}, method="POST")
        request.headers = {CSRF_HEADER: "csrf-value"}
        middleware = CSRFMiddleware(app=AsyncMock())
        call_next = AsyncMock(return_value="the-response")

        result = await middleware.dispatch(request, call_next)

        assert result == "the-response"
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_check_when_no_session_cookie_present(self):
        """Login/register are unauthenticated POSTs — nothing to CSRF-protect
        yet, so they must not be blocked just for lacking a CSRF header."""
        request = _mock_request({}, method="POST")
        request.headers = {}
        middleware = CSRFMiddleware(app=AsyncMock())
        call_next = AsyncMock(return_value="the-response")

        result = await middleware.dispatch(request, call_next)

        assert result == "the-response"
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_check_for_get_requests(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "token"}, method="GET")
        request.headers = {}
        middleware = CSRFMiddleware(app=AsyncMock())
        call_next = AsyncMock(return_value="the-response")

        result = await middleware.dispatch(request, call_next)

        assert result == "the-response"
        call_next.assert_called_once()
