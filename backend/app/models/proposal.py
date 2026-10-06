import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProposalStatus


class Proposal(Base):
    __tablename__ = "proposals"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[ProposalStatus] = mapped_column(Enum(ProposalStatus, name="proposal_status"), default=ProposalStatus.draft)
    file_url: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    # Workflow doc §7 lists "Client comments" and "Rejection reason" as
    # required proposal-history fields — the client's own accept/reject
    # endpoints (app/routers/clients.py) populate these; staff-side
    # accept/reject (app/routers/proposals.py) leave them null.
    client_comment: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), index=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lead = relationship("Lead", back_populates="proposals")
    contract = relationship("Contract", back_populates="proposal", uselist=False)
