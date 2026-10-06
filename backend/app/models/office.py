from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Office(Base):
    """Global office location — About page's "Global Presence" map/list.
    Follows the same simple-CMS-resource shape as Award/Testimonial."""

    __tablename__ = "offices"

    city: Mapped[str] = mapped_column(String(150), nullable=False)
    country: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    is_headquarters: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
