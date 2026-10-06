import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LeadActivity(Base):
    """One timeline entry per pipeline step taken on a lead (call logged,
    requirement gathering, proposal created/sent/approved, disqualified,
    converted) — backs the lead flow page's step-wise activity log."""

    __tablename__ = "lead_activities"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lead = relationship("Lead", foreign_keys=[lead_id])
    actor = relationship("User", foreign_keys=[actor_id])
