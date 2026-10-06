import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.task import Task
from app.models.task_activity import TaskActivity
from app.models.user import User
from app.schemas.task import TaskActivityOut, TaskCreate, TaskOut, TaskStatusUpdate, TaskUpdate
from app.services.project_progress import recompute_project_progress
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/tasks", tags=["Tasks"], dependencies=[Depends(get_current_user)])

crud = CRUDBase(Task, searchable_fields=["title"], relationships=["project"])


async def _log_task_activity(db: AsyncSession, task_id: uuid.UUID, activity_type: str, description: str | None, actor_id: uuid.UUID | None) -> None:
    db.add(TaskActivity(task_id=task_id, activity_type=activity_type, description=description, actor_id=actor_id))
    await db.commit()


def _require_privileged_or_assignee(current_user: User, task: Task) -> None:
    is_privileged = current_user.role in ("admin", "super_admin", "project_manager")
    is_assignee = task.assigned_to is not None and task.assigned_to == current_user.id
    if not is_privileged and not is_assignee:
        raise ApiError.forbidden("You do not have access to this task")


@router.get("", response_model=dict)
async def list_tasks(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("project_id", "assigned_to", "status", "priority") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    data = []
    for t in items:
        out = TaskOut.model_validate(t).model_dump()
        out["project_title"] = t.project.title if t.project else None
        data.append(out)
    return success_response(data=data, message="Tasks fetched", meta=meta)


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "project_manager"))])
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = await crud.create(db, payload.model_dump())
    # A new (not-done) task lowers the done/total ratio — recompute so
    # progress_percent doesn't sit stale at whatever it was before this task existed.
    await recompute_project_progress(db, task.project_id)
    await _log_task_activity(db, task.id, "created", f"Ticket '{task.title}' created", current_user.id)
    return success_response(data=TaskOut.model_validate(task), message="Task created successfully", status_code=201)


@router.patch("/{task_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "project_manager"))])
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Full ticket edit (title/description/assignee/priority/due
    date/estimated hours) — restricted to admin/PM, distinct from the
    assignee-facing status-only endpoint below."""
    existing = await crud.get(db, task_id)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if getattr(existing, k) != v}
    if not changes:
        return success_response(data=TaskOut.model_validate(existing), message="No changes")

    task = await crud.update(db, task_id, changes)
    await recompute_project_progress(db, task.project_id)
    description = "; ".join(f"{field} changed" for field in changes)
    await _log_task_activity(db, task.id, "updated", description, current_user.id)
    return success_response(data=TaskOut.model_validate(task), message="Task updated")


@router.delete("/{task_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "project_manager"))])
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = await crud.get(db, task_id)
    project_id = task.project_id
    await _log_task_activity(db, task.id, "deleted", f"Ticket '{task.title}' deleted", current_user.id)
    await crud.delete(db, task_id)
    await recompute_project_progress(db, project_id)
    return success_response(message="Task deleted successfully")


@router.patch("/{task_id}/status", response_model=dict)
async def update_task_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await crud.get(db, task_id)
    _require_privileged_or_assignee(current_user, existing)
    previous_status = existing.status

    task = await crud.update(db, task_id, payload.model_dump())
    await recompute_project_progress(db, task.project_id)
    if task.status != previous_status:
        await _log_task_activity(db, task.id, "status_changed", f"Status changed from {previous_status.value} to {task.status.value}", current_user.id)
    return success_response(data=TaskOut.model_validate(task), message="Task status updated")


@router.get("/{task_id}/activities", response_model=dict)
async def list_task_activities(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Per-ticket audit trail — visible to admin/PM for any ticket, and to
    the assignee for their own ticket, so the people accountable for a
    project's tickets can see who changed what and when."""
    task = await crud.get(db, task_id)
    _require_privileged_or_assignee(current_user, task)
    items = (
        await db.execute(select(TaskActivity).where(TaskActivity.task_id == task_id).order_by(TaskActivity.created_at))
    ).scalars().all()
    return success_response(data=[TaskActivityOut.model_validate(a) for a in items])
