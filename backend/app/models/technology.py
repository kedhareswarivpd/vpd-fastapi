from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TechnologyCategory


class Technology(Base):
    __tablename__ = "technologies"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[TechnologyCategory] = mapped_column(Enum(TechnologyCategory, name="technology_category"), default=TechnologyCategory.other)
    logo: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
