import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(255))
    billing_address: Mapped[str | None] = mapped_column(Text)
    account_manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)

    user = relationship("User", back_populates="client_profile")
    projects = relationship("Project", back_populates="client")
    invoices = relationship("Invoice", back_populates="client")
    tickets = relationship("Ticket", back_populates="client")
    testimonials = relationship("Testimonial", back_populates="client")
    meetings = relationship("Meeting", back_populates="client")
    files = relationship("ClientFile", back_populates="client")
    reports = relationship("ClientReport", back_populates="client")
