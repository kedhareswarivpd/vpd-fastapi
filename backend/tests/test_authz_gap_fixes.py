"""Regression tests for real IDOR / horizontal-privilege-escalation /
mass-assignment findings from an OWASP-style authorization audit, fixed in
the same session. See docs/BACKEND_GAPS_AND_ISSUES.md and status.md for the
full write-up of each finding.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import ApiError
from app.models.lead import Lead
from app.models.leave import Leave
from app.models.project import Project
from app.models.user import User
from app.routers.employees import (
    list_all_timesheets,
    list_leaves,
    review_leave,
    review_timesheet,
)
from app.routers.leads import update_lead
from app.routers.projects import assign_team, update_project
from app.routers.users import deactivate_user, update_user
from app.schemas.crm import LeadUpdate
from app.schemas.employee import LeaveStatusUpdate, TimesheetStatusUpdate
from app.schemas.project import AssignTeamRequest, ProjectUpdate
from app.schemas.user import UserUpdate


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


def _mock_request(query: dict | None = None) -> MagicMock:
    request = MagicMock()
    request.query_params = query or {}
    return request


class TestLeadUpdateIDOR:
    @pytest.mark.asyncio
    async def test_sales_cannot_patch_a_lead_they_do_not_own(self):
        """The real bug: GET already blocked this, PATCH did not."""
        owner_id = uuid.uuid4()
        attacker = _make_user("sales")
        lead = Lead(id=uuid.uuid4(), contact_name="X", email="x@example.com", owner_id=owner_id)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=lead):
            with pytest.raises(ApiError) as exc_info:
                await update_lead(lead.id, LeadUpdate(owner_id=attacker.id), mock_db, attacker)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_sales_can_patch_their_own_lead(self):
        owner = _make_user("sales")
        lead = Lead(id=uuid.uuid4(), contact_name="X", email="x@example.com", owner_id=owner.id, source="website", status="new", **_stamps())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=lead):
            with patch("app.routers.leads.crud.update", new_callable=AsyncMock, return_value=lead):
                result = await update_lead(lead.id, LeadUpdate(notes="hi"), mock_db, owner)
        assert result["message"] == "Lead updated"

    @pytest.mark.asyncio
    async def test_admin_can_patch_any_lead(self):
        admin = _make_user("admin")
        lead = Lead(id=uuid.uuid4(), contact_name="X", email="x@example.com", owner_id=uuid.uuid4(), source="website", status="new", **_stamps())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=lead):
            with patch("app.routers.leads.crud.update", new_callable=AsyncMock, return_value=lead):
                result = await update_lead(lead.id, LeadUpdate(notes="hi"), mock_db, admin)
        assert result["message"] == "Lead updated"


class TestUserEscalationBoundary:
    @pytest.mark.asyncio
    async def test_hr_cannot_deactivate_an_admin(self):
        hr = _make_user("hr")
        target_admin = _make_user("admin", id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.users.crud.get", new_callable=AsyncMock, return_value=target_admin):
            with pytest.raises(ApiError) as exc_info:
                await deactivate_user(target_admin.id, mock_db, hr)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_can_deactivate_an_admin(self):
        super_admin = _make_user("super_admin")
        target_admin = _make_user("admin", id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.users.crud.get", new_callable=AsyncMock, return_value=target_admin):
            with patch("app.routers.users.crud.update", new_callable=AsyncMock, return_value=target_admin):
                with patch("app.routers.users.revoke_all_sessions", new_callable=AsyncMock):
                    result = await deactivate_user(target_admin.id, mock_db, super_admin)
        assert result["message"] == "User deactivated"

    @pytest.mark.asyncio
    async def test_hr_cannot_modify_an_admin_via_put(self):
        """Real bug: the role check only fired when GRANTING admin/super_admin
        — it never checked whether the TARGET already held one, so HR could
        still edit (e.g. flip is_active on) an existing admin via PUT."""
        hr = _make_user("hr")
        target_admin = _make_user("admin", id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.users.crud.get", new_callable=AsyncMock, return_value=target_admin):
            with pytest.raises(ApiError) as exc_info:
                await update_user(target_admin.id, UserUpdate(is_active=False), mock_db, hr)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_hr_can_still_modify_a_regular_employee(self):
        hr = _make_user("hr")
        target = _make_user("employee", id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.users.crud.get", new_callable=AsyncMock, return_value=target):
            with patch("app.routers.users.crud.update", new_callable=AsyncMock, return_value=target):
                result = await update_user(target.id, UserUpdate(phone="123"), mock_db, hr)
        assert result["message"] == "User updated successfully"


class TestPmTeamScoping:
    @pytest.mark.asyncio
    async def test_pm_cannot_approve_leave_outside_their_team(self):
        pm = _make_user("project_manager")
        other_leave = MagicMock(employee_id=uuid.uuid4())  # not in PM's team
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees.leave_crud.get", new_callable=AsyncMock, return_value=other_leave):
            with patch("app.routers.employees._pm_team_employee_ids", new_callable=AsyncMock, return_value=[]):
                with pytest.raises(ApiError) as exc_info:
                    await review_leave(uuid.uuid4(), LeaveStatusUpdate(status="approved"), mock_db, pm)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_pm_can_approve_own_team_leave(self):
        from datetime import date

        pm = _make_user("project_manager")
        team_employee_id = uuid.uuid4()
        target_leave = Leave(
            id=uuid.uuid4(), employee_id=team_employee_id, type="casual",
            start_date=date.today(), end_date=date.today(), status="approved", **_stamps(),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees.leave_crud.get", new_callable=AsyncMock, return_value=target_leave):
            with patch("app.routers.employees._pm_team_employee_ids", new_callable=AsyncMock, return_value=[team_employee_id]):
                with patch("app.routers.employees.leave_crud.update", new_callable=AsyncMock, return_value=target_leave):
                    result = await review_leave(uuid.uuid4(), LeaveStatusUpdate(status="approved"), mock_db, pm)
        assert result["message"] == "Leave request updated"

    @pytest.mark.asyncio
    async def test_hr_bypasses_team_scoping(self):
        from datetime import date

        hr = _make_user("hr")
        target_leave = Leave(
            id=uuid.uuid4(), employee_id=uuid.uuid4(), type="casual",
            start_date=date.today(), end_date=date.today(), status="approved", **_stamps(),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees.leave_crud.get", new_callable=AsyncMock, return_value=target_leave):
            with patch("app.routers.employees.leave_crud.update", new_callable=AsyncMock, return_value=target_leave):
                result = await review_leave(uuid.uuid4(), LeaveStatusUpdate(status="approved"), mock_db, hr)
        assert result["message"] == "Leave request updated"

    @pytest.mark.asyncio
    async def test_reapproving_decided_leave_does_not_renotify(self):
        """P3 follow-up from the UAT closure pass: a repeated/concurrent
        approve call re-sent the employee notification every time even
        though the leave was already decided. Only the request that
        actually moves the leave out of "pending" should notify."""
        from datetime import date

        hr = _make_user("hr")
        already_approved = Leave(
            id=uuid.uuid4(), employee_id=uuid.uuid4(), type="casual",
            start_date=date.today(), end_date=date.today(), status="approved", **_stamps(),
        )
        mock_db = AsyncMock()

        with patch("app.routers.employees.leave_crud.get", new_callable=AsyncMock, return_value=already_approved):
            with patch("app.routers.employees.leave_crud.update", new_callable=AsyncMock, return_value=already_approved):
                with patch("app.routers.employees.notify_user", new_callable=AsyncMock) as mock_notify:
                    result = await review_leave(uuid.uuid4(), LeaveStatusUpdate(status="approved"), mock_db, hr)
        assert result["message"] == "Leave request updated"
        mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_pm_cannot_approve_timesheet_outside_their_team(self):
        pm = _make_user("project_manager")
        other_timesheet = MagicMock(employee_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees.timesheet_crud.get", new_callable=AsyncMock, return_value=other_timesheet):
            with patch("app.routers.employees._pm_team_employee_ids", new_callable=AsyncMock, return_value=[]):
                with pytest.raises(ApiError) as exc_info:
                    await review_timesheet(uuid.uuid4(), TimesheetStatusUpdate(status="approved"), mock_db, pm)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_pm_list_leaves_scoped_to_team_only(self):
        pm = _make_user("project_manager")
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees._pm_team_employee_ids", new_callable=AsyncMock, return_value=[]):
            result = await list_leaves(_mock_request(), mock_db, MagicMock(page=1, limit=20, offset=0, sort=None), pm)
        # No team members -> empty result, not every leave company-wide.
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_pm_list_timesheets_rejects_foreign_employee_id_filter(self):
        pm = _make_user("project_manager")
        foreign_employee_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.employees._pm_team_employee_ids", new_callable=AsyncMock, return_value=[]):
            with pytest.raises(ApiError) as exc_info:
                await list_all_timesheets(
                    _mock_request({"employee_id": str(foreign_employee_id)}), mock_db,
                    MagicMock(page=1, limit=20, offset=0, sort=None), pm,
                )
        assert exc_info.value.status_code == 403


class TestProjectManagerOwnership:
    @pytest.mark.asyncio
    async def test_pm_cannot_update_a_project_they_do_not_manage(self):
        pm = _make_user("project_manager")
        project = Project(id=uuid.uuid4(), title="Other PM's project", slug="x", project_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with pytest.raises(ApiError) as exc_info:
                await update_project(project.id, ProjectUpdate(title="hacked"), mock_db, pm)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_pm_can_update_their_own_project(self):
        pm = _make_user("project_manager")
        project = Project(
            id=uuid.uuid4(), title="Mine", slug="mine", project_manager_id=pm.id,
            status="planning", progress_percent=0, is_featured=False, is_published=False,
            technology_stack=[], team=[], **_stamps(),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=project))

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with patch("app.routers.projects.crud.update", new_callable=AsyncMock, return_value=project):
                result = await update_project(project.id, ProjectUpdate(title="Mine v2"), mock_db, pm)
        assert result["message"] == "Project updated successfully"

    @pytest.mark.asyncio
    async def test_pm_cannot_reassign_team_of_unowned_project(self):
        pm = _make_user("project_manager")
        project = Project(id=uuid.uuid4(), title="Other PM's project", slug="x", project_manager_id=uuid.uuid4())
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=project))

        with pytest.raises(ApiError) as exc_info:
            await assign_team(project.id, AssignTeamRequest(employee_ids=[]), mock_db, pm)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_update_any_project(self):
        admin = _make_user("admin")
        project = Project(
            id=uuid.uuid4(), title="Someone's project", slug="x", project_manager_id=uuid.uuid4(),
            status="planning", progress_percent=0, is_featured=False, is_published=False,
            technology_stack=[], team=[], **_stamps(),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock(scalar_one=MagicMock(return_value=project))

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with patch("app.routers.projects.crud.update", new_callable=AsyncMock, return_value=project):
                result = await update_project(project.id, ProjectUpdate(title="v2"), mock_db, admin)
        assert result["message"] == "Project updated successfully"
