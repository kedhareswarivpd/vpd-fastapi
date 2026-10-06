"""Router-level tests for the MFA-enabled login branch and the mfa/* endpoints
— same mocked-db pattern as test_cookie_auth.py. Verifies the global
MFA_ENABLED switch actually gates the feature end-to-end (404 when off,
regardless of any per-account state), and that the password-login ->
MFA-challenge -> verify-login handoff behaves correctly when on.
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi import Request, Response

from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.errors import ApiError
from app.core.mfa import encrypt_secret, generate_totp_secret
from app.core.password import hash_password
from app.models.mfa_challenge import MfaChallenge
from app.models.user import User
from app.routers.auth import (
    login,
    mfa_disable,
    mfa_enable,
    mfa_setup,
    mfa_status,
    mfa_verify_login,
)
from app.schemas.auth import (
    LoginRequest,
    MfaDisableRequest,
    MfaEnableRequest,
    MfaVerifyLoginRequest,
)


def _mock_request(cookies: dict | None = None, method: str = "POST") -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    request.method = method
    request.headers = {}
    request.client = None
    return request


def _make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(), name="Jane", email="jane@example.com",
        password_hash=hash_password("password123"),
        role="client", is_active=True, is_email_verified=True,
        failed_login_attempts=0, is_locked=False, locked_until=None,
        mfa_enabled=False, mfa_secret_encrypted=None, mfa_enabled_at=None,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return User(**defaults)


@pytest.fixture(autouse=True)
def _mfa_globally_on(monkeypatch):
    monkeypatch.setattr(settings, "mfa_enabled", True)
    monkeypatch.setattr(settings, "mfa_encryption_key", Fernet.generate_key().decode())
    yield


class TestGlobalSwitch:
    @pytest.mark.asyncio
    async def test_mfa_endpoints_404_when_globally_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "mfa_enabled", False)
        user = _make_user()
        with pytest.raises(ApiError) as exc_info:
            await mfa_setup(_mock_request(), AsyncMock(), user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_status_reports_unavailable_when_globally_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "mfa_enabled", False)
        user = _make_user()
        result = await mfa_status(user)
        assert result["data"].available is False

    @pytest.mark.asyncio
    async def test_login_never_branches_into_mfa_when_globally_disabled(self, monkeypatch):
        """Even an account with mfa_enabled=True on the row itself must log
        in normally if the global switch is off — the DB flag alone is never
        enough to trigger the challenge path."""
        monkeypatch.setattr(settings, "mfa_enabled", False)
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(generate_totp_secret()))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        result = await login(_mock_request(), response, LoginRequest(email=user.email, password="password123"), mock_db)

        assert "mfa_required" not in result["data"].model_dump()
        assert f"{ACCESS_TOKEN_COOKIE}=" in " ".join(response.headers.getlist("set-cookie"))


class TestLoginWithMfaEnabled:
    @pytest.mark.asyncio
    async def test_correct_password_returns_challenge_not_a_session(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        response = Response()
        result = await login(_mock_request(), response, LoginRequest(email=user.email, password="password123"), mock_db)

        assert result["data"].mfa_required is True
        assert result["data"].mfa_token
        # No session cookies yet — login isn't complete until MFA verifies.
        assert not response.headers.getlist("set-cookie")

    @pytest.mark.asyncio
    async def test_wrong_password_still_401s_before_any_mfa_challenge(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await login(_mock_request(), Response(), LoginRequest(email=user.email, password="wrong"), mock_db)
        assert exc_info.value.status_code == 401


class TestMfaVerifyLogin:
    @pytest.mark.asyncio
    async def test_valid_totp_code_completes_login(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        challenge = MfaChallenge(
            id=uuid.uuid4(), user_id=user.id, token_hash="th",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        challenge_result = MagicMock()
        challenge_result.scalar_one_or_none.return_value = challenge
        mock_db.execute.return_value = challenge_result
        mock_db.get.return_value = user

        code = pyotp.totp.TOTP(secret).now()
        response = Response()
        with patch("app.routers.auth.hash_token", return_value="th"):
            result = await mfa_verify_login(
                _mock_request(), response,
                MfaVerifyLoginRequest(mfa_token="the-challenge-token", code=code),
                mock_db,
            )

        assert result["message"] == "Logged in successfully"
        assert f"{ACCESS_TOKEN_COOKIE}=" in " ".join(response.headers.getlist("set-cookie"))
        assert challenge.used_at is not None

    @pytest.mark.asyncio
    async def test_invalid_code_rejected_and_challenge_not_consumed_for_reuse(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        challenge = MfaChallenge(
            id=uuid.uuid4(), user_id=user.id, token_hash="th",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        challenge_result = MagicMock()
        challenge_result.scalar_one_or_none.return_value = challenge
        # Second execute() call (backup-code lookup) finds nothing.
        no_backup = MagicMock()
        no_backup.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [challenge_result, no_backup]
        mock_db.get.return_value = user

        with patch("app.routers.auth.hash_token", return_value="th"), pytest.raises(ApiError) as exc_info:
            await mfa_verify_login(
                _mock_request(), Response(),
                MfaVerifyLoginRequest(mfa_token="the-challenge-token", code="000000"),
                mock_db,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_code_does_not_burn_the_challenge_a_retry_can_still_succeed(self):
        """Regression test for a real bug found via a live drill: the
        challenge lookup used to mark itself used_at on ANY resolution, even
        before the code was checked — so a single typo permanently burned
        the challenge and forced the user back to a fresh login. It must
        only be consumed after a successful code check."""
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        challenge = MfaChallenge(
            id=uuid.uuid4(), user_id=user.id, token_hash="th",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        challenge_result = MagicMock(scalar_one_or_none=MagicMock(return_value=challenge))
        no_backup = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.side_effect = [challenge_result, no_backup, challenge_result]
        mock_db.get.return_value = user

        with patch("app.routers.auth.hash_token", return_value="th"):
            with pytest.raises(ApiError):
                await mfa_verify_login(
                    _mock_request(), Response(),
                    MfaVerifyLoginRequest(mfa_token="tok", code="000000"),
                    mock_db,
                )
            assert challenge.used_at is None  # still usable after the wrong attempt

            code = pyotp.totp.TOTP(secret).now()
            result = await mfa_verify_login(
                _mock_request(), Response(),
                MfaVerifyLoginRequest(mfa_token="tok", code=code),
                mock_db,
            )
        assert result["message"] == "Logged in successfully"
        assert challenge.used_at is not None

    @pytest.mark.asyncio
    async def test_expired_challenge_rejected(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        challenge = MfaChallenge(
            id=uuid.uuid4(), user_id=user.id, token_hash="th",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),  # already expired
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        challenge_result = MagicMock()
        challenge_result.scalar_one_or_none.return_value = challenge
        mock_db.execute.return_value = challenge_result

        with patch("app.routers.auth.hash_token", return_value="th"), pytest.raises(ApiError) as exc_info:
            await mfa_verify_login(
                _mock_request(), Response(),
                MfaVerifyLoginRequest(mfa_token="expired", code="123456"),
                mock_db,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_rejected(self):
        with pytest.raises(ApiError) as exc_info:
            await mfa_verify_login(
                _mock_request(), Response(),
                MfaVerifyLoginRequest(mfa_token=None, code="123456"),
                AsyncMock(),
            )
        assert exc_info.value.status_code == 401


class TestMfaSetupEnableDisable:
    @pytest.mark.asyncio
    async def test_setup_returns_secret_and_otpauth_url(self):
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = await mfa_setup(_mock_request(), mock_db, user)
        assert result["data"].secret
        assert result["data"].otpauth_url.startswith("otpauth://totp/")
        assert user.mfa_secret_encrypted is not None
        assert user.mfa_enabled is False  # not flipped on until /enable

    @pytest.mark.asyncio
    async def test_setup_rejected_if_already_enabled(self):
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(generate_totp_secret()))
        with pytest.raises(ApiError) as exc_info:
            await mfa_setup(_mock_request(), AsyncMock(), user)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_enable_with_correct_code_turns_mfa_on_and_returns_backup_codes(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_secret_encrypted=encrypt_secret(secret))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        code = pyotp.totp.TOTP(secret).now()
        result = await mfa_enable(_mock_request(), MfaEnableRequest(code=code), mock_db, user)

        assert user.mfa_enabled is True
        assert user.mfa_enabled_at is not None
        assert len(result["data"].backup_codes) == 10
        assert len(set(result["data"].backup_codes)) == 10  # all unique

    @pytest.mark.asyncio
    async def test_enable_with_wrong_code_rejected_and_mfa_stays_off(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_secret_encrypted=encrypt_secret(secret))
        with pytest.raises(ApiError) as exc_info:
            await mfa_enable(_mock_request(), MfaEnableRequest(code="000000"), AsyncMock(), user)
        assert exc_info.value.status_code == 401
        assert user.mfa_enabled is False

    @pytest.mark.asyncio
    async def test_enable_without_prior_setup_rejected(self):
        user = _make_user()
        with pytest.raises(ApiError) as exc_info:
            await mfa_enable(_mock_request(), MfaEnableRequest(code="123456"), AsyncMock(), user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_disable_requires_correct_password(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        with pytest.raises(ApiError) as exc_info:
            await mfa_disable(MfaDisableRequest(password="wrong-password"), AsyncMock(), user)
        assert exc_info.value.status_code == 401
        assert user.mfa_enabled is True  # unchanged

    @pytest.mark.asyncio
    async def test_disable_with_correct_password_turns_mfa_off(self):
        secret = generate_totp_secret()
        user = _make_user(mfa_enabled=True, mfa_secret_encrypted=encrypt_secret(secret))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        await mfa_disable(MfaDisableRequest(password="password123"), mock_db, user)
        assert user.mfa_enabled is False
        assert user.mfa_secret_encrypted is None
        assert user.mfa_enabled_at is None
