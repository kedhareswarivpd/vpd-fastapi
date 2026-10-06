from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import PartnerType


class Partner(Base):
    __tablename__ = "partners"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    logo: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[PartnerType] = mapped_column(Enum(PartnerType, name="partner_type"), default=PartnerType.technology_partner)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
