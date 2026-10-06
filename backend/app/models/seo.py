from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SeoMetadata(Base):
    __tablename__ = "seo_metadata"

    page_path: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(320))
    keywords: Mapped[str | None] = mapped_column(String(500))
    og_title: Mapped[str | None] = mapped_column(String(160))
    og_description: Mapped[str | None] = mapped_column(String(320))
    og_image: Mapped[str | None] = mapped_column(String(500))
    og_type: Mapped[str | None] = mapped_column(String(50), default="website")
    canonical_url: Mapped[str | None] = mapped_column(String(500))
    schema_markup: Mapped[dict | None] = mapped_column(JSONB)
    no_index: Mapped[bool] = mapped_column(default=False)
