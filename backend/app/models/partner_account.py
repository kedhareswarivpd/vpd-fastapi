import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PartnerType


class PartnerAccount(Base):
    """A login-gated Partner Portal account — distinct from `Partner`
    (app/models/partner.py), which is the public CMS "our partners" logo
    listing on the marketing site. Named `PartnerAccount`/`partner_accounts`
    specifically to avoid colliding with that unrelated, pre-existing model."""

    __tablename__ = "partner_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    partnership_type: Mapped[PartnerType] = mapped_column(Enum(PartnerType, name="partner_type"), default=PartnerType.reseller)
    industry: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    account_manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)

    user = relationship("User", back_populates="partner_account")
    files = relationship("PartnerFile", back_populates="partner_account")
    tickets = relationship("Ticket", back_populates="partner_account")
