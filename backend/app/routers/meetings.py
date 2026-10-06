import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.logger import logger
from app.crud.base import CRUDBase
from app.models.client import Client
from app.models.enums import NotificationType
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas.ops import MeetingCreate, MeetingOut, MeetingUpdate
from app.services.email_service import send_meeting_scheduled_email
from app.services.notification_service import notify_user
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/meetings", tags=["Sales CRM — Meetings"], dependencies=[Depends(require_roles("admin", "sales", "project_manager"))])

crud = CRUDBase(Meeting, searchable_fields=["title", "agenda"])


@router.get("", response_model=dict)
async def list_meetings(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("status", "client_id", "project_id") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[MeetingOut.model_validate(m) for m in items], message="Meetings fetched", meta=meta)


@router.get("/{meeting_id}", response_model=dict)
async def get_meeting(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    meeting = await crud.get(db, meeting_id)
    return success_response(data=MeetingOut.model_validate(meeting))


@router.post("", response_model=dict, status_code=201)
async def create_meeting(payload: MeetingCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    data = payload.model_dump()
    data["organizer_id"] = current_user.id
    meeting = await crud.create(db, data)

    if meeting.client_id:
        await _notify_client_of_meeting(db, meeting)

    return success_response(data=MeetingOut.model_validate(meeting), message="Meeting created", status_code=201)


async def _notify_client_of_meeting(db: AsyncSession, meeting: Meeting) -> None:
    """Best-effort, mirrors the pattern used elsewhere in this codebase for
    post-commit notification/email side effects (e.g. contracts.py's
    _send_client_welcome) — the meeting itself is already created by the
    time this runs, so a delivery failure here shouldn't undo it or fail the
    request."""
    try:
        result = await db.execute(
            select(Client, User).join(User, User.id == Client.user_id).where(Client.id == meeting.client_id)
        )
        row = result.first()
        if row is None:
            return
        client, user = row
        await notify_user(
            db, user.id, f"Meeting scheduled: {meeting.title}",
            f"A meeting has been scheduled for {meeting.scheduled_at.strftime('%B %d, %Y at %I:%M %p')}.",
            NotificationType.info, "/client?tab=meetings",
        )
        await send_meeting_scheduled_email(
            user.name, user.email, meeting.title,
            meeting.scheduled_at.strftime("%B %d, %Y at %I:%M %p"),
            meeting.duration_minutes, meeting.meeting_link, meeting.agenda,
        )
    except Exception as exc:  # noqa: BLE001 — meeting creation must not fail over notification/email delivery
        logger.warning("Failed to notify client of meeting %s: %s", meeting.id, exc)


@router.patch("/{meeting_id}", response_model=dict)
async def update_meeting(meeting_id: uuid.UUID, payload: MeetingUpdate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    meeting = await crud.update(db, meeting_id, data)
    return success_response(data=MeetingOut.model_validate(meeting), message="Meeting updated")


@router.delete("/{meeting_id}", response_model=dict)
async def cancel_meeting(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # A real bug found during a documentation review: this endpoint is named
    # (and responds) as "cancel" but was hard-deleting the row, losing
    # meeting history rather than marking it cancelled. Fixed to match its
    # own stated intent.
    meeting = await crud.update(db, meeting_id, {"status": "cancelled"})
    return success_response(data=MeetingOut.model_validate(meeting), message="Meeting cancelled")
