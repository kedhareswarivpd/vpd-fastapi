from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Leadership(Base):
    """Executive leadership team member — About page ("Executive Leadership" grid).
    Follows the same simple-CMS-resource shape as Award/Testimonial."""

    __tablename__ = "leadership"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    linkedin: Mapped[str | None] = mapped_column(String(500))
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
