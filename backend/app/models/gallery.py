import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import GalleryType


class Gallery(Base):
    __tablename__ = "gallery"

    title: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[GalleryType] = mapped_column(Enum(GalleryType, name="gallery_type"), default=GalleryType.image)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    album_name: Mapped[str | None] = mapped_column(String(150))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    project = relationship("Project", back_populates="gallery_items")
