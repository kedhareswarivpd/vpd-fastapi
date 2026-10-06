import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.core.logger import logger
from app.crud.base import CRUDBase
from app.models.contract import Contract
from app.models.enums import ContractStatus, LeadStatus, ProposalStatus
from app.models.lead import Lead
from app.models.proposal import Proposal
from app.models.user import User
from app.schemas.crm import ContractCreate, ContractOut, ContractSign
from app.services.client_provisioning import provision_client_account
from app.services.lead_pipeline import advance_lead_status, log_lead_activity
from app.services.project_provisioning import provision_project_for_accepted_proposal
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/contracts", tags=["CRM — Contracts"], dependencies=[Depends(require_roles("sales", "admin", "project_manager", "marketing"))])

crud = CRUDBase(Contract)


@router.get("", response_model=dict)
async def list_contracts(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("status", "proposal_id") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[ContractOut.model_validate(c) for c in items], message="Contracts fetched", meta=meta)


@router.post("", response_model=dict, status_code=201)
async def create_contract(payload: ContractCreate, response: Response, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    proposal = (await db.execute(select(Proposal).where(Proposal.id == payload.proposal_id))).scalar_one_or_none()
    if proposal is None:
        raise ApiError.not_found("Proposal not found")
    if proposal.status != ProposalStatus.accepted:
        raise ApiError.bad_request("A contract can only be generated from an accepted proposal")

    # Check if a contract for this proposal already exists — return it gracefully (idempotent)
    existing = (await db.execute(select(Contract).where(Contract.proposal_id == payload.proposal_id))).scalar_one_or_none()
    if existing:
        # The route decorator's `status_code=201` is only a default — a
        # returned dict doesn't override the real HTTP status, only
        # `response.status_code` does (found as a side effect of fixing the
        # identical bug in finance.py::record_payment this session; without
        # this the real response stayed 201 even though nothing was created).
        response.status_code = 200
        return success_response(
            data=ContractOut.model_validate(existing),
            message="Contract already exists for this proposal",
            status_code=200,
        )

    try:
        contract = await crud.create(db, payload.model_dump())
    except Exception as exc:
        logger.exception("Failed to create contract for proposal %s: %s", payload.proposal_id, exc)
        raise ApiError.bad_request("Could not draft contract. Please verify proposal details and try again.") from exc

    await log_lead_activity(
        db, proposal.lead_id, "contract_generated",
        f"Contract drafted for proposal v{proposal.version} — pending signatures from both parties.",
        current_user.id,
    )
    return success_response(data=ContractOut.model_validate(contract), message="Contract drafted", status_code=201)


@router.post("/{contract_id}/sign", response_model=dict)
async def sign_contract(contract_id: uuid.UUID, payload: ContractSign, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    contract = await crud.get(db, contract_id)
    if contract.status == ContractStatus.signed:
        return success_response(data=ContractOut.model_validate(contract), message="Contract is already signed")

    proposal = (await db.execute(select(Proposal).where(Proposal.id == contract.proposal_id))).scalar_one_or_none()

    now = datetime.now(UTC)
    update_data = {}
    if payload.client_signed:
        update_data["signed_by_client_at"] = now
        if proposal:
            await log_lead_activity(db, proposal.lead_id, "contract_signed_client", f"Contract for proposal v{proposal.version} signed by the client.", current_user.id)
    if payload.company_signed:
        update_data["signed_by_company_at"] = now
        if proposal:
            await log_lead_activity(db, proposal.lead_id, "contract_signed_company", f"Contract for proposal v{proposal.version} signed by the company.", current_user.id)

    contract = await crud.update(db, contract_id, update_data)

    if contract.signed_by_client_at and contract.signed_by_company_at:
        contract = await crud.update(db, contract_id, {"status": ContractStatus.signed})

        lead = (await db.execute(select(Lead).where(Lead.id == proposal.lead_id))).scalar_one_or_none() if proposal else None

        if lead is not None and lead.status != LeadStatus.converted:
            client = None
            if payload.provision_client_account:
                try:
                    client = await provision_client_account(db, lead)
                except Exception as exc:  # noqa: BLE001 — contract stays signed even if account provisioning has an issue
                    logger.error(f"Client account provisioning failed for lead {lead.id}: {exc}")

            if client is not None:
                lead.converted_client_id = client.id
                await db.commit()
            await advance_lead_status(db, lead, LeadStatus.converted)
            await log_lead_activity(db, lead.id, "converted", f"Contract fully signed — converted to client account {client.company_name if client else lead.converted_client_id}.")

            # Auto-creates the project and sends the PM a notification with
            # full project + client details (see project_provisioning.py) —
            # this is what satisfies "PM gets notified about this project"
            # at the same moment credentials go out, no manual step needed.
            try:
                await provision_project_for_accepted_proposal(db, proposal)
            except Exception as exc:  # noqa: BLE001 — the client account/contract are already committed; a project-creation hiccup must not undo them
                logger.error(f"Auto project creation failed after contract signature for lead {lead.id}: {exc}")

    return success_response(data=ContractOut.model_validate(contract), message="Contract signature recorded")
