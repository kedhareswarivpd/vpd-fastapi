from sqlalchemy import ARRAY, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Solution(Base):
    __tablename__ = "solutions"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    icon: Mapped[str | None] = mapped_column(String(255))
    overview: Mapped[str | None] = mapped_column(Text)
    problem_statement: Mapped[str | None] = mapped_column(Text)
    approach: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    outcomes: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    related_industries: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    related_services: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
