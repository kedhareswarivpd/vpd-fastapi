import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CommentStatus


class Comment(Base):
    __tablename__ = "comments"

    blog_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blogs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommentStatus] = mapped_column(Enum(CommentStatus, name="comment_status"), default=CommentStatus.pending)

    blog = relationship("Blog", back_populates="comments")
