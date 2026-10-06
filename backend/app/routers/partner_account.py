import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.employee import Employee
from app.models.enums import TicketPriority
from app.models.partner_account import PartnerAccount
from app.models.partner_file import PartnerFile
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.client import TicketCreate
from app.schemas.ops import TicketOut
from app.schemas.partner_account import (
    PartnerAccountCreate,
    PartnerAccountOut,
    PartnerAccountUpdate,
    PartnerFileCreate,
    PartnerFileOut,
)
from app.utils.pagination import PageParams, bounded_select, page_params
from app.utils.responses import build_pagination_meta, success_response
from app.utils.sla import compute_sla_due_at

# Partner Portal — a login-gated self-service portal for an actual partner
# organization (reseller/technology/business partner), mirroring Client
# Portal's shape (self-service `/me/*` + admin management) per the workflow
# PDF's Client Portal pattern. Prefix is `/partner-accounts`, not `/partners`
# — that prefix is already the public "our partners" CMS logo listing
# (app/routers/partner.py), a different, unrelated, unauthenticated resource.
router = APIRouter(prefix="/partner-accounts", tags=["Partner Portal"], dependencies=[Depends(get_current_user)])

crud = CRUDBase(PartnerAccount, searchable_fields=["company_name", "country"])


async def _get_partner_account_for_user(db: AsyncSession, user: User) -> PartnerAccount:
    partner = (await db.execute(select(PartnerAccount).where(PartnerAccount.user_id == user.id))).scalar_one_or_none()
    if not partner:
        partner = PartnerAccount(user_id=user.id, company_name=user.name)
        db.add(partner)
        await db.commit()
        await db.refresh(partner)
    return partner


async def _require_assigned_account_manager(db: AsyncSession, current_user: User, partner: PartnerAccount) -> None:
    """Same ownership gap fix as clients.py — a role check alone isn't
    ownership. admin/super_admin bypass."""
    if current_user.role in ("admin", "super_admin"):
        return
    employee = (await db.execute(select(Employee).where(Employee.user_id == current_user.id))).scalar_one_or_none()
    if employee is None or partner.account_manager_id != employee.id:
        raise ApiError.forbidden("You are not the assigned account manager for this partner account")


# ---------- Partner self-service (Partner Portal) ----------
@router.get("/me/profile", response_model=dict)
async def my_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await _get_partner_account_for_user(db, current_user)
    data = PartnerAccountOut.model_validate(partner).model_dump()
    data["contact_name"] = current_user.name
    data["email"] = current_user.email
    return success_response(data=data)


@router.put("/me/profile", response_model=dict)
async def update_my_profile(payload: PartnerAccountUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await _get_partner_account_for_user(db, current_user)
    # A partner may edit their own descriptive info, not who manages their
    # account — that stays an admin-only assignment.
    data = payload.model_dump(exclude_unset=True, exclude={"account_manager_id"})
    partner = await crud.update(db, partner.id, data)
    return success_response(data=PartnerAccountOut.model_validate(partner), message="Profile updated")


@router.get("/me/files", response_model=dict)
async def my_files(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await _get_partner_account_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(PartnerFile).where(PartnerFile.partner_account_id == partner.id)
            .order_by(PartnerFile.created_at.desc())
        )
    )
    return success_response(data=[PartnerFileOut.model_validate(f) for f in result.scalars().all()])


@router.post("/me/files", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "sales"))])
async def upload_partner_file(partner_account_id: uuid.UUID, payload: PartnerFileCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await crud.get(db, partner_account_id)
    await _require_assigned_account_manager(db, current_user, partner)
    f = PartnerFile(**payload.model_dump(), partner_account_id=partner_account_id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return success_response(data=PartnerFileOut.model_validate(f), message="File uploaded", status_code=201)


@router.get("/me/tickets", response_model=dict)
async def my_tickets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await _get_partner_account_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Ticket).where(Ticket.partner_account_id == partner.id)
            .order_by(Ticket.created_at.desc())
        )
    )
    return success_response(data=[TicketOut.model_validate(t) for t in result.scalars().all()])


@router.post("/me/tickets", response_model=dict, status_code=201)
async def create_ticket(payload: TicketCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    partner = await _get_partner_account_for_user(db, current_user)
    ticket_number = f"TCK-{int(datetime.utcnow().timestamp())}"
    ticket = Ticket(
        **payload.model_dump(), partner_account_id=partner.id, ticket_number=ticket_number,
        sla_due_at=compute_sla_due_at(TicketPriority(payload.priority)),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return success_response(data=TicketOut.model_validate(ticket), message="Support ticket created", status_code=201)


# ---------- Admin / Sales management ----------
@router.get("", response_model=dict, dependencies=[Depends(require_roles("admin", "sales"))])
async def list_partner_accounts(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("partnership_type", "industry") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[PartnerAccountOut.model_validate(p) for p in items], message="Partner accounts fetched", meta=meta)


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "sales"))])
async def create_partner_account(payload: PartnerAccountCreate, db: AsyncSession = Depends(get_db)):
    partner = await crud.create(db, payload.model_dump())
    return success_response(data=PartnerAccountOut.model_validate(partner), message="Partner account created successfully", status_code=201)
