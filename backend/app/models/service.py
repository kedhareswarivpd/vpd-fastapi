from sqlalchemy import ARRAY, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Service(Base):
    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    icon: Mapped[str | None] = mapped_column(String(255))
    overview: Mapped[str | None] = mapped_column(Text)
    business_problems: Mapped[str | None] = mapped_column(Text)
    solutions: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    benefits: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    process: Mapped[list | None] = mapped_column(JSONB, default=list)
    technology_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    deliverables: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    related_industries: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    gallery: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    faqs: Mapped[list | None] = mapped_column(JSONB, default=list)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
