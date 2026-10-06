"""Schemas for support/ops modules: Ticket, Meeting, Notification, Media, Setting, AuditLog."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import MeetingStatus, NotificationType, TicketPriority, TicketStatus
from app.schemas.common import TimestampedRead


# ---------- Ticket ----------
class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: uuid.UUID | None = None
    resolution: str | None = None


class TicketOut(TimestampedRead):
    ticket_number: str
    client_id: uuid.UUID | None = None
    partner_account_id: uuid.UUID | None = None
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    assigned_to: uuid.UUID | None = None
    sla_due_at: datetime | None = None
    resolution: str | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None


class TicketReplyCreate(BaseModel):
    message: str | None = None
    content: str | None = None
    attachment_url: str | None = None

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        if not d.get("message") and d.get("content"):
            d["message"] = d.pop("content")
        else:
            d.pop("content", None)
        return d



class TicketReplyOut(TimestampedRead):
    ticket_id: uuid.UUID
    user_id: uuid.UUID
    message: str
    attachment_url: str | None = None


# ---------- Meeting ----------
class MeetingCreate(BaseModel):
    project_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    title: str
    agenda: str | None = None
    scheduled_at: datetime
    duration_minutes: int = 30
    meeting_link: str | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    scheduled_at: datetime | None = None
    status: MeetingStatus | None = None
    notes: str | None = None
    recording_url: str | None = None


class MeetingOut(TimestampedRead):
    project_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    title: str
    agenda: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    meeting_link: str | None = None
    organizer_id: uuid.UUID | None = None
    status: MeetingStatus
    notes: str | None = None
    recording_url: str | None = None


# ---------- Notification ----------
class NotificationOut(TimestampedRead):
    title: str
    message: str | None = None
    type: NotificationType
    link: str | None = None
    is_read: bool


class NotificationCreate(BaseModel):
    title: str
    message: str | None = None
    type: NotificationType = NotificationType.info
    link: str | None = None
    user_id: uuid.UUID | None = None
    roles: list[str] | None = None


# ---------- Media ----------
class MediaOut(TimestampedRead):
    file_name: str
    url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    uploaded_by: uuid.UUID | None = None
    folder: str


# ---------- Setting ----------
class SettingUpsert(BaseModel):
    value: Any
    group: str = "general"


class SettingOut(TimestampedRead):
    key: str
    value: Any
    group: str


# ---------- Audit Log ----------
class AuditLogOut(TimestampedRead):
    user_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    log_metadata: dict | None = None
