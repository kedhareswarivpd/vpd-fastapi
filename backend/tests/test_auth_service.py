"""Unit tests for app/services/auth_service.py — session issuance, rotation,
reuse detection, and account lockout. This is the core of the CoreFusion-
owned auth migration, so it gets the deepest test coverage in this pass."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.tokens import hash_token
from app.models.user import User
from app.models.user_session import UserSession
from app.services.auth_service import (
    LOCKOUT_DURATION,
    MAX_FAILED_LOGIN_ATTEMPTS,
    create_session,
    get_session_by_access_token,
    is_account_locked,
    record_failed_login,
    record_successful_login,
    revoke_all_sessions,
    revoke_session,
    rotate_session,
)


def _make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(), name="Jane", email="jane@example.com", password_hash="x", role="client",
        failed_login_attempts=0, is_locked=False, locked_until=None,
    )
    defaults.update(overrides)
    return User(**defaults)


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_returns_plaintext_tokens_and_stores_only_hashes(self):
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        access_token, refresh_token, session = await create_session(mock_db, user, "127.0.0.1", "pytest-agent")

        assert access_token != refresh_token
        assert session.session_token_hash == hash_token(access_token)
        assert session.refresh_token_hash == hash_token(refresh_token)
        # The stored session never holds the plaintext token anywhere.
        assert access_token not in vars(session).values()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_records_ip_and_user_agent(self):
        user = _make_user()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        _, _, session = await create_session(mock_db, user, "203.0.113.5", "Mozilla/5.0")
        assert session.ip_address == "203.0.113.5"
        assert session.user_agent == "Mozilla/5.0"


class TestGetSessionByAccessToken:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_session(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        assert await get_session_by_access_token(mock_db, "some-token") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_revoked_session(self):
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_token_hash="h", refresh_token_hash="r",
            expires_at=datetime.now(UTC) + timedelta(days=1),
            revoked_at=datetime.now(UTC),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = result

        assert await get_session_by_access_token(mock_db, "some-token") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_expired_session(self):
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_token_hash="h", refresh_token_hash="r",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = result

        assert await get_session_by_access_token(mock_db, "some-token") is None

    @pytest.mark.asyncio
    async def test_returns_live_session(self):
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_token_hash="h", refresh_token_hash="r",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = result

        assert await get_session_by_access_token(mock_db, "some-token") is session


class TestRotateSession:
    @pytest.mark.asyncio
    async def test_valid_refresh_rotates_tokens_in_place(self):
        old_refresh_hash = hash_token("old-refresh-token")
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_token_hash="old-access-hash", refresh_token_hash=old_refresh_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = result

        result_tuple = await rotate_session(mock_db, "old-refresh-token", "127.0.0.1", "agent")

        assert result_tuple is not None
        new_access, new_refresh, returned_session = result_tuple
        assert returned_session is session
        # The old refresh hash is retained as "previous" — this is exactly
        # what makes reuse detection possible.
        assert session.previous_refresh_token_hash == old_refresh_hash
        assert session.refresh_token_hash == hash_token(new_refresh)
        assert session.session_token_hash == hash_token(new_access)
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_unknown_token_returns_none(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        no_match = MagicMock()
        no_match.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = no_match

        result = await rotate_session(mock_db, "never-issued-token", "127.0.0.1", "agent")
        assert result is None

    @pytest.mark.asyncio
    async def test_reused_already_rotated_token_is_detected_and_session_revoked(self):
        """The core security property: presenting a refresh token that was
        already rotated away (i.e. stolen-and-replayed) must not mint new
        tokens — it must revoke the session instead."""
        reused_token = "already-rotated-away-token"
        reused_hash = hash_token(reused_token)
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_token_hash="current-access-hash", refresh_token_hash="current-refresh-hash",
            previous_refresh_token_hash=reused_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        # First execute (lookup by current refresh_token_hash) finds nothing;
        # second execute (lookup by previous_refresh_token_hash) finds the session.
        no_current_match = MagicMock()
        no_current_match.scalar_one_or_none.return_value = None
        found_by_previous = MagicMock()
        found_by_previous.scalar_one_or_none.return_value = session
        mock_db.execute.side_effect = [no_current_match, found_by_previous]

        result = await rotate_session(mock_db, reused_token, "attacker-ip", "attacker-agent")

        assert result is None
        assert session.revoked_at is not None
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_expired_session_is_not_rotated(self):
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            session_token_hash="h", refresh_token_hash=hash_token("expired-token"),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        found = MagicMock()
        found.scalar_one_or_none.return_value = session
        no_previous_match = MagicMock()
        no_previous_match.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [found, no_previous_match]

        result = await rotate_session(mock_db, "expired-token", "127.0.0.1", "agent")
        assert result is None


class TestRevokeSession:
    @pytest.mark.asyncio
    async def test_sets_revoked_at(self):
        session = UserSession(
            id=uuid.uuid4(), user_id=uuid.uuid4(), session_token_hash="h", refresh_token_hash="r",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        await revoke_session(mock_db, session)
        assert session.revoked_at is not None
        mock_db.commit.assert_awaited_once()


class TestRevokeAllSessions:
    @pytest.mark.asyncio
    async def test_revokes_every_active_session(self):
        user_id = uuid.uuid4()
        sessions = [
            UserSession(id=uuid.uuid4(), user_id=user_id, session_token_hash=f"h{i}", refresh_token_hash=f"r{i}",
                        expires_at=datetime.now(UTC) + timedelta(days=1))
            for i in range(3)
        ]
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = sessions
        mock_db.execute.return_value = result

        await revoke_all_sessions(mock_db, user_id)

        assert all(s.revoked_at is not None for s in sessions)

    @pytest.mark.asyncio
    async def test_leaves_the_excepted_session_alone(self):
        user_id = uuid.uuid4()
        keep = UserSession(id=uuid.uuid4(), user_id=user_id, session_token_hash="h0", refresh_token_hash="r0",
                            expires_at=datetime.now(UTC) + timedelta(days=1))
        revoke_me = UserSession(id=uuid.uuid4(), user_id=user_id, session_token_hash="h1", refresh_token_hash="r1",
                                 expires_at=datetime.now(UTC) + timedelta(days=1))
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [keep, revoke_me]
        mock_db.execute.return_value = result

        await revoke_all_sessions(mock_db, user_id, except_session_id=keep.id)

        assert keep.revoked_at is None
        assert revoke_me.revoked_at is not None


class TestAccountLockout:
    def test_not_locked_by_default(self):
        user = _make_user()
        assert is_account_locked(user) is False

    def test_locked_with_future_locked_until(self):
        user = _make_user(is_locked=True, locked_until=datetime.now(UTC) + timedelta(minutes=10))
        assert is_account_locked(user) is True

    def test_lock_auto_expires_once_locked_until_passes(self):
        user = _make_user(is_locked=True, locked_until=datetime.now(UTC) - timedelta(seconds=1))
        assert is_account_locked(user) is False

    @pytest.mark.asyncio
    async def test_record_failed_login_increments_counter(self):
        user = _make_user(failed_login_attempts=0)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        await record_failed_login(mock_db, user)
        assert user.failed_login_attempts == 1
        assert user.is_locked is False

    @pytest.mark.asyncio
    async def test_record_failed_login_locks_account_at_threshold(self):
        user = _make_user(failed_login_attempts=MAX_FAILED_LOGIN_ATTEMPTS - 1)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        await record_failed_login(mock_db, user)
        assert user.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS
        assert user.is_locked is True
        assert user.locked_until is not None
        assert user.locked_until <= datetime.now(UTC) + LOCKOUT_DURATION

    @pytest.mark.asyncio
    async def test_record_successful_login_resets_lockout_state(self):
        user = _make_user(
            failed_login_attempts=4, is_locked=True,
            locked_until=datetime.now(UTC) + timedelta(minutes=5),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        await record_successful_login(mock_db, user)
        assert user.failed_login_attempts == 0
        assert user.is_locked is False
        assert user.locked_until is None
        assert user.last_login_at is not None
