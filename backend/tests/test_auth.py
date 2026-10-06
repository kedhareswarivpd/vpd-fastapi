"""Unit tests for auth business logic (not covered by API endpoint tests).

Registration is fully local now (CoreFusion-owned auth — see
app/services/auth_service.py) — there is no external identity provider
dependency left to test failure modes for; these tests target the actual
remaining logic: duplicate-email rejection and successful account creation.
"""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from app.core.errors import ApiError
from app.core.password import verify_password
from app.models.user import User
from app.routers.auth import register
from app.schemas.auth import RegisterRequest


def _refresh_side_effect(obj):
    obj.id = obj.id or "00000000-0000-0000-0000-000000000000"
    obj.created_at = obj.created_at or datetime.now(UTC)
    obj.updated_at = obj.updated_at or datetime.now(UTC)


def _fake_request() -> Request:
    """Minimal ASGI scope so slowapi's rate-limit decorator (which requires a
    real Request) can be satisfied when calling the endpoint function directly."""
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/register",
        "headers": [],
        "client": ("testclient", 123),
        "query_string": b"",
    })


class TestRegister:
    @pytest.mark.asyncio
    async def test_rejects_duplicate_email(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(
            id="00000000-0000-0000-0000-000000000000", name="Existing", email="test@example.com",
            password_hash="x", role="client",
        )
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await register(
                _fake_request(),
                RegisterRequest(name="Test User", email="test@example.com", password="Password123!"),
                db=mock_db,
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_creates_account_with_hashed_password_and_issues_verification_email(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _refresh_side_effect
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_existing

        with patch("app.routers.auth._issue_verification_email", new_callable=AsyncMock) as mock_issue:
            result = await register(
                _fake_request(),
                RegisterRequest(name="Test User", email="new@example.com", password="Password123!"),
                db=mock_db,
            )

        assert result["data"].email == "new@example.com"
        assert result["data"].is_active is True
        mock_db.add.assert_called_once()
        created_user = mock_db.add.call_args[0][0]
        assert isinstance(created_user, User)
        # The plaintext password is never stored — only its hash.
        assert created_user.password_hash != "Password123!"
        assert verify_password("Password123!", created_user.password_hash)
        mock_issue.assert_awaited_once()
