"""Unit tests for auth dependencies, role checking, and IP resolution."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.dependencies import (
    get_client_ip,
    get_current_user,
    get_optional_user,
    require_roles,
)
from app.core.errors import ApiError
from app.models.user import User
from app.models.user_session import UserSession


def _mock_request(cookies: dict | None = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    return request


def _live_session(user_id: uuid.UUID) -> UserSession:
    return UserSession(
        id=uuid.uuid4(), user_id=user_id, session_token_hash="h", refresh_token_hash="r",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_no_cookie_raises_unauthorized(self):
        with pytest.raises(ApiError) as exc_info:
            await get_current_user(request=_mock_request(), db=AsyncMock())
        assert exc_info.value.status_code == 401
        assert "Authentication token missing" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_no_matching_session_raises_unauthorized(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "invalid-token"})
        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = None
            with pytest.raises(ApiError) as exc_info:
                await get_current_user(request=request, db=AsyncMock())
            assert exc_info.value.status_code == 401
            assert "Invalid or expired session" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_valid_session_returns_user(self):
        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Test", email="test@example.com", password_hash="x", role="client", is_active=True)
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get.return_value = mock_user

        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = _live_session(user_id)
            user = await get_current_user(request=request, db=mock_db)

        assert user is mock_user

    @pytest.mark.asyncio
    async def test_deactivated_user_raises_unauthorized(self):
        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Test", email="test@example.com", password_hash="x", role="client", is_active=False)
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get.return_value = mock_user

        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = _live_session(user_id)
            with pytest.raises(ApiError) as exc_info:
                await get_current_user(request=request, db=mock_db)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_session_for_deleted_user_raises_unauthorized(self):
        """A session can outlive its user row being deleted (e.g. a race
        between an admin delete and an in-flight request) — must not crash,
        must reject cleanly."""
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get.return_value = None

        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = _live_session(uuid.uuid4())
            with pytest.raises(ApiError) as exc_info:
                await get_current_user(request=request, db=mock_db)
            assert exc_info.value.status_code == 401


class TestGetOptionalUser:
    @pytest.mark.asyncio
    async def test_no_cookie_returns_none(self):
        result = await get_optional_user(request=_mock_request(), db=AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_matching_session_returns_none(self):
        request = _mock_request({ACCESS_TOKEN_COOKIE: "invalid-token"})
        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = None
            result = await get_optional_user(request=request, db=AsyncMock())
            assert result is None

    @pytest.mark.asyncio
    async def test_valid_session_returns_user(self):
        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Test", email="test@example.com", password_hash="x", role="client", is_active=True)
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get.return_value = mock_user

        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = _live_session(user_id)
            result = await get_optional_user(request=request, db=mock_db)

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_deactivated_user_returns_none(self):
        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Test", email="test@example.com", password_hash="x", role="client", is_active=False)
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get.return_value = mock_user

        with patch("app.core.dependencies.get_session_by_access_token", new_callable=AsyncMock) as mock_lookup:
            mock_lookup.return_value = _live_session(user_id)
            result = await get_optional_user(request=request, db=mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_error_is_swallowed_and_returns_none(self):
        """get_optional_user backs public routes (get_optional_user is used
        where auth is optional) — an unexpected failure resolving the
        session must degrade to "anonymous", not break the public page."""
        request = _mock_request({ACCESS_TOKEN_COOKIE: "valid-token"})
        with patch("app.core.dependencies.get_session_by_access_token", side_effect=RuntimeError("boom")):
            result = await get_optional_user(request=request, db=AsyncMock())
        assert result is None


class TestRequireRoles:
    @pytest.mark.asyncio
    async def test_super_admin_bypasses_role_check(self):
        mock_user = User(id=uuid.uuid4(), name="Admin", email="admin@example.com", password_hash="x", role="super_admin")
        dependency = require_roles("admin", "hr")

        with patch("app.core.dependencies.get_current_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user
            result = await dependency(current_user=mock_user)

        assert result.role == "super_admin"

    @pytest.mark.asyncio
    async def test_matching_role_returns_user(self):
        mock_user = User(id=uuid.uuid4(), name="HR", email="hr@example.com", password_hash="x", role="hr")
        dependency = require_roles("admin", "hr")

        result = await dependency(current_user=mock_user)
        assert result.role == "hr"

    @pytest.mark.asyncio
    async def test_non_matching_role_raises_forbidden(self):
        mock_user = User(id=uuid.uuid4(), name="Dev", email="dev@example.com", password_hash="x", role="developer")
        dependency = require_roles("admin", "hr")

        with pytest.raises(ApiError) as exc_info:
            await dependency(current_user=mock_user)
        assert exc_info.value.status_code == 403
        assert "permission" in exc_info.value.message.lower()


class TestGetClientIp:
    def test_returns_client_host_by_default(self):
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_returns_x_forwarded_for_when_trusted(self):
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.3.18"}

        with patch.object(settings, "trust_proxy_headers", True):
            ip = get_client_ip(mock_request)
            assert ip == "203.0.113.50"

    def test_ignores_x_forwarded_for_when_not_trusted(self):
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"x-forwarded-for": "203.0.113.50"}

        with patch.object(settings, "trust_proxy_headers", False):
            ip = get_client_ip(mock_request)
            assert ip == "192.168.1.100"

    def test_returns_unknown_when_no_client(self):
        mock_request = MagicMock(spec=Request)
        mock_request.client = None
        mock_request.headers = {}

        ip = get_client_ip(mock_request)
        assert ip == "unknown"
