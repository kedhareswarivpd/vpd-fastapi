import uuid
from datetime import date

from pydantic import BaseModel

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import TimestampedRead


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    priority: TaskPriority = TaskPriority.medium
    status: TaskStatus = TaskStatus.todo
    due_date: date | None = None
    estimated_hours: float | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    estimated_hours: float | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskOut(TimestampedRead):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    priority: TaskPriority
    status: TaskStatus
    due_date: date | None = None
    estimated_hours: float | None = None
    project_title: str | None = None


class TaskActivityOut(TimestampedRead):
    task_id: uuid.UUID
    activity_type: str
    description: str | None = None
    actor_id: uuid.UUID | None = None
