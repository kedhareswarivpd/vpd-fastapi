from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class CourseBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = None
    category: str | None = None
    duration_hours: int | None = None
    cover_image: str | None = None
    is_published: bool = False


class CourseCreate(CourseBase):
    pass


class CourseUpdate(CourseBase):
    title: str | None = None
    is_published: bool | None = None


class CourseOut(CourseBase, TimestampedRead):
    slug: str


class TrainingEnrollmentOut(TimestampedRead):
    employee_id: UUID
    course_id: UUID
    status: str
    enrolled_at: datetime
    completed_at: datetime | None = None
