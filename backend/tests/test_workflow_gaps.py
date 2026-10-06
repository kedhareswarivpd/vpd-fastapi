"""Regression tests for the contact->lead auto-creation, proposal-accept
auto-project-creation, and proposal PM-review stage added to close the gap
between the workflow doc's end-to-end diagram (Contact -> Lead -> Proposal
-> Project) and the previously separate, manually-connected modules."""
import copy
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.core.errors import ApiError
from app.models.enums import ProposalStatus
from app.models.lead import Lead
from app.models.proposal import Proposal
from app.models.user import User
from app.schemas.contact import ContactSubmit
from app.schemas.crm import ProposalReviewRequest


def _stamps() -> dict:
    now = datetime.now(UTC)
    return dict(created_at=now, updated_at=now)


def _make_user(role: str) -> User:
    return User(id=uuid.uuid4(), name="Someone", email="someone@example.com", password_hash="x", role=role)


def _fake_request() -> Request:
    return Request(scope={"type": "http", "query_string": b"", "headers": [], "client": ("test", 0)})


class TestContactAutoCreatesLead:
    @pytest.mark.asyncio
    async def test_submit_creates_lead_with_copied_fields(self):
        from app.routers.contact import submit

        service_id, industry_id = uuid.uuid4(), uuid.uuid4()
        payload = ContactSubmit(
            name="Jane Prospect", email="jane@example.com", phone="+15551234567",
            company="Prospect Co", message="Need a CRM", service_id=service_id,
            industry_id=industry_id, expected_budget=25000, requirements="Must integrate with our ERP",
        )
        submission = MagicMock(
            id=uuid.uuid4(), email=payload.email, message=payload.message,
            subject=None, company=payload.company, phone=payload.phone,
            service_id=service_id, industry_id=industry_id,
            expected_budget=payload.expected_budget, requirements=payload.requirements,
        )
        submission.name = payload.name  # MagicMock's `name=` kwarg sets the mock's repr, not an attribute
        mock_db = AsyncMock()

        with patch("app.routers.contact.crud.create", new_callable=AsyncMock, return_value=submission):
            with patch("app.routers.contact.send_contact_notification", new_callable=AsyncMock):
                await submit(_fake_request(), payload, mock_db)

        mock_db.add.assert_called_once()
        added_lead = mock_db.add.call_args[0][0]
        assert added_lead.contact_name == "Jane Prospect"
        assert added_lead.service_id == service_id
        assert added_lead.industry_id == industry_id
        assert added_lead.estimated_value == 25000
        assert added_lead.notes == "Must integrate with our ERP"
        assert submission.lead_id == added_lead.id


class TestProvisionProjectForAcceptedProposal:
    @pytest.mark.asyncio
    async def test_creates_project_when_lead_converted(self):
        from app.services.project_provisioning import provision_project_for_accepted_proposal

        client_id, service_id, industry_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        lead = Lead(
            id=uuid.uuid4(), contact_name="Acme", email="acme@example.com", company="Acme Corp",
            converted_client_id=client_id, industry_id=industry_id,
        )
        proposal = Proposal(
            id=uuid.uuid4(), lead_id=lead.id, version=1, scope_summary="Build a thing",
            price=10000, currency="USD", status=ProposalStatus.accepted, service_id=service_id, **_stamps(),
        )

        mock_db = AsyncMock()
        no_existing_project = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        lead_row = MagicMock(scalar_one_or_none=MagicMock(return_value=lead))
        mock_db.execute.side_effect = [no_existing_project, lead_row]

        def fake_refresh(obj):
            obj.id = uuid.uuid4()
        mock_db.refresh.side_effect = fake_refresh

        with patch("app.services.project_provisioning.notify_roles", new_callable=AsyncMock):
            project = await provision_project_for_accepted_proposal(mock_db, proposal)

        assert project is not None
        assert project.client_id == client_id
        assert project.proposal_id == proposal.id
        assert project.service_id == service_id
        assert project.industry_id == industry_id
        assert project.budget == 10000
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_returns_existing_project(self):
        from app.models.project import Project
        from app.services.project_provisioning import provision_project_for_accepted_proposal

        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.accepted, **_stamps(),
        )
        existing_project = Project(id=uuid.uuid4(), title="Existing", slug="existing", proposal_id=proposal.id)

        mock_db = AsyncMock()
        found_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_project))
        mock_db.execute.side_effect = [found_existing]

        project = await provision_project_for_accepted_proposal(mock_db, proposal)
        assert project is existing_project
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_when_lead_not_converted(self):
        from app.services.project_provisioning import provision_project_for_accepted_proposal

        lead = Lead(id=uuid.uuid4(), contact_name="X", email="x@example.com", converted_client_id=None)
        proposal = Proposal(
            id=uuid.uuid4(), lead_id=lead.id, version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.accepted, **_stamps(),
        )

        mock_db = AsyncMock()
        no_existing_project = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        lead_row = MagicMock(scalar_one_or_none=MagicMock(return_value=lead))
        mock_db.execute.side_effect = [no_existing_project, lead_row]

        project = await provision_project_for_accepted_proposal(mock_db, proposal)
        assert project is None
        mock_db.add.assert_not_called()


