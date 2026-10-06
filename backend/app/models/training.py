import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(280), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    duration_hours: Mapped[int | None] = mapped_column(Integer)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)

    enrollments = relationship("TrainingEnrollment", back_populates="course")


class TrainingEnrollment(Base):
    __tablename__ = "training_enrollments"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="enrolled")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    course = relationship("Course", back_populates="enrollments")

    # Real duplicate-enrollment race found during a documentation review:
    # the router only did a query-then-insert check with no matching
    # database constraint, so two concurrent enroll requests for the same
    # employee/course could both pass the check before either committed.
    __table_args__ = (UniqueConstraint("employee_id", "course_id", name="uq_training_enrollment_employee_course"),)
