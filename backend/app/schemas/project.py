import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProjectStatus
from app.schemas.common import TimestampedRead


class ProjectCreate(BaseModel):
    title: str
    slug: str | None = None
    client_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    overview: str | None = None
    challenge: str | None = None
    solution: str | None = None
    technology_stack: list[str] = []
    architecture_notes: str | None = None
    industry: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = Field(None, ge=0)
    status: ProjectStatus = ProjectStatus.planning
    project_manager_id: uuid.UUID | None = None
    cover_image: str | None = None
    video_url: str | None = None
    deliverables: list[str] = []
    gallery: list[str] = []
    downloads: list[dict] = []
    is_featured: bool = False
    is_published: bool = False


class ProjectUpdate(BaseModel):
    title: str | None = None
    client_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    overview: str | None = None
    challenge: str | None = None
    solution: str | None = None
    technology_stack: list[str] | None = None
    architecture_notes: str | None = None
    status: ProjectStatus | None = None
    progress_percent: int | None = Field(None, ge=0, le=100)
    budget: float | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    project_manager_id: uuid.UUID | None = None
    cover_image: str | None = None
    video_url: str | None = None
    deliverables: list[str] | None = None
    gallery: list[str] | None = None
    downloads: list[dict] | None = None
    is_featured: bool | None = None
    is_published: bool | None = None


class ProjectMemberOut(BaseModel):
    id: uuid.UUID
    employee_code: str | None = None
    designation: str | None = None
    user_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectOut(TimestampedRead):
    title: str
    slug: str
    client_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    completion_submitted_at: datetime | None = None
    client_review_status: str | None = None
    client_approved_at: datetime | None = None
    client_feedback: str | None = None
    final_delivery_version: int | None = 0
    overview: str | None = None
    challenge: str | None = None
    solution: str | None = None
    technology_stack: list[str] = []
    architecture_notes: str | None = None
    industry: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    status: ProjectStatus
    progress_percent: int
    project_manager_id: uuid.UUID | None = None
    cover_image: str | None = None
    video_url: str | None = None
    deliverables: list[str] = []
    gallery: list[str] = []
    downloads: list[dict] = []
    is_featured: bool
    is_published: bool
    team: list[ProjectMemberOut] = []

    @field_validator("deliverables", "gallery", "downloads", mode="before")
    @classmethod
    def _coerce_none_to_empty_list(cls, value):
        """A partially-built (never flushed) ORM object, or a real DB row with a
        NULL in one of these columns, yields an explicit None here rather than a
        missing field — the `= []` default only fills in a *missing* field, so
        None would otherwise fail validation. Coerce it to an empty list."""
        return [] if value is None else value


class ClientProjectOut(TimestampedRead):
    """Workflow doc §6/§16: the client's view of their own project must be
    limited to "Overall progress, Milestones, Deliverables, Approved updates,
    Project status" — explicitly NOT the internal team roster ("client
    should have a controlled communication mechanism through the designated
    PM... rather than unrestricted internal access"). The full `ProjectOut`
    above (used by staff/employee endpoints) includes `team: list[
    ProjectMemberOut]`, which leaks employee_code/designation/user_id to the
    client — this schema is what /clients/me/projects actually returns
    instead, replacing the full team roster with just the PM's name as the
    single designated point of contact."""
    title: str
    slug: str
    overview: str | None = None
    challenge: str | None = None
    solution: str | None = None
    technology_stack: list[str] = []
    industry: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    status: ProjectStatus
    progress_percent: int
    project_manager_name: str | None = None
    cover_image: str | None = None
    video_url: str | None = None
    deliverables: list[str] = []
    gallery: list[str] = []
    completion_submitted_at: datetime | None = None
    client_review_status: str | None = None
    client_approved_at: datetime | None = None
    client_feedback: str | None = None
    final_delivery_version: int | None = 0

    @field_validator("deliverables", "gallery", mode="before")
    @classmethod
    def _coerce_none_to_empty_list(cls, value):
        return [] if value is None else value


class AssignTeamRequest(BaseModel):
    employee_ids: list[uuid.UUID] = []

