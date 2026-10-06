from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    value: Mapped[dict | list | str | None] = mapped_column(JSONB)
    group: Mapped[str] = mapped_column(String(50), default="general")
