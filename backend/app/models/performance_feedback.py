import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PerformanceFeedback(Base):
    """Continuous feedback — lighter-weight than a formal PerformanceReview
    cycle, for the ongoing "manager/peer leaves a note" pattern the
    workflow doc's performance lifecycle calls for alongside periodic
    reviews.
    """
    __tablename__ = "performance_feedback"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    given_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(20), default="general")

    employee = relationship("Employee")
    giver = relationship("User")
