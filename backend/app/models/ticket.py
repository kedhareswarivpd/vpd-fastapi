import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TicketPriority, TicketStatus


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True)
    partner_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("partner_accounts.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority, name="ticket_priority"), default=TicketPriority.medium)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus, name="ticket_status"), default=TicketStatus.open)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    # Workflow doc §12: "The system should track SLA/response and resolution
    # deadlines based on priority" + "Resolution"/"Closed date" fields — none
    # of this existed before (only `priority` itself). sla_due_at is computed
    # once at creation (app/utils/sla.py) from the priority at that time;
    # changing priority later does not recompute it, matching how a real
    # support desk's SLA clock works (the commitment was made at intake).
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client = relationship("Client", back_populates="tickets")
    partner_account = relationship("PartnerAccount", back_populates="tickets")
    assignee = relationship("User")
    replies = relationship("TicketReply", back_populates="ticket")
