import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ContractStatus


class Contract(Base):
    __tablename__ = "contracts"

    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proposals.id"), unique=True, nullable=False)
    document_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus, name="contract_status"), default=ContractStatus.pending)
    signed_by_client_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_by_company_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    proposal = relationship("Proposal", back_populates="contract")
