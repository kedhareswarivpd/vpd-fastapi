"""Regression tests for the Daily Project Update feature added during the
UAT closure pass (docs/requirments/UAT_REPORT.md §2) — this entity and its
authorization rules did not exist before. Also covers the project<->proposal
linkage + duplicate-project-creation guard added in the same pass (§1)."""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import ApiError
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.enums import LeadStatus, ProposalStatus
from app.models.lead import Lead
from app.models.project import Project
from app.models.proposal import Proposal
from app.models.timesheet import Timesheet
from app.models.user import User
from app.routers.projects import create_project, post_project_update
from app.schemas.project import ProjectCreate
from app.schemas.project_update import ProjectUpdateCreate


def _stamps() -> dict:
    now = datetime.now(UTC)
    return dict(created_at=now, updated_at=now)


def _stamp_on_refresh(obj) -> None:
    """Mimics what a real db.refresh() populates after commit — AsyncMock's
    refresh() is a no-op and the handlers under test serialize the object
    immediately afterward. Same pattern as test_gap_fixes.py."""
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    now = datetime.now(UTC)
    obj.created_at = now
    obj.updated_at = now
    if getattr(obj, "client_visible", None) is None:
        obj.client_visible = False
    if isinstance(obj, Timesheet) and obj.status is None:
        obj.status = "draft"


def _project_defaults() -> dict:
    return dict(
        technology_stack=[], deliverables=[], gallery=[], downloads=[],
        progress_percent=0, is_featured=False, is_published=False, **_stamps(),
    )


def _make_user(role: str, **overrides) -> User:
    defaults = dict(id=uuid.uuid4(), name="Someone", email="someone@example.com", password_hash="x", role=role)
    defaults.update(overrides)
    return User(**defaults)


class TestProjectUpdateAuthorization:
    @pytest.mark.asyncio
    async def test_employee_on_team_can_post_update(self):
        user = _make_user("developer")
        project_id = uuid.uuid4()
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-1")
        project = Project(id=project_id, title="X", slug="x", status="planning", **_project_defaults())

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _stamp_on_refresh

        # First execute() resolves the Employee row, second confirms team membership.
        team_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee.id))
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.side_effect = [emp_row, team_row]

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            result = await post_project_update(
                project_id, ProjectUpdateCreate(update_text="Did the thing", hours_logged=3), mock_db, user,
            )
        assert result["message"] == "Update posted"

    @pytest.mark.asyncio
    async def test_employee_not_on_team_is_rejected(self):
        user = _make_user("developer")
        project_id = uuid.uuid4()
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-2")
        project = Project(id=project_id, title="X", slug="x", status="planning", project_manager_id=uuid.uuid4(), **_project_defaults())

        mock_db = AsyncMock()
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        not_a_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.side_effect = [emp_row, not_a_member]

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with pytest.raises(ApiError) as exc_info:
                await post_project_update(
                    project_id, ProjectUpdateCreate(update_text="sneaking in"), mock_db, user,
                )
        assert exc_info.value.status_code == 403


class TestProjectProposalLinkage:
    @pytest.mark.asyncio
    async def test_duplicate_project_for_same_proposal_returns_existing(self):
        proposal_id = uuid.uuid4()
        existing_project = Project(id=uuid.uuid4(), title="Existing", slug="existing", proposal_id=proposal_id, status="planning", client_id=None, **_project_defaults())

        mock_db = AsyncMock()
        found_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_project))
        # Second execute() re-fetches the existing project with team eager-loaded.
        reloaded = MagicMock(scalar_one=MagicMock(return_value=existing_project))
        mock_db.execute.side_effect = [found_existing, reloaded]

        mock_response = MagicMock(status_code=201)
        result = await create_project(
            ProjectCreate(title="Duplicate Attempt", proposal_id=proposal_id), mock_response, mock_db,
        )
        assert mock_response.status_code == 200
        assert result["message"] == "A project already exists for this proposal"


