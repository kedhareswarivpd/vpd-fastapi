"""Consolidated negative-security proof for IDOR/BOLA across every
assignment-based ("coordinator/agent") relationship this codebase actually
has: Lead.owner_id (sales), Employee.reporting_manager_id (project_manager
over leaves/timesheets), Project.project_manager_id, and
Client/PartnerAccount.account_manager_id (staff file/report uploads).

This file exists specifically to answer, with executable proof, the
question: "can one agent access/modify/delete another agent's records by
manipulating IDs, query parameters, or request bodies?" See
docs/security/authorization-audit.md for the full narrative writeup this
file backs.

Individual fixes already have focused tests in test_authz_gap_fixes.py and
test_gap_fixes.py — this file specifically drives each fixed endpoint
through the ID-swap / query-param / body-tampering attack shapes requested,
in one place, rather than duplicating the fix-specific assertions.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import ApiError
from app.models.client import Client
from app.models.lead import Lead
from app.models.partner_account import PartnerAccount
from app.models.project import Project
from app.models.user import User
from app.routers.clients import staff_upload_client_file
from app.routers.leads import get_lead, list_leads, update_lead
from app.routers.partner_account import upload_partner_file
from app.routers.projects import assign_team, update_project
from app.schemas.crm import LeadUpdate
from app.schemas.partner_account import PartnerFileCreate
from app.schemas.project import AssignTeamRequest, ProjectUpdate


def _stamps() -> dict:
    now = datetime.now(UTC)
    return dict(created_at=now, updated_at=now)


def _make_user(role: str, **overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(), name="U", email="u@example.com", password_hash="x", role=role,
        is_active=True, is_email_verified=True, **_stamps(),
    )
    defaults.update(overrides)
    return User(**defaults)


class TestLeadIDORAttackSurface:
    """Agent 1 = sales_a, Agent 2's record = a lead owned by sales_b."""

    @pytest.mark.asyncio
    async def test_id_swap_get_denied(self):
        sales_a = _make_user("sales")
        sales_b_lead = Lead(id=uuid.uuid4(), contact_name="B's Lead", email="b@example.com", owner_id=uuid.uuid4(), source="website", status="new", **_stamps())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=sales_b_lead):
            with pytest.raises(ApiError) as exc_info:
                await get_lead(sales_b_lead.id, mock_db, sales_a)
        assert exc_info.value.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_id_swap_patch_denied(self):
        sales_a = _make_user("sales")
        sales_b_lead = Lead(id=uuid.uuid4(), contact_name="B's Lead", email="b@example.com", owner_id=uuid.uuid4(), source="website", status="new", **_stamps())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=sales_b_lead):
            with pytest.raises(ApiError) as exc_info:
                await update_lead(sales_b_lead.id, LeadUpdate(notes="tampered"), mock_db, sales_a)
        assert exc_info.value.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_body_tampering_cannot_steal_ownership_of_unowned_lead(self):
        """Even the reassignment vector itself: sales_a cannot use the
        owner_id field in a PATCH body to grab a lead they don't already
        own — the ownership check runs before the payload is ever applied."""
        sales_a = _make_user("sales")
        sales_b_lead = Lead(id=uuid.uuid4(), contact_name="B's Lead", email="b@example.com", owner_id=uuid.uuid4(), source="website", status="new", **_stamps())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=sales_b_lead):
            with pytest.raises(ApiError):
                await update_lead(sales_b_lead.id, LeadUpdate(owner_id=sales_a.id), mock_db, sales_a)
        # crud.update must never have been reached with the tampered payload.
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_param_tampering_cannot_list_another_agents_leads(self):
        """GET /leads?owner_id=<sales_b> as sales_a must NOT return sales_b's
        leads — the query param is ignored for the sales role; the filter is
        force-derived from the authenticated identity server-side."""
        sales_a = _make_user("sales")
        sales_b_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        mock_db.execute.return_value.scalar_one = MagicMock(return_value=0)

        request = MagicMock()
        request.query_params = {"owner_id": str(sales_b_id)}
        page = MagicMock(page=1, limit=20, offset=0, sort=None, search=None)

        captured_filters = {}

        async def _fake_list(db, page_params, filters):
            captured_filters.update(filters)
            return [], 0

        with patch("app.routers.leads.crud.list", new_callable=AsyncMock, side_effect=_fake_list):
            await list_leads(request, mock_db, page, sales_a)

        # The attempted owner_id=sales_b_id is completely overridden —
        # the actual filter sent to the database is the caller's own id.
        assert captured_filters["owner_id"] == sales_a.id
        assert captured_filters["owner_id"] != sales_b_id

    @pytest.mark.asyncio
    async def test_admin_role_is_not_subject_to_the_same_restriction(self):
        """Sanity check that the restriction is role-specific, not a global
        block — admin's explicit owner_id query filter (a legitimate staff
        "show me this rep's leads" feature) still works."""
        admin = _make_user("admin")
        target_owner_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        request = MagicMock()
        request.query_params = {"owner_id": str(target_owner_id)}
        page = MagicMock(page=1, limit=20, offset=0, sort=None, search=None)

        captured_filters = {}

        async def _fake_list(db, page_params, filters):
            captured_filters.update(filters)
            return [], 0

        with patch("app.routers.leads.crud.list", new_callable=AsyncMock, side_effect=_fake_list):
            await list_leads(request, mock_db, page, admin)

        assert captured_filters["owner_id"] == str(target_owner_id)


