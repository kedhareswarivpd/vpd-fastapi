"""Keeps Project.progress_percent (and, at the boundaries, Project.status) in
sync with its tasks' completion — previously a purely manual number nothing
ever recomputed, so task work was invisible everywhere that reads it
(client/PM/admin dashboards all just display this same field).

Recomputed as done_tasks / total_tasks whenever a task is created or its
status changes. Auto status transitions are the two edges only:
planning -> in_progress the moment any task exists at all, and
in_progress -> completed the moment every task is done — both nudges, not a
hard lock (a PM can still set on_hold/cancelled/back to planning by hand;
the next task-status change will simply recompute progress again without
overriding a deliberate manual status choice back to `completed` when it's
already there).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.enums import NotificationType, ProjectStatus, TaskStatus
from app.models.project import Project
from app.models.task import Task
from app.services.notification_service import notify_roles, notify_user


async def recompute_project_progress(db: AsyncSession, project_id) -> None:
    project = await db.get(Project, project_id)
    if project is None:
        return

    total = (await db.execute(select(func.count()).select_from(Task).where(Task.project_id == project_id))).scalar_one()
    if total == 0:
        return

    done = (
        await db.execute(select(func.count()).select_from(Task).where(Task.project_id == project_id, Task.status == TaskStatus.done))
    ).scalar_one()
    new_progress = round(100 * done / total)
    progress_changed = new_progress != project.progress_percent
    project.progress_percent = new_progress

    just_completed = False
    if project.status == ProjectStatus.planning and new_progress > 0:
        project.status = ProjectStatus.in_progress
    elif new_progress == 100 and project.status == ProjectStatus.in_progress:
        project.status = ProjectStatus.completed
        just_completed = True

    if progress_changed or just_completed:
        await db.commit()

    if just_completed:
        try:
            await notify_roles(
                db, ["admin"], "Project reached 100% — ready for client review",
                f"'{project.title}' — every task is done. Submit it for client review when ready.",
                NotificationType.success, f"/admin-panel?tab=projects&project={project.id}",
            )
            if project.project_manager_id:
                await notify_user(
                    db, project.project_manager_id, "Project reached 100% — ready for client review",
                    f"'{project.title}' — every task is done. Submit it for client review when ready.",
                    NotificationType.success, f"/project-manager?tab=projects&project={project.id}",
                )
        except Exception as exc:  # noqa: BLE001 — the progress/status update itself is already committed; a notify failure must not undo it
            logger.warning("Failed to notify staff that project %s hit 100%%: %s", project.id, exc)
