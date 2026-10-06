import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.limiter import limiter
from app.core.logger import logger
from app.crud.base import CRUDBase
from app.models.contact_submission import ContactSubmission
from app.schemas.contact import ContactOut, ContactStatusUpdate, ContactSubmit
from app.services.email_service import send_contact_notification
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/contact", tags=["Contact"])

crud = CRUDBase(ContactSubmission, searchable_fields=["name", "email", "company"])


@router.post("", response_model=dict, status_code=201)
@limiter.limit("5/minute")
async def submit(request: Request, payload: ContactSubmit, db: AsyncSession = Depends(get_db)):
    submission = await crud.create(db, payload.model_dump())
    try:
        await send_contact_notification(submission.name, submission.email, submission.message, submission.subject)
    except Exception as exc:
        logger.error("Failed to send contact notification email: %s", exc)

    # Lead creation is a manual staff action (Mark In Progress -> Convert to
    # Lead -> Resolve in the Sales/Marketing Contact Submissions views), not
    # automatic on submission — see POST /leads (contact_submission_id links
    # the new lead back to this submission).
    return success_response(message="Thank you for reaching out — our team will get back to you shortly.", status_code=201)


@router.get("", response_model=dict, dependencies=[Depends(require_roles("admin", "sales", "marketing", "support"))])
async def list_submissions(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("department", "status") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[ContactOut.model_validate(s) for s in items], message="Submissions fetched", meta=meta)


@router.patch("/{submission_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "sales", "marketing", "support"))])
async def update_status(submission_id: uuid.UUID, payload: ContactStatusUpdate, db: AsyncSession = Depends(get_db)):
    from app.models.enums import ContactStatus, NotificationType
    from app.services.notification_service import notify_roles

    submission = await crud.update(db, submission_id, {"status": payload.status.value})

    # When a contact is picked up for follow-up, notify marketing so they can convert it to a lead
    if payload.status == ContactStatus.in_progress:
        try:
            await notify_roles(
                db, ["marketing"],
                "New contact ready for lead conversion",
                f"{submission.name} ({submission.email}) — {submission.subject or 'No subject'} — is in progress and ready to convert to a CRM lead.",
                NotificationType.info,
                "/marketing?tab=marketing-leads",
            )
        except Exception as exc:  # noqa: BLE001 — notification failure must not break the status update
            logger.warning("Failed to notify marketing of in_progress contact %s: %s", submission_id, exc)

    return success_response(data=ContactOut.model_validate(submission), message="Submission status updated")
