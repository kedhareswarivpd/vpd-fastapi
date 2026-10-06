"""Schemas for the Sales CRM pipeline: Lead -> Proposal -> Contract."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ContractStatus, LeadSource, LeadStatus, ProposalStatus
from app.schemas.common import TimestampedRead


# ---------- Lead ----------
class LeadCreate(BaseModel):
    company: str | None = None
    contact_name: str
    email: EmailStr
    phone: str | None = None
    source: LeadSource = LeadSource.other
    estimated_value: float | None = Field(None, ge=0)
    notes: str | None = None
    contact_submission_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None


class LeadUpdate(BaseModel):
    # No `status` field on purpose — the pipeline is one-way and driven only
    # by the dedicated action endpoints (log-call, requirement-gathering,
    # disqualify, and the proposal/convert endpoints), never by a free-form
    # manual edit. See app/services/lead_pipeline.py.
    company: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    source: LeadSource | None = None
    estimated_value: float | None = Field(None, ge=0)
    notes: str | None = None
    owner_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    # Lead Evaluation record
    evaluation_date: date | None = None
    meeting_notes: str | None = None
    requirements_confirmed: bool | None = None
    delivery_timeline: str | None = None
    evaluation_result: str | None = None
    rejection_reason: str | None = None


class LeadOut(TimestampedRead):
    contact_submission_id: uuid.UUID | None = None
    company: str | None = None
    contact_name: str
    email: str
    phone: str | None = None
    source: LeadSource
    status: LeadStatus
    estimated_value: float | None = None
    notes: str | None = None
    owner_id: uuid.UUID | None = None
    converted_client_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    industry_id: uuid.UUID | None = None
    evaluation_date: date | None = None
    meeting_notes: str | None = None
    requirements_confirmed: bool | None = False
    delivery_timeline: str | None = None
    evaluation_result: str | None = None
    rejection_reason: str | None = None


class LeadLogCallRequest(BaseModel):
    notes: str = Field(min_length=1)


class LeadRequirementGatheringRequest(BaseModel):
    notes: str | None = None


class LeadDisqualifyRequest(BaseModel):
    reason: str = Field(min_length=1)


class LeadActivityOut(TimestampedRead):
    lead_id: uuid.UUID
    activity_type: str
    description: str | None = None
    actor_id: uuid.UUID | None = None


# ---------- Proposal ----------
class ProposalCreate(BaseModel):
    lead_id: uuid.UUID
    scope_summary: str
    price: float = Field(gt=0)
    currency: str = "USD"
    file_url: str | None = None
    service_id: uuid.UUID | None = None


class ProposalUpdate(BaseModel):
    scope_summary: str | None = None
    price: float | None = Field(None, gt=0)
    currency: str | None = None
    file_url: str | None = None
    status: ProposalStatus | None = None
    service_id: uuid.UUID | None = None


class ProposalOut(TimestampedRead):
    lead_id: uuid.UUID
    version: int
    scope_summary: str
    price: float
    currency: str
    status: ProposalStatus
    file_url: str | None = None
    sent_at: datetime | None = None
    viewed_at: datetime | None = None
    created_by: uuid.UUID | None = None
    client_comment: str | None = None
    rejection_reason: str | None = None
    service_id: uuid.UUID | None = None
    review_notes: str | None = None
    reviewed_by: uuid.UUID | None = None


class ProposalRejectRequest(BaseModel):
    reason: str | None = None


class ProposalReviewRequest(BaseModel):
    approved: bool
    review_notes: str | None = None


# ---------- Contract ----------
class ContractCreate(BaseModel):
    proposal_id: uuid.UUID
    document_url: str | None = None


class ContractSign(BaseModel):
    client_signed: bool = True
    company_signed: bool = True
    provision_client_account: bool = True


class ContractOut(TimestampedRead):
    proposal_id: uuid.UUID
    document_url: str | None = None
    status: ContractStatus
    signed_by_client_at: datetime | None = None
    signed_by_company_at: datetime | None = None