class TestClientProposalAcceptUpdatesLeadStatus:
    """UAT closure pass §3: a client accepting their own proposal via
    POST /clients/me/proposals/{id}/accept never advanced Lead.status to
    proposal_approved (unlike the staff-facing /proposals/{id}/accept, which
    does) — live UAT caught the lead stuck at proposal_sent after acceptance."""

    @pytest.mark.asyncio
    async def test_client_accept_advances_lead_to_proposal_approved(self):
        from app.models.client import Client
        from app.routers.clients import accept_my_proposal

        user = _make_user("client")
        client = Client(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
        lead_id = uuid.uuid4()
        proposal = Proposal(
            id=uuid.uuid4(), lead_id=lead_id, version=2, scope_summary="revised",
            price=22000, currency="USD", status=ProposalStatus.sent, **_stamps(),
        )
        lead = Lead(id=lead_id, contact_name="Acme Contact", email="acme@example.com", status=LeadStatus.proposal_sent)

        mock_db = AsyncMock()
        mock_db.refresh.side_effect = _stamp_on_refresh
        proposal_row = MagicMock(scalar_one_or_none=MagicMock(return_value=proposal))
        lead_row = MagicMock(scalar_one_or_none=MagicMock(return_value=lead))
        mock_db.execute.side_effect = [proposal_row, lead_row]

        with patch("app.routers.clients._get_client_for_user", new_callable=AsyncMock, return_value=client):
            with patch("app.routers.clients.notify_roles", new_callable=AsyncMock):
                with patch("app.routers.clients.provision_project_for_accepted_proposal", new_callable=AsyncMock):
                    await accept_my_proposal(proposal.id, mock_db, user)

        assert proposal.status == ProposalStatus.accepted
        assert lead.status == LeadStatus.proposal_approved


class TestDisqualifiedLeadCannotBeConverted:
    """UAT closure pass §4: POST /leads/{id}/convert never checked for a
    disqualified (rejected/closed) lead — live UAT converted one straight
    into a real client account + login credentials, violating "Unsuccessful
    Lead -> Reject/Close" (no client/credentials should ever be created)."""

    @pytest.mark.asyncio
    async def test_convert_disqualified_lead_is_rejected(self):
        from app.routers.leads import convert_lead

        lead = Lead(
            id=uuid.uuid4(), contact_name="Nope", email="nope@example.com",
            status=LeadStatus.disqualified, **_stamps(),
        )
        mock_db = AsyncMock()

        with patch("app.routers.leads.crud.get", new_callable=AsyncMock, return_value=lead):
            with pytest.raises(ApiError) as exc_info:
                await convert_lead(lead.id, mock_db)
        assert exc_info.value.status_code == 400
        mock_db.execute.assert_not_called()


class TestAttendanceHistoryAndHrAccess:
    """UAT closure pass §6: GET /employees/me/attendance (own history) and
    GET /employees/attendance (HR/admin cross-employee view) did not exist
    at all — only "today" check-in/out was ever readable. Workflow doc §15
    requires "Attendance information should be accessible to authorized
    HR users"."""

    @pytest.mark.asyncio
    async def test_my_attendance_scoped_to_own_employee(self):
        from fastapi import Request

        from app.routers.employees import my_attendance
        from app.utils.pagination import PageParams

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-1")
        record = Attendance(id=uuid.uuid4(), employee_id=employee.id, date=datetime.now(UTC).date(), status="present", **_stamps())

        mock_db = AsyncMock()
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        items_row = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[record]))))
        count_row = MagicMock(scalar_one=MagicMock(return_value=1))
        mock_db.execute.side_effect = [emp_row, items_row, count_row]

        request = Request(scope={"type": "http", "query_string": b"", "headers": []})
        result = await my_attendance(request, mock_db, PageParams(page=1, limit=20), user)
        assert result["data"][0].employee_id == employee.id

    @pytest.mark.asyncio
    async def test_hr_can_filter_attendance_by_employee_id(self):
        from fastapi import Request

        from app.routers.employees import list_attendance
        from app.utils.pagination import PageParams

        employee_id = uuid.uuid4()
        record = Attendance(id=uuid.uuid4(), employee_id=employee_id, date=datetime.now(UTC).date(), status="present", **_stamps())

        mock_db = AsyncMock()
        items_row = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[record]))))
        count_row = MagicMock(scalar_one=MagicMock(return_value=1))
        mock_db.execute.side_effect = [items_row, count_row]

        request = Request(scope={"type": "http", "query_string": f"employee_id={employee_id}".encode(), "headers": []})
        result = await list_attendance(request, mock_db, PageParams(page=1, limit=20))
        assert result["data"][0]["employee_id"] == employee_id


