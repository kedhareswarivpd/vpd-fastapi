import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import TimestampedRead


class ProjectMilestoneCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: date | None = None
    status: str = "pending"
    progress_percent: int = 0
    client_visible: bool = True
    order: int = 0


class ProjectMilestoneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: date | None = None
    completed_date: date | None = None
    status: str | None = None
    progress_percent: int | None = None
    client_visible: bool | None = None
    order: int | None = None


class ProjectMilestoneOut(TimestampedRead):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    due_date: date | None = None
    completed_date: date | None = None
    status: str
    progress_percent: int
    client_visible: bool
    order: int


class ProjectDeliverableCreate(BaseModel):
    title: str
    description: str | None = None
    file_url: str | None = None
    milestone_id: uuid.UUID | None = None


class ProjectDeliverableUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    file_url: str | None = None
    milestone_id: uuid.UUID | None = None
    status: str | None = None


class ProjectDeliverableReviewRequest(BaseModel):
    approved: bool
    client_comment: str | None = None


class ProjectDeliverableOut(TimestampedRead):
    project_id: uuid.UUID
    milestone_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    file_url: str | None = None
    status: str
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    client_comment: str | None = None
