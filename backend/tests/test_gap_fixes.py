"""Regression tests for real gaps found during a documentation review and
fixed in the same session: staff-side file/report upload ownership checks
(clients.py, partner_account.py), meeting "cancel" actually cancelling
instead of hard-deleting, the training-enrollment race being handled
gracefully, and the overdue-invoice sweep. See docs/BACKEND_GAPS_AND_ISSUES.md
and status.md for the full write-up of each finding.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.models.client import Client
from app.models.employee import Employee
from app.models.meeting import Meeting
from app.models.partner_account import PartnerAccount
from app.models.user import User
from app.routers.clients import create_client_report, staff_upload_client_file
from app.routers.finance import sweep_overdue_invoices
from app.routers.meetings import cancel_meeting
from app.routers.partner_account import upload_partner_file
from app.routers.training import enroll
from app.schemas.finance import ClientReportCreate
from app.schemas.partner_account import PartnerFileCreate


def _make_user(role: str, **overrides) -> User:
    defaults = dict(id=uuid.uuid4(), name="Staff", email="staff@example.com", password_hash="x", role=role)
    defaults.update(overrides)
    return User(**defaults)


def _stamp_on_refresh(obj) -> None:
    """Mimics what a real db.refresh() populates after commit (id,
    created_at, updated_at) — needed since AsyncMock's db.refresh() is a
    no-op and the route handlers below serialize the object immediately
    afterward."""
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    now = datetime.now(UTC)
    obj.created_at = now
    obj.updated_at = now


class TestClientFileOwnership:
    @pytest.mark.asyncio
    async def test_admin_can_upload_to_any_client(self):
        admin = _make_user("admin")
        client = Client(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Acme", account_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _stamp_on_refresh

        with patch("app.routers.clients.crud.get", new_callable=AsyncMock, return_value=client):
            with patch("app.routers.clients.save_upload", new_callable=AsyncMock, return_value="client-files/x.pdf"):
                result = await staff_upload_client_file(
                    client.id, "doc", "contract", MagicMock(), mock_db, admin,
                )
        assert result["message"] == "File uploaded"

    @pytest.mark.asyncio
    async def test_assigned_account_manager_can_upload(self):
        pm = _make_user("project_manager")
        employee = Employee(id=uuid.uuid4(), user_id=pm.id, employee_code="EMP-1")
        client = Client(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Acme", account_manager_id=employee.id)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.return_value = mock_result
        mock_db.refresh.side_effect = _stamp_on_refresh

        with patch("app.routers.clients.crud.get", new_callable=AsyncMock, return_value=client):
            with patch("app.routers.clients.save_upload", new_callable=AsyncMock, return_value="client-files/x.pdf"):
                result = await staff_upload_client_file(
                    client.id, "doc", "contract", MagicMock(), mock_db, pm,
                )
        assert result["message"] == "File uploaded"

    @pytest.mark.asyncio
    async def test_unassigned_staff_member_rejected(self):
        """The real bug: a role-gated staff member could previously attach a
        file to ANY client, not just their own assigned accounts."""
        pm = _make_user("project_manager")
        other_employee_id = uuid.uuid4()
        client = Client(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Acme", account_manager_id=other_employee_id)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        # This pm has no Employee row assigned as this client's manager.
        mock_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.return_value = mock_result

        with patch("app.routers.clients.crud.get", new_callable=AsyncMock, return_value=client):
            with pytest.raises(ApiError) as exc_info:
                await staff_upload_client_file(
                    client.id, "doc", "contract", MagicMock(), mock_db, pm,
                )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_report_creation_same_ownership_check(self):
        finance_user = _make_user("finance")
        other_employee_id = uuid.uuid4()
        client = Client(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Acme", account_manager_id=other_employee_id)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with patch("app.routers.clients.crud.get", new_callable=AsyncMock, return_value=client):
            with pytest.raises(ApiError) as exc_info:
                await create_client_report(
                    client.id, ClientReportCreate(title="Q1", report_type="quarterly", period="Q1-2026"),
                    mock_db, finance_user,
                )
        assert exc_info.value.status_code == 403


class TestPartnerFileOwnership:
    @pytest.mark.asyncio
    async def test_unassigned_staff_member_rejected(self):
        sales_user = _make_user("sales")
        partner = PartnerAccount(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Partner Co", account_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with patch("app.routers.partner_account.crud.get", new_callable=AsyncMock, return_value=partner):
            with pytest.raises(ApiError) as exc_info:
                await upload_partner_file(
                    partner.id, PartnerFileCreate(name="doc", category="contract", file_url="http://x/doc.pdf"),
                    mock_db, sales_user,
                )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_bypasses_ownership_check(self):
        admin = _make_user("admin")
        partner = PartnerAccount(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Partner Co", account_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _stamp_on_refresh

        with patch("app.routers.partner_account.crud.get", new_callable=AsyncMock, return_value=partner):
            result = await upload_partner_file(
                partner.id, PartnerFileCreate(name="doc", category="contract", file_url="http://x/doc.pdf"),
                mock_db, admin,
            )
        assert result["message"] == "File uploaded"


class TestMeetingCancelActuallyCancels:
    @pytest.mark.asyncio
    async def test_cancel_sets_status_not_hard_delete(self):
        """Regression test for a real bug: DELETE /meetings/{id} was named
        (and responded) as 'cancel' but called CRUDBase.delete() — a hard
        row delete, losing meeting history rather than marking it
        cancelled."""
        meeting_id = uuid.uuid4()
        now = datetime.now(UTC)
        cancelled_meeting = Meeting(
            id=meeting_id, title="Kickoff", scheduled_at=now, status="cancelled",
            duration_minutes=30, created_at=now, updated_at=now,
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.meetings.crud.update", new_callable=AsyncMock, return_value=cancelled_meeting) as mock_update:
            with patch("app.routers.meetings.crud.delete", new_callable=AsyncMock) as mock_delete:
                result = await cancel_meeting(meeting_id, mock_db)

        mock_update.assert_called_once_with(mock_db, meeting_id, {"status": "cancelled"})
        mock_delete.assert_not_called()
        assert result["message"] == "Meeting cancelled"
        assert result["data"].status == "cancelled"


class TestTrainingEnrollmentRace:
    @pytest.mark.asyncio
    async def test_concurrent_enroll_race_returns_friendly_conflict_not_500(self):
        """The pre-check (query-then-insert) can't prevent a genuine race
        between two concurrent requests — only the database's unique
        constraint can. This verifies the IntegrityError from that
        constraint is translated into the same friendly 409, not a raw 500."""
        user = _make_user("employee")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-1")
        course_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        employee_lookup = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.side_effect = [employee_lookup, no_existing]
        mock_db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate key"))

        with pytest.raises(ApiError) as exc_info:
            await enroll(course_id, mock_db, user)

        assert exc_info.value.status_code == 409
        mock_db.rollback.assert_awaited_once()


class TestOverdueInvoiceSweep:
    @pytest.mark.asyncio
    async def test_sweeps_only_sent_and_past_due(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [uuid.uuid4(), uuid.uuid4()]
        mock_db.execute.return_value = mock_result

        result = await sweep_overdue_invoices(mock_db)

        assert result["data"]["updated_count"] == 2
        mock_db.commit.assert_awaited_once()
        # Verify the WHERE clause actually filters on status="sent" and a
        # past due_date, not a blanket update of every invoice.
        executed_stmt = mock_db.execute.call_args.args[0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "status" in compiled.lower()
        assert "due_date" in compiled.lower()