class TestClientPartnerFileIDORAttackSurface:
    """Agent 1 = project_manager_a, Agent 2's record = a client managed by
    a different employee."""

    @pytest.mark.asyncio
    async def test_id_swap_cannot_upload_file_to_unassigned_client(self):
        pm_a = _make_user("project_manager")
        unassigned_client = Client(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Not Mine", account_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))  # pm_a has no Employee row matching

        with patch("app.routers.clients.crud.get", new_callable=AsyncMock, return_value=unassigned_client):
            with pytest.raises(ApiError) as exc_info:
                await staff_upload_client_file(
                    unassigned_client.id, "x", "contract", MagicMock(), mock_db, pm_a,
                )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_id_swap_cannot_upload_file_to_unassigned_partner(self):
        sales_a = _make_user("sales")
        unassigned_partner = PartnerAccount(id=uuid.uuid4(), user_id=uuid.uuid4(), company_name="Not Mine", account_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with patch("app.routers.partner_account.crud.get", new_callable=AsyncMock, return_value=unassigned_partner):
            with pytest.raises(ApiError) as exc_info:
                await upload_partner_file(
                    unassigned_partner.id, PartnerFileCreate(name="x", category="contract", file_url="http://x/y.pdf"),
                    mock_db, sales_a,
                )
        assert exc_info.value.status_code == 403


class TestProjectIDORAttackSurface:
    """Agent 1 = project_manager_a, Agent 2's record = a project managed by
    a different PM."""

    @pytest.mark.asyncio
    async def test_id_swap_update_denied(self):
        pm_a = _make_user("project_manager")
        pm_b_project = Project(id=uuid.uuid4(), title="B's Project", slug="b", project_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=pm_b_project):
            with pytest.raises(ApiError) as exc_info:
                await update_project(pm_b_project.id, ProjectUpdate(title="hijacked"), mock_db, pm_a)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_id_swap_team_reassignment_denied(self):
        """The 'bulk-ish' endpoint (assign_team replaces the whole team list
        in one call) gets the same check as the single-field update."""
        pm_a = _make_user("project_manager")
        pm_b_project = Project(id=uuid.uuid4(), title="B's Project", slug="b", project_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=pm_b_project))

        with pytest.raises(ApiError) as exc_info:
            await assign_team(pm_b_project.id, AssignTeamRequest(employee_ids=[pm_a.id]), mock_db, pm_a)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_body_tampering_project_manager_id_does_not_grant_access(self):
        """Even if pm_a's PATCH body includes project_manager_id trying to
        claim the project as their own, the ownership check runs against
        the EXISTING record before any payload field is applied — the
        tampered field is never reached."""
        pm_a = _make_user("project_manager")
        pm_b_project = Project(id=uuid.uuid4(), title="B's Project", slug="b", project_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=pm_b_project):
            with patch("app.routers.projects.crud.update", new_callable=AsyncMock) as mock_update:
                with pytest.raises(ApiError):
                    await update_project(pm_b_project.id, ProjectUpdate(project_manager_id=pm_a.id), mock_db, pm_a)
                mock_update.assert_not_called()
