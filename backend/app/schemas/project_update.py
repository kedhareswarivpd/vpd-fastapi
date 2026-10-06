import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ProjectUpdateCreate(BaseModel):
    update_text: str = Field(min_length=1, max_length=4000)
    hours_logged: float | None = Field(None, ge=0, le=24)


class ProjectUpdateVisibility(BaseModel):
    client_visible: bool


class ProjectUpdateOut(TimestampedRead):
    """Internal (employee/PM) view — includes employee_id for PM/HR context."""
    project_id: uuid.UUID
    employee_id: uuid.UUID
    update_text: str
    hours_logged: float | None = None
    client_visible: bool


class ClientProjectUpdateOut(BaseModel):
    """Client-facing view — workflow doc §16: the client must not receive
    employee internal IDs, employee codes, or other internal details. Only
    the update text, when it was posted, and the author's display name."""
    id: uuid.UUID
    update_text: str
    created_at: datetime
    author_name: str | None = None
