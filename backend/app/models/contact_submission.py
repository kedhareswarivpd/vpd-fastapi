import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ContactStatus


class ContactSubmission(Base):
    __tablename__ = "contact_submissions"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    company: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ContactStatus] = mapped_column(Enum(ContactStatus, name="contact_status"), default=ContactStatus.new)
    # Contact->Lead auto-creation: the workflow doc's contact form collects
    # service interest, industry, budget, and requirements, and expects a
    # Lead to be generated automatically rather than left for staff to
    # manually re-key. service_id/industry_id are nullable FKs (the public
    # form may not always know these) rather than required.
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), index=True)
    industry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("industries.id"), index=True)
    expected_budget: Mapped[float | None] = mapped_column(Numeric(12, 2))
    requirements: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), index=True)
