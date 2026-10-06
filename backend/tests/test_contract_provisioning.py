"""Unit tests for contracts.py's client-provisioning helpers.

Extracted during this engagement's DRY/KISS/SOLID review from a single
~75-line function (`provision_client_account`) that mixed five
responsibilities — account creation, local User row, password-reset email,
welcome email, Client row creation — with no test coverage at all beyond an
auth-required smoke test on the HTTP endpoint. These tests target the three
extracted functions directly, which is the point of splitting them: each is
now testable in isolation without mocking the entire chain at once.

Updated for the Supabase Auth -> CoreFusion Auth migration: account creation
is now fully local (no external identity provider call to mock), and the
welcome email issues a real CoreFusion password-reset token instead of
calling Supabase's `reset_password_for_email`.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.password import verify_password
from app.models.client import Client
from app.models.employee import Employee
from app.models.lead import Lead
from app.models.user import User
from app.services.client_provisioning import (
    get_or_create_client_record,
    get_or_create_client_user,
    provision_client_account,
    send_client_welcome,
)


def _make_lead(**overrides) -> Lead:
    defaults = dict(
        id=uuid.uuid4(),
        contact_name="Jane Client",
        email="jane@example.com",
        phone="+1-555-0100",
        company="Acme Co",
        owner_id=None,
    )
    defaults.update(overrides)
    return Lead(**defaults)


class TestGetOrCreateClientUser:
    @pytest.mark.asyncio
    async def test_returns_existing_user_without_creating(self):
        lead = _make_lead()
        existing = User(id=uuid.uuid4(), name="Jane", email=lead.email, password_hash="x", role="client")
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result

        user, created = await get_or_create_client_user(mock_db, lead)

        assert user is existing
        assert created is False
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_local_user_when_none_exists(self):
        lead = _make_lead()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        user, created = await get_or_create_client_user(mock_db, lead)

        assert created is True
        assert user.email == lead.email
        assert user.role == "client"
        # The placeholder password is a real Argon2id hash of an unguessable
        # random value the caller never sees — never usable to log in with,
        # by design (the real password is set via the reset link
        # send_client_welcome issues).
        assert user.password_hash.startswith("$argon2id$")
        assert not verify_password("", user.password_hash)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()


class TestSendClientWelcome:
    @pytest.mark.asyncio
    async def test_triggers_password_reset_token_and_welcome_email(self):
        lead = _make_lead()
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, password_hash="x", role="client")
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.services.client_provisioning.send_password_reset_email", new_callable=AsyncMock) as mock_reset_email:
            with patch("app.services.client_provisioning.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
                await send_client_welcome(mock_db, user, lead)

        mock_db.add.assert_called_once()  # the PasswordResetToken row
        mock_reset_email.assert_awaited_once()
        mock_welcome.assert_awaited_once_with(lead.contact_name, lead.email)

    @pytest.mark.asyncio
    async def test_swallows_reset_email_failure(self):
        lead = _make_lead()
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, password_hash="x", role="client")
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.services.client_provisioning.send_password_reset_email", side_effect=Exception("smtp down")):
            with patch("app.services.client_provisioning.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
                await send_client_welcome(mock_db, user, lead)  # must not raise
        mock_welcome.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_welcome_email_failure(self):
        lead = _make_lead()
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, password_hash="x", role="client")
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.services.client_provisioning.send_password_reset_email", new_callable=AsyncMock) as mock_reset_email:
            with patch("app.services.client_provisioning.send_welcome_email", side_effect=Exception("smtp down")):
                await send_client_welcome(mock_db, user, lead)  # must not raise
        mock_reset_email.assert_awaited_once()


class TestGetOrCreateClientRecord:
    @pytest.mark.asyncio
    async def test_returns_existing_client_without_creating(self):
        lead = _make_lead()
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, role="client")
        existing_client = Client(id=uuid.uuid4(), user_id=user.id)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_client
        mock_db.execute.return_value = mock_result

        client = await get_or_create_client_record(mock_db, user, lead)

        assert client is existing_client
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_client_linked_to_lead_owners_employee_record(self):
        lead = _make_lead(owner_id=uuid.uuid4())
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, role="client")
        account_mgr_employee = Employee(id=uuid.uuid4(), user_id=lead.owner_id, employee_code="EMP-1")

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        employee_result = MagicMock()
        employee_result.scalar_one_or_none.return_value = account_mgr_employee
        client_result = MagicMock()
        client_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [employee_result, client_result]

        client = await get_or_create_client_record(mock_db, user, lead)

        assert client.user_id == user.id
        assert client.company_name == lead.company
        assert client.account_manager_id == account_mgr_employee.id
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_client_with_no_account_manager_when_lead_has_no_owner(self):
        lead = _make_lead(owner_id=None)
        user = User(id=uuid.uuid4(), name="Jane", email=lead.email, role="client")

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        client_result = MagicMock()
        client_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = client_result

        client = await get_or_create_client_record(mock_db, user, lead)

        assert client.account_manager_id is None


class TestProvisionClientAccount:
    """Orchestration: the welcome email must fire only for a genuinely new
    account, never for a reused existing one — this was the exact behavior
    the original nested-if implementation encoded implicitly."""

    @pytest.mark.asyncio
    async def test_sends_welcome_email_only_when_account_is_new(self):
        lead = _make_lead()
        new_user = User(id=uuid.uuid4(), name="Jane", email=lead.email, role="client")
        client = Client(id=uuid.uuid4(), user_id=new_user.id)

        with patch("app.services.client_provisioning.get_or_create_client_user", return_value=(new_user, True)):
            with patch("app.services.client_provisioning.send_client_welcome") as mock_welcome:
                with patch("app.services.client_provisioning.get_or_create_client_record", return_value=client) as mock_record:
                    result = await provision_client_account(AsyncMock(), lead)

        assert result is client
        mock_welcome.assert_awaited_once()
        assert mock_welcome.call_args[0][1] is new_user
        assert mock_welcome.call_args[0][2] is lead
        mock_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_welcome_email_for_reused_account(self):
        lead = _make_lead()
        existing_user = User(id=uuid.uuid4(), name="Jane", email=lead.email, role="client")
        client = Client(id=uuid.uuid4(), user_id=existing_user.id)

        with patch("app.services.client_provisioning.get_or_create_client_user", return_value=(existing_user, False)):
            with patch("app.services.client_provisioning.send_client_welcome") as mock_welcome:
                with patch("app.services.client_provisioning.get_or_create_client_record", return_value=client):
                    result = await provision_client_account(AsyncMock(), lead)

        assert result is client
        mock_welcome.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_and_skips_everything_when_user_cannot_be_resolved(self):
        lead = _make_lead()
        with patch("app.services.client_provisioning.get_or_create_client_user", return_value=(None, False)):
            with patch("app.services.client_provisioning.send_client_welcome") as mock_welcome:
                with patch("app.services.client_provisioning.get_or_create_client_record") as mock_record:
                    result = await provision_client_account(AsyncMock(), lead)

        assert result is None
        mock_welcome.assert_not_called()
        mock_record.assert_not_called()
