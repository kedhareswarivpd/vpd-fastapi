import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import MeetingStatus


class Meeting(Base):
    __tablename__ = "meetings"

    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    agenda: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    meeting_link: Mapped[str | None] = mapped_column(String(500))
    organizer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus, name="meeting_status"), default=MeetingStatus.scheduled)
    notes: Mapped[str | None] = mapped_column(Text)
    # UAT closure pass §8: doc §13 — "If meetings are recorded, the
    # recording and/or meeting notes should be stored according to the
    # applicable access permissions." Notes already had a field/access path;
    # recordings had none at all. Stored as a URL (the recording file itself
    # lives in existing private object storage, same as EmployeeDocument/
    # ClientFile), shares the same staff-write/participant-read visibility
    # notes already uses rather than inventing a separate access path.
    recording_url: Mapped[str | None] = mapped_column(String(500))

    project = relationship("Project", back_populates="meetings")
    client = relationship("Client", back_populates="meetings")
    organizer = relationship("User")
