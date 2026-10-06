import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TimesheetStatus


class Timesheet(Base):
    __tablename__ = "timesheets"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TimesheetStatus] = mapped_column(Enum(TimesheetStatus, name="timesheet_status"), default=TimesheetStatus.draft)

    employee = relationship("Employee", back_populates="timesheets")
    project = relationship("Project", back_populates="timesheets")
    task = relationship("Task", back_populates="timesheets")
