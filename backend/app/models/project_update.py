import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectUpdate(Base):
    """Workflow doc §8 ("Daily Project Updates") and §16's Employee/Client
    view split — this entity did not exist at all before the UAT closure
    pass that added it. An employee posts a dated progress note against a
    project they're actually assigned to; a PM/admin can flag individual
    updates as client_visible, which is the "approved" subset the doc says
    the client should see. Client-visible updates are read through a
    dedicated client-facing endpoint (app/routers/clients.py) that strips
    everything except the update text, date, and the author's display name
    — never employee_code/designation/internal user_id (see ClientProjectOut
    for the same principle applied to the project's team roster)."""

    __tablename__ = "project_updates"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True, nullable=False)
    update_text: Mapped[str] = mapped_column(Text, nullable=False)
    hours_logged: Mapped[float | None] = mapped_column(Numeric(5, 2))
    client_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project = relationship("Project")
    employee = relationship("Employee")
