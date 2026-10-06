from sqlalchemy import ARRAY, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    tagline: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    benefits: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    pricing_tiers: Mapped[list | None] = mapped_column(JSONB, default=list)
    technology_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    use_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str | None] = mapped_column(String(255))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
