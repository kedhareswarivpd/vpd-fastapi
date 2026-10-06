import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    review_period: Mapped[str] = mapped_column(String(50), nullable=False)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    strengths: Mapped[str | None] = mapped_column(Text)
    areas_for_improvement: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # Review-acknowledgment lifecycle: the employee confirming they've read
    # a finalized review, previously had no backing field at all.
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee = relationship("Employee")
    reviewer = relationship("User")
