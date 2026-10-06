import uuid

from pydantic import BaseModel

from app.schemas.common import TimestampedRead


class ClientCreate(BaseModel):
    user_id: uuid.UUID
    company_name: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    billing_address: str | None = None
    account_manager_id: uuid.UUID | None = None


class ClientUpdate(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    billing_address: str | None = None
    account_manager_id: uuid.UUID | None = None


class ClientOut(TimestampedRead):
    user_id: uuid.UUID
    company_name: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    billing_address: str | None = None
    account_manager_id: uuid.UUID | None = None


class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "medium"
