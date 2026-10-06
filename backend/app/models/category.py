from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CategoryType


class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(170), nullable=False, unique=True)
    type: Mapped[CategoryType] = mapped_column(Enum(CategoryType, name="category_type"), default=CategoryType.blog)

    blogs = relationship("Blog", back_populates="category")
