"""Regression tests for the IDOR/authorization gaps closed during the
CoreFusion Phase-1 remediation (see status.md, CF-AUD-005).

These exercise the router functions directly with a stubbed CRUDBase/db,
mirroring the style of tests/test_auth.py, since the shared test harness
mocks the SQLAlchemy engine (no real database is available here).
"""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import ApiError
from app.schemas.task import TaskStatusUpdate

_NOW = datetime.now(UTC)


def _user(role: str, user_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid.uuid4(), role=role)


class TestTaskStatusIDOR:
    """CF-AUD-005: any authenticated user could previously update any task."""

    async def test_non_assignee_employee_is_forbidden(self):
        from app.routers import task as task_router

        assignee_id = uuid.uuid4()
        other_user = _user("employee")
        existing_task = SimpleNamespace(id=uuid.uuid4(), assigned_to=assignee_id)

        with patch.object(task_router.crud, "get", new=AsyncMock(return_value=existing_task)):
            with pytest.raises(ApiError) as exc_info:
                await task_router.update_task_status(
                    existing_task.id,
                    TaskStatusUpdate(status="in_progress"),
                    db=AsyncMock(),
                    current_user=other_user,
                )
        assert exc_info.value.status_code == 403

    async def test_assignee_can_update_own_task(self):
        from app.routers import task as task_router

        assignee = _user("employee")
        existing_task = SimpleNamespace(id=uuid.uuid4(), assigned_to=assignee.id)
        updated_task = SimpleNamespace(id=existing_task.id, title="t", project_id=uuid.uuid4(), description=None, assigned_to=assignee.id, priority="medium", status="in_progress", due_date=None, estimated_hours=None, created_at=_NOW, updated_at=_NOW)

        with patch.object(task_router.crud, "get", new=AsyncMock(return_value=existing_task)), \
             patch.object(task_router.crud, "update", new=AsyncMock(return_value=updated_task)):
            result = await task_router.update_task_status(
                existing_task.id,
                TaskStatusUpdate(status="in_progress"),
                db=AsyncMock(),
                current_user=assignee,
            )
        assert result["success"] is True

    async def test_admin_can_update_any_task(self):
        from app.routers import task as task_router

        admin = _user("admin")
        existing_task = SimpleNamespace(id=uuid.uuid4(), assigned_to=uuid.uuid4())
        updated_task = SimpleNamespace(id=existing_task.id, title="t", project_id=uuid.uuid4(), description=None, assigned_to=existing_task.assigned_to, priority="medium", status="done", due_date=None, estimated_hours=None, created_at=_NOW, updated_at=_NOW)

        with patch.object(task_router.crud, "get", new=AsyncMock(return_value=existing_task)), \
             patch.object(task_router.crud, "update", new=AsyncMock(return_value=updated_task)):
            result = await task_router.update_task_status(
                existing_task.id,
                TaskStatusUpdate(status="done"),
                db=AsyncMock(),
                current_user=admin,
            )
        assert result["success"] is True


class TestLeadOwnershipIDOR:
    """CF-AUD-005: a sales rep could previously read any lead by ID."""

    async def test_sales_rep_cannot_read_others_lead(self):
        from app.routers import leads as leads_router

        sales_user = _user("sales")
        other_owner_id = uuid.uuid4()
        lead = SimpleNamespace(id=uuid.uuid4(), owner_id=other_owner_id)

        with patch.object(leads_router.crud, "get", new=AsyncMock(return_value=lead)):
            with pytest.raises(ApiError) as exc_info:
                await leads_router.get_lead(lead.id, db=AsyncMock(), current_user=sales_user)
        assert exc_info.value.status_code == 403

    async def test_sales_rep_can_read_own_lead(self):
        from app.routers import leads as leads_router

        sales_user = _user("sales")
        lead = SimpleNamespace(
            id=uuid.uuid4(), owner_id=sales_user.id, company="Acme", contact_name="J",
            email="j@acme.com", phone=None, source="website", status="new", notes=None,
            created_at=_NOW, updated_at=_NOW,
        )

        with patch.object(leads_router.crud, "get", new=AsyncMock(return_value=lead)):
            result = await leads_router.get_lead(lead.id, db=AsyncMock(), current_user=sales_user)
        assert result["success"] is True

    async def test_admin_can_read_any_lead(self):
        from app.routers import leads as leads_router

        admin = _user("admin")
        lead = SimpleNamespace(
            id=uuid.uuid4(), owner_id=uuid.uuid4(), company="Acme", contact_name="J",
            email="j@acme.com", phone=None, source="website", status="new", notes=None,
            created_at=_NOW, updated_at=_NOW,
        )

        with patch.object(leads_router.crud, "get", new=AsyncMock(return_value=lead)):
            result = await leads_router.get_lead(lead.id, db=AsyncMock(), current_user=admin)
        assert result["success"] is True
