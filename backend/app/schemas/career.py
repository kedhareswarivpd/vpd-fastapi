import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.enums import ApplicationStatus, CareerEmploymentType, CareerStatus
from app.schemas.common import TimestampedRead


class CareerCreate(BaseModel):
    title: str
    slug: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: CareerEmploymentType = CareerEmploymentType.full_time
    experience_required: str | None = None
    description: str | None = None
    responsibilities: list[str] = []
    requirements: list[str] = []
    status: CareerStatus = CareerStatus.open


class CareerUpdate(BaseModel):
    description: str | None = None
    status: CareerStatus | None = None
    responsibilities: list[str] | None = None
    requirements: list[str] | None = None


class CareerOut(TimestampedRead):
    title: str
    slug: str
    department: str | None = None
    location: str | None = None
    employment_type: CareerEmploymentType
    experience_required: str | None = None
    description: str | None = None
    responsibilities: list[str] = []
    requirements: list[str] = []
    status: CareerStatus
    posted_at: datetime


class ApplicationCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    cover_letter: str | None = None
    linkedin_url: str | None = None


class ApplicationOut(TimestampedRead):
    career_id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None = None
    resume_url: str
    cover_letter: str | None = None
    linkedin_url: str | None = None
    status: ApplicationStatus


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
