from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CareerEmploymentType, CareerStatus


class Career(Base):
    __tablename__ = "careers"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    department: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(150))
    employment_type: Mapped[CareerEmploymentType] = mapped_column(
        Enum(CareerEmploymentType, name="career_employment_type"), default=CareerEmploymentType.full_time
    )
    experience_required: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    status: Mapped[CareerStatus] = mapped_column(Enum(CareerStatus, name="career_status"), default=CareerStatus.open)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    applications = relationship("Application", back_populates="career")
