import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.enums import LeadStatus, NotificationType, ProposalStatus
from app.models.lead import Lead
from app.models.proposal import Proposal
from app.models.user import User
from app.schemas.crm import ProposalCreate, ProposalOut, ProposalRejectRequest, ProposalReviewRequest
from app.services.email_service import send_proposal_email
from app.services.lead_pipeline import advance_lead_status, log_lead_activity
from app.services.notification_service import notify_roles
from app.services.project_provisioning import provision_project_for_accepted_proposal
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/proposals", tags=["CRM — Proposals"], dependencies=[Depends(require_roles("sales", "admin", "project_manager", "marketing"))])

crud = CRUDBase(Proposal, searchable_fields=["scope_summary"])
lead_crud = CRUDBase(Lead)

# Proposals priced above this value need a Finance/Admin discount-threshold sign-off before sending.
DISCOUNT_APPROVAL_THRESHOLD = 50_000


@router.get("", response_model=dict)
async def list_proposals(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("status", "lead_id") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[ProposalOut.model_validate(p) for p in items], message="Proposals fetched", meta=meta)


@router.post("", response_model=dict, status_code=201)
async def create_proposal(payload: ProposalCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # UAT closure pass §3: `version` defaulted to 1 at the model level and
    # nothing ever computed a real one — every proposal for the same lead,
    # including an explicit revision after a rejection, silently got
    # version=1 again (ProposalCreate doesn't even expose `version` as a
    # settable field). A revised proposal must outrank the one it replaces.
    max_version = (await db.execute(
        select(func.max(Proposal.version)).where(Proposal.lead_id == payload.lead_id)
    )).scalar_one()
    next_version = (max_version or 0) + 1
    proposal = await crud.create(db, {**payload.model_dump(), "created_by": current_user.id, "version": next_version})

    lead = await lead_crud.get(db, proposal.lead_id)
    await advance_lead_status(db, lead, LeadStatus.proposal_created)
    await log_lead_activity(
        db, proposal.lead_id, "proposal_created",
        f"Proposal v{proposal.version} drafted: {proposal.scope_summary[:120]} ({proposal.currency} {proposal.price})",
        current_user.id,
    )
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal drafted", status_code=201)


@router.post("/{proposal_id}/submit-for-review", response_model=dict)
async def submit_proposal_for_review(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Employee Draft -> Submitted for PM Review, an optional stage ahead of
    sending — staff with direct sending authority can still send straight
    from draft (see send_proposal below), this just makes the review gate
    available for teams that want it enforced."""
    proposal = await crud.get(db, proposal_id)
    if proposal.status != ProposalStatus.draft:
        raise ApiError.bad_request("Only a draft proposal can be submitted for review")
    proposal = await crud.update(db, proposal_id, {"status": ProposalStatus.submitted_for_review})
    await notify_roles(
        db, ["admin", "project_manager"], "Proposal ready for review",
        f"Proposal v{proposal.version} ({proposal.scope_summary[:80]}) was submitted for review.",
        NotificationType.info, f"/employee-portal?tab=proposals&proposal={proposal.id}",
    )
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal submitted for review")


@router.post("/{proposal_id}/review", response_model=dict, dependencies=[Depends(require_roles("admin", "project_manager"))])
async def review_proposal(proposal_id: uuid.UUID, payload: ProposalReviewRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    proposal = await crud.get(db, proposal_id)
    if proposal.status != ProposalStatus.submitted_for_review:
        raise ApiError.bad_request("Only a proposal submitted for review can be reviewed")
    new_status = ProposalStatus.pm_approved if payload.approved else ProposalStatus.pm_rejected
    proposal = await crud.update(db, proposal_id, {
        "status": new_status, "review_notes": payload.review_notes, "reviewed_by": current_user.id,
    })
    return success_response(data=ProposalOut.model_validate(proposal), message=f"Proposal {'approved' if payload.approved else 'sent back'}")


@router.post("/{proposal_id}/send", response_model=dict)
async def send_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    proposal = await crud.get(db, proposal_id)
    if proposal.status not in (ProposalStatus.draft, ProposalStatus.pm_approved):
        raise ApiError.bad_request("Only a draft or PM-approved proposal can be sent")

    proposal = await crud.update(db, proposal_id, {"status": ProposalStatus.sent, "sent_at": datetime.now(UTC)})
    lead = await lead_crud.update(db, proposal.lead_id, {"status": LeadStatus.proposal_sent})
    await send_proposal_email(lead.contact_name, lead.email, proposal.scope_summary, float(proposal.price), proposal.currency)
    await log_lead_activity(db, lead.id, "proposal_sent", f"Proposal v{proposal.version} emailed to {lead.email}")

    if float(proposal.price) > DISCOUNT_APPROVAL_THRESHOLD:
        await notify_roles(
            db, ["finance", "admin"], "Proposal above discount threshold",
            f"Proposal {proposal.id} for {proposal.price} {proposal.currency} was sent and exceeds the standard discount threshold — review pricing.",
            NotificationType.warning, f"/admin-panel?tab=projects&proposal={proposal.id}",
        )
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal sent")


@router.post("/{proposal_id}/accept", response_model=dict)
async def accept_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    proposal = await crud.get(db, proposal_id)
    if proposal.status not in (ProposalStatus.sent, ProposalStatus.viewed):
        raise ApiError.bad_request("Only a sent proposal can be accepted")

    proposal = await crud.update(db, proposal_id, {"status": ProposalStatus.accepted})
    await lead_crud.update(db, proposal.lead_id, {"status": LeadStatus.proposal_approved})
    await log_lead_activity(db, proposal.lead_id, "proposal_approved", f"Proposal v{proposal.version} accepted by the client")
    # Workflow doc's end-to-end diagram: "Client Accepts Proposal -> Project
    # Created" — no manual step in between. Idempotent (see
    # provision_project_for_accepted_proposal); a no-op if the lead hasn't
    # converted to a client yet.
    await provision_project_for_accepted_proposal(db, proposal)
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal accepted")


@router.post("/{proposal_id}/reject", response_model=dict)
async def reject_proposal(proposal_id: uuid.UUID, payload: ProposalRejectRequest = ProposalRejectRequest(), db: AsyncSession = Depends(get_db)):
    proposal = await crud.get(db, proposal_id)
    if proposal.status not in (ProposalStatus.sent, ProposalStatus.viewed):
        raise ApiError.bad_request("Only a sent proposal can be rejected")

    proposal = await crud.update(db, proposal_id, {"status": ProposalStatus.rejected, "rejection_reason": payload.reason})
    # A rejected proposal closes the lead out — matches the pipeline's
    # documented "proposal sent -> disqualified" branch (see
    # app/services/lead_pipeline.py); staff can still disqualify a lead
    # directly via POST /leads/{id}/disqualify for reasons unrelated to a
    # specific proposal.
    lead = await lead_crud.get(db, proposal.lead_id)
    if lead.status not in (LeadStatus.converted, LeadStatus.disqualified):
        lead.rejection_reason = payload.reason
        await db.commit()
        await advance_lead_status(db, lead, LeadStatus.disqualified)
    await log_lead_activity(db, proposal.lead_id, "disqualified", payload.reason or f"Proposal v{proposal.version} rejected by the client")
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal rejected")
