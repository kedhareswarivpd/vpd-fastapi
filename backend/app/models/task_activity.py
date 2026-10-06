import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaskActivity(Base):
    """One audit-log entry per change made to a task (created, edited,
    status changed, deleted) — who did it and when, so a PM/admin can see
    the full history of a ticket rather than just its current state."""

    __tablename__ = "task_activities"

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    task = relationship("Task", foreign_keys=[task_id])
    actor = relationship("User", foreign_keys=[actor_id])
