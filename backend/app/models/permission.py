from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import role_permissions


class Permission(Base):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