class TestTimesheetRequiresProjectMembership:
    """UAT closure pass §7: POST /employees/me/timesheets never checked that
    the employee was actually assigned to payload.project_id — live UAT
    logged billable hours against a project the employee had zero
    assignment to."""

    @pytest.mark.asyncio
    async def test_timesheet_for_unassigned_project_is_rejected(self):
        from app.routers.employees import submit_timesheet
        from app.schemas.employee import TimesheetCreate

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-3")
        project_id = uuid.uuid4()

        mock_db = AsyncMock()
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        not_a_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.side_effect = [emp_row, not_a_member]

        payload = TimesheetCreate(project_id=project_id, date=datetime.now(UTC).date(), hours=8)
        with pytest.raises(ApiError) as exc_info:
            await submit_timesheet(payload, mock_db, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_timesheet_for_assigned_project_succeeds(self):
        from app.routers.employees import submit_timesheet
        from app.schemas.employee import TimesheetCreate

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-4")
        project_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.refresh.side_effect = _stamp_on_refresh
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        is_member = MagicMock(scalar_one_or_none=MagicMock(return_value=employee.id))
        mock_db.execute.side_effect = [emp_row, is_member]

        payload = TimesheetCreate(project_id=project_id, date=datetime.now(UTC).date(), hours=8)
        result = await submit_timesheet(payload, mock_db, user)
        assert result["message"] == "Timesheet entry logged"
        assert result["data"].status == "submitted"


class TestClientCannotSeeInternalProjectsList:
    """UAT closure pass §14 (RBAC matrix): GET /projects only special-cased
    current_user is None as "public/restricted" — ANY authenticated caller,
    including a client, was treated as staff and got is_published left
    unfiltered (full internal ProjectOut for every client's projects, no
    scoping). Live UAT caught a real client account pulling every project
    in the system, budget/team roster included."""

    @pytest.mark.asyncio
    async def test_client_role_forced_to_published_only(self):
        from fastapi import Request

        from app.routers.projects import list_projects
        from app.utils.pagination import PageParams

        client_user = _make_user("client")
        mock_db = AsyncMock()

        captured_filters = {}

        async def fake_list(db, page, filters):
            captured_filters.update(filters)
            return [], 0

        with patch("app.routers.projects.crud.list", new_callable=AsyncMock, side_effect=fake_list):
            request = Request(scope={"type": "http", "query_string": b"is_published=false", "headers": []})
            await list_projects(request, mock_db, PageParams(page=1, limit=20), client_user)

        assert captured_filters.get("is_published") is True


class TestFinalDeliveryClientApproval:
    """Project Tracker / Final Delivery workflow: Project Execution -> Final
    Review -> Completed -> Deliverables Shared -> Client Review -> Client
    Approval had no backing fields or endpoints at all."""

    @pytest.mark.asyncio
    async def test_submit_for_client_review_requires_completed_status(self):
        from app.routers.projects import submit_project_for_client_review

        user = _make_user("admin")
        project = Project(id=uuid.uuid4(), title="X", slug="x", status="in_progress", **_project_defaults())
        mock_db = AsyncMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with pytest.raises(ApiError) as exc_info:
                await submit_project_for_client_review(project.id, mock_db, user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_for_client_review_succeeds_when_completed(self):
        from app.routers.projects import submit_project_for_client_review

        user = _make_user("admin")
        project = Project(id=uuid.uuid4(), title="X", slug="x", status="completed", client_id=None, **_project_defaults())
        mock_db = AsyncMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            result = await submit_project_for_client_review(project.id, mock_db, user)
        assert project.client_review_status == "pending"
        assert project.completion_submitted_at is not None
        assert result["message"] == "Project submitted for client review"

    @pytest.mark.asyncio
    async def test_approve_delivery_requires_pending_review(self):
        from app.models.client import Client
        from app.routers.clients import approve_project_delivery

        user = _make_user("client")
        client = Client(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
        project = Project(
            id=uuid.uuid4(), title="X", slug="x", status="completed",
            client_id=client.id, client_review_status=None, **_project_defaults(),
        )
        mock_db = AsyncMock()
        project_row = MagicMock(scalar_one_or_none=MagicMock(return_value=project))
        mock_db.execute.side_effect = [project_row]

        with patch("app.routers.clients._get_client_for_user", new_callable=AsyncMock, return_value=client):
            with pytest.raises(ApiError) as exc_info:
                await approve_project_delivery(project.id, mock_db, user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_delivery_succeeds_when_pending(self):
        from app.models.client import Client
        from app.routers.clients import approve_project_delivery

        user = _make_user("client")
        client = Client(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
        project = Project(
            id=uuid.uuid4(), title="X", slug="x", status="completed",
            client_id=client.id, client_review_status="pending", final_delivery_version=0, **_project_defaults(),
        )
        mock_db = AsyncMock()
        project_row = MagicMock(scalar_one_or_none=MagicMock(return_value=project))
        mock_db.execute.side_effect = [project_row]

        with patch("app.routers.clients._get_client_for_user", new_callable=AsyncMock, return_value=client):
            with patch("app.routers.clients.notify_roles", new_callable=AsyncMock):
                result = await approve_project_delivery(project.id, mock_db, user)
        assert project.client_review_status == "approved"
        assert project.final_delivery_version == 1
        assert project.client_approved_at is not None
        assert result["message"] == "Delivery approved"


class TestMilestonesAndDeliverables:
    @pytest.mark.asyncio
    async def test_pm_can_create_milestone_for_own_project(self):
        from app.routers.projects import create_milestone
        from app.schemas.project_milestone import ProjectMilestoneCreate

        pm_id = uuid.uuid4()
        user = _make_user("project_manager", id=pm_id)
        project = Project(id=uuid.uuid4(), title="X", slug="x", status="planning", project_manager_id=pm_id, **_project_defaults())
        mock_db = AsyncMock()
        mock_db.refresh.side_effect = _stamp_on_refresh

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            result = await create_milestone(
                project.id, ProjectMilestoneCreate(title="Phase 1", due_date=None), mock_db, user,
            )
        assert result["message"] == "Milestone created"

    @pytest.mark.asyncio
    async def test_pm_cannot_create_milestone_for_other_project(self):
        from app.routers.projects import create_milestone
        from app.schemas.project_milestone import ProjectMilestoneCreate

        user = _make_user("project_manager", id=uuid.uuid4())
        project = Project(id=uuid.uuid4(), title="X", slug="x", status="planning", project_manager_id=uuid.uuid4(), **_project_defaults())
        mock_db = AsyncMock()

        with patch("app.routers.projects.crud.get", new_callable=AsyncMock, return_value=project):
            with pytest.raises(ApiError) as exc_info:
                await create_milestone(project.id, ProjectMilestoneCreate(title="Phase 1"), mock_db, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_deliverable_only_visible_to_client_once_submitted(self):
        from app.models.client import Client
        from app.models.project_deliverable import ProjectDeliverable
        from app.routers.clients import my_project_deliverables

        user = _make_user("client")
        client = Client(id=uuid.uuid4(), user_id=user.id, company_name="Acme")
        project = Project(id=uuid.uuid4(), title="X", slug="x", client_id=client.id, status="in_progress", **_project_defaults())
        deliverable = ProjectDeliverable(id=uuid.uuid4(), project_id=project.id, title="Doc", status="submitted", **_stamps())

        mock_db = AsyncMock()
        project_row = MagicMock(scalar_one_or_none=MagicMock(return_value=project))
        items_row = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[deliverable]))))
        mock_db.execute.side_effect = [project_row, items_row]

        with patch("app.routers.clients._get_client_for_user", new_callable=AsyncMock, return_value=client):
            result = await my_project_deliverables(project.id, mock_db, user)
        assert result["data"][0].status == "submitted"
