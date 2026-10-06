import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ContactStatus
from app.schemas.common import TimestampedRead


class ContactSubmit(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    department: str | None = None
    subject: str | None = None
    message: str
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    expected_budget: float | None = Field(None, ge=0)
    requirements: str | None = None


class ContactOut(TimestampedRead):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    department: str | None = None
    subject: str | None = None
    message: str
    status: ContactStatus
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    expected_budget: float | None = None
    requirements: str | None = None
    lead_id: uuid.UUID | None = None


class ContactStatusUpdate(BaseModel):
    status: ContactStatus
