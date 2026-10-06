import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from app.schemas.common import TimestampedRead


class InvoiceCreate(BaseModel):
    invoice_number: str | None = None
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    amount: float = Field(gt=0)
    tax: float = Field(0, ge=0)
    currency: str = "INR"
    issue_date: date
    due_date: date
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    notes: str | None = None
    due_date: date | None = None


class InvoiceOut(TimestampedRead):
    invoice_number: str
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    amount: float
    tax: float
    total_amount: float
    currency: str
    issue_date: date
    due_date: date
    status: InvoiceStatus
    notes: str | None = None


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    method: PaymentMethod
    transaction_ref: str | None = None
    paid_at: datetime
    status: PaymentStatus = PaymentStatus.completed


class PaymentOut(TimestampedRead):
    invoice_id: uuid.UUID
    amount: float
    method: PaymentMethod
    transaction_ref: str | None = None
    paid_at: datetime
    status: PaymentStatus


class ClientPaymentOut(TimestampedRead):
    """Payment enriched with invoice_number for the client portal."""
    invoice_id: uuid.UUID
    invoice_number: str | None = None
    amount: float
    method: PaymentMethod
    transaction_ref: str | None = None
    paid_at: datetime
    status: PaymentStatus


class ClientFileCreate(BaseModel):
    name: str
    category: str
    file_url: str
    size_bytes: int | None = None
    uploaded_by: str | None = None


class ClientFileOut(TimestampedRead):
    client_id: uuid.UUID
    name: str
    category: str
    file_url: str
    size_bytes: int | None = None
    uploaded_by: str | None = None


class ClientReportCreate(BaseModel):
    title: str
    report_type: str
    period: str
    file_url: str | None = None
    size_bytes: int | None = None


class ClientReportOut(TimestampedRead):
    client_id: uuid.UUID
    title: str
    report_type: str
    period: str
    file_url: str | None = None
    size_bytes: int | None = None
