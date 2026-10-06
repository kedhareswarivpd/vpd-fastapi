import uuid

from pydantic import BaseModel

from app.models.enums import PartnerType
from app.schemas.common import TimestampedRead


class PartnerAccountCreate(BaseModel):
    user_id: uuid.UUID
    company_name: str | None = None
    partnership_type: PartnerType = PartnerType.reseller
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    notes: str | None = None


class PartnerAccountUpdate(BaseModel):
    company_name: str | None = None
    partnership_type: PartnerType | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    notes: str | None = None
    account_manager_id: uuid.UUID | None = None


class PartnerAccountOut(TimestampedRead):
    user_id: uuid.UUID
    company_name: str | None = None
    partnership_type: PartnerType
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    notes: str | None = None
    account_manager_id: uuid.UUID | None = None


class PartnerFileCreate(BaseModel):
    name: str
    category: str
    file_url: str
    size_bytes: int | None = None
    uploaded_by: str | None = None


class PartnerFileOut(TimestampedRead):
    partner_account_id: uuid.UUID
    name: str
    category: str
    file_url: str
    size_bytes: int | None = None
    uploaded_by: str | None = None
