from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class PerformanceReviewBase(BaseModel):
    employee_id: UUID
    reviewer_id: UUID
    review_period: str = Field(min_length=1, max_length=50)
    review_date: date
    rating: int | None = Field(None, ge=1, le=10)
    strengths: str | None = None
    areas_for_improvement: str | None = None
    goals: str | None = None
    comments: str | None = None
    status: str = "draft"


class PerformanceReviewCreate(PerformanceReviewBase):
    pass


class PerformanceReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=10)
    strengths: str | None = None
    areas_for_improvement: str | None = None
    goals: str | None = None
    comments: str | None = None
    status: str | None = None


class PerformanceReviewOut(PerformanceReviewBase, TimestampedRead):
    acknowledged_at: datetime | None = None


class PerformanceGoalCreate(BaseModel):
    employee_id: UUID
    review_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_date: date | None = None
    status: str = "not_started"
    progress_percent: int = Field(0, ge=0, le=100)


class PerformanceGoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    target_date: date | None = None
    status: str | None = None
    progress_percent: int | None = Field(None, ge=0, le=100)


class PerformanceGoalOut(TimestampedRead):
    employee_id: UUID
    review_id: UUID | None = None
    title: str
    description: str | None = None
    target_date: date | None = None
    status: str
    progress_percent: int
    created_by: UUID | None = None


class PerformanceFeedbackCreate(BaseModel):
    feedback_text: str = Field(min_length=1)
    feedback_type: str = "general"


class PerformanceFeedbackOut(TimestampedRead):
    employee_id: UUID
    given_by: UUID
    feedback_text: str
    feedback_type: str
