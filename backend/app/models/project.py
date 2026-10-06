import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import project_members
from app.models.enums import ProjectStatus


class Project(Base):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True)
    # UAT closure pass, section 1: the workflow doc requires a project to be
    # traceable back to the proposal/lead that produced it ("Project linked
    # to correct proposal/lead where applicable") — no such link existed at
    # all before this. `unique=True` is the actual answer to "should the
    # same accepted proposal be able to spawn two projects?" — no; this
    # constraint is the enforcement, not just documentation of the rule.
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("proposals.id"), unique=True, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), index=True)
    industry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("industries.id"), index=True)
    overview: Mapped[str | None] = mapped_column(Text)
    challenge: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    technology_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    architecture_notes: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    budget: Mapped[float | None] = mapped_column(Numeric(14, 2))
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, name="project_status"), default=ProjectStatus.planning)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    project_manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    cover_image: Mapped[str | None] = mapped_column(String(500))
    video_url: Mapped[str | None] = mapped_column(String(500))
    deliverables: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    gallery: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    downloads: Mapped[list | None] = mapped_column(JSONB, default=list)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # Final Delivery / Client Approval workflow: "Project Execution -> Final
    # Review -> Completed -> Deliverables Shared -> Client Review -> Client
    # Approval" had no backing state beyond the generic `status` enum — a
    # client had no way to formally approve or request changes on a
    # completed project's final delivery.
    completion_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_review_status: Mapped[str | None] = mapped_column(String(30))
    client_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_feedback: Mapped[str | None] = mapped_column(Text)
    final_delivery_version: Mapped[int] = mapped_column(Integer, default=0)

    client = relationship("Client", back_populates="projects")
    tasks = relationship("Task", back_populates="project")
    invoices = relationship("Invoice", back_populates="project")
    case_studies = relationship("CaseStudy", back_populates="project")
    meetings = relationship("Meeting", back_populates="project")
    timesheets = relationship("Timesheet", back_populates="project")
    gallery_items = relationship("Gallery", back_populates="project")
    team = relationship("Employee", secondary=project_members, back_populates="projects")