class TestProposalPmReviewStage:
    @pytest.mark.asyncio
    async def test_submit_for_review_transitions_draft(self):
        from app.routers.proposals import submit_proposal_for_review

        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.draft, **_stamps(),
        )
        updated = copy.copy(proposal)
        updated.status = ProposalStatus.submitted_for_review
        mock_db = AsyncMock()

        with patch("app.routers.proposals.crud.get", new_callable=AsyncMock, return_value=proposal):
            with patch("app.routers.proposals.crud.update", new_callable=AsyncMock, return_value=updated):
                with patch("app.routers.proposals.notify_roles", new_callable=AsyncMock):
                    result = await submit_proposal_for_review(proposal.id, mock_db)
        assert result["data"].status == ProposalStatus.submitted_for_review

    @pytest.mark.asyncio
    async def test_review_approve_sets_pm_approved(self):
        from app.routers.proposals import review_proposal

        user = _make_user("project_manager")
        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.submitted_for_review, **_stamps(),
        )
        updated = copy.copy(proposal)
        updated.status = ProposalStatus.pm_approved
        mock_db = AsyncMock()

        with patch("app.routers.proposals.crud.get", new_callable=AsyncMock, return_value=proposal):
            with patch("app.routers.proposals.crud.update", new_callable=AsyncMock, return_value=updated):
                result = await review_proposal(proposal.id, ProposalReviewRequest(approved=True), mock_db, user)
        assert result["data"].status == ProposalStatus.pm_approved

    @pytest.mark.asyncio
    async def test_review_reject_sets_pm_rejected(self):
        from app.routers.proposals import review_proposal

        user = _make_user("admin")
        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.submitted_for_review, **_stamps(),
        )
        updated = copy.copy(proposal)
        updated.status = ProposalStatus.pm_rejected
        mock_db = AsyncMock()

        with patch("app.routers.proposals.crud.get", new_callable=AsyncMock, return_value=proposal):
            with patch("app.routers.proposals.crud.update", new_callable=AsyncMock, return_value=updated):
                result = await review_proposal(proposal.id, ProposalReviewRequest(approved=False), mock_db, user)
        assert result["data"].status == ProposalStatus.pm_rejected

    @pytest.mark.asyncio
    async def test_send_blocked_while_submitted_for_review(self):
        from app.routers.proposals import send_proposal

        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.submitted_for_review, **_stamps(),
        )
        mock_db = AsyncMock()

        with patch("app.routers.proposals.crud.get", new_callable=AsyncMock, return_value=proposal):
            with pytest.raises(ApiError) as exc_info:
                await send_proposal(proposal.id, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_send_allowed_when_pm_approved(self):
        from app.routers.proposals import send_proposal

        proposal = Proposal(
            id=uuid.uuid4(), lead_id=uuid.uuid4(), version=1, scope_summary="x",
            price=1000, currency="USD", status=ProposalStatus.pm_approved, **_stamps(),
        )
        updated = copy.copy(proposal)
        updated.status = ProposalStatus.sent
        mock_db = AsyncMock()

        with patch("app.routers.proposals.crud.get", new_callable=AsyncMock, return_value=proposal):
            with patch("app.routers.proposals.crud.update", new_callable=AsyncMock, return_value=updated):
                with patch("app.routers.proposals.lead_crud.update", new_callable=AsyncMock):
                    result = await send_proposal(proposal.id, mock_db)
        assert result["data"].status == ProposalStatus.sent


class TestPerformanceGoalOwnershipBoundary:
    """Performance goals/feedback lifecycle: staff set a goal's title/
    description/target_date; the employee it belongs to may only progress
    status/progress_percent on their own goal — not edit its definition or
    touch anyone else's."""

    @pytest.mark.asyncio
    async def test_employee_can_update_own_progress(self):
        from app.models.employee import Employee
        from app.models.performance_goal import PerformanceGoal
        from app.routers.employees import update_performance_goal
        from app.schemas.performance import PerformanceGoalUpdate

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-1")
        goal = PerformanceGoal(id=uuid.uuid4(), employee_id=employee.id, title="Learn X", status="not_started", progress_percent=0, **_stamps())

        mock_db = AsyncMock()
        goal_row = MagicMock(scalar_one_or_none=MagicMock(return_value=goal))
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.side_effect = [goal_row, emp_row]

        result = await update_performance_goal(goal.id, PerformanceGoalUpdate(progress_percent=50), mock_db, user)
        assert result["data"].progress_percent == 50

    @pytest.mark.asyncio
    async def test_employee_cannot_edit_own_goal_title(self):
        from app.models.employee import Employee
        from app.models.performance_goal import PerformanceGoal
        from app.routers.employees import update_performance_goal
        from app.schemas.performance import PerformanceGoalUpdate

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-2")
        goal = PerformanceGoal(id=uuid.uuid4(), employee_id=employee.id, title="Learn X", status="not_started", progress_percent=0, **_stamps())

        mock_db = AsyncMock()
        goal_row = MagicMock(scalar_one_or_none=MagicMock(return_value=goal))
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.side_effect = [goal_row, emp_row]

        with pytest.raises(ApiError) as exc_info:
            await update_performance_goal(goal.id, PerformanceGoalUpdate(title="hacked"), mock_db, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_employee_cannot_update_someone_elses_goal(self):
        from app.models.employee import Employee
        from app.models.performance_goal import PerformanceGoal
        from app.routers.employees import update_performance_goal
        from app.schemas.performance import PerformanceGoalUpdate

        user = _make_user("developer")
        employee = Employee(id=uuid.uuid4(), user_id=user.id, employee_code="EMP-3")
        other_employee_goal = PerformanceGoal(id=uuid.uuid4(), employee_id=uuid.uuid4(), title="Not yours", status="not_started", progress_percent=0, **_stamps())

        mock_db = AsyncMock()
        goal_row = MagicMock(scalar_one_or_none=MagicMock(return_value=other_employee_goal))
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee))
        mock_db.execute.side_effect = [goal_row, emp_row]

        with pytest.raises(ApiError) as exc_info:
            await update_performance_goal(other_employee_goal.id, PerformanceGoalUpdate(progress_percent=100), mock_db, user)
        assert exc_info.value.status_code == 403


class TestPayslipSecureDownload:
    @pytest.mark.asyncio
    async def test_download_blocked_for_non_owner(self):
        from app.models.payslip import Payslip
        from app.routers.employees import download_my_payslip

        other = _make_user("employee")
        employee_other = MagicMock()  # the *caller's* employee row, unrelated to the payslip
        payslip = Payslip(id=uuid.uuid4(), employee_id=uuid.uuid4(), month=8, year=2026, basic=5000, net_pay=5000, file_url="payslips/x.pdf")

        mock_db = AsyncMock()
        emp_row = MagicMock(scalar_one_or_none=MagicMock(return_value=employee_other))
        no_matching_payslip = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_db.execute.side_effect = [emp_row, no_matching_payslip]

        with pytest.raises(ApiError) as exc_info:
            await download_my_payslip(payslip.id, mock_db, other)
        assert exc_info.value.status_code == 404
