import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.client import Client
from app.models.client_file import ClientFile
from app.models.client_report import ClientReport
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.enums import LeadStatus, NotificationType, ProposalStatus, TicketPriority
from app.models.invoice import Invoice
from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.payment import Payment
from app.models.project import Project
from app.models.project_deliverable import ProjectDeliverable
from app.models.project_milestone import ProjectMilestone
from app.models.project_update import ProjectUpdate as ProjectUpdateModel
from app.models.proposal import Proposal
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, TicketCreate
from app.schemas.crm import ContractOut, ProposalOut, ProposalRejectRequest
from app.schemas.finance import (
    ClientFileOut,
    ClientPaymentOut,
    ClientReportCreate,
    ClientReportOut,
    InvoiceOut,
)
from app.schemas.ops import MeetingOut, TicketOut
from app.schemas.project import ClientProjectOut
from app.schemas.project_milestone import (
    ProjectDeliverableOut,
    ProjectDeliverableReviewRequest,
    ProjectMilestoneOut,
)
from app.schemas.project_update import ClientProjectUpdateOut
from app.services.notification_service import notify_roles
from app.services.project_provisioning import provision_project_for_accepted_proposal
from app.utils.pagination import PageParams, bounded_select, page_params
from app.utils.responses import build_pagination_meta, success_response
from app.utils.sla import compute_sla_due_at
from app.utils.uploads import load_private_file, save_upload

router = APIRouter(prefix="/clients", tags=["Clients"], dependencies=[Depends(get_current_user)])

crud = CRUDBase(Client, searchable_fields=["company_name", "country"])


async def _get_client_for_user(db: AsyncSession, user: User) -> Client:
    # D5 (UAT_REPORT.md): this router's /me/* routes are only gated by
    # get_current_user, not require_roles("client") — restricting the whole
    # router would break the staff-facing routes declared further down in
    # this same file, so the guard lives here instead. Without it, any
    # authenticated staff member hitting a /me/* route (e.g. testing in
    # Swagger) would silently get a junk Client profile auto-created and
    # tied to their own admin/employee account.
    if user.role != "client":
        raise ApiError.forbidden("This endpoint is only available to client accounts")
    client = (await db.execute(select(Client).where(Client.user_id == user.id))).scalar_one_or_none()
    if not client:
        client = Client(user_id=user.id, company_name=user.name)
        db.add(client)
        await db.commit()
        await db.refresh(client)
    return client


async def _require_assigned_account_manager(db: AsyncSession, current_user: User, client: Client) -> None:
    """A role check alone (admin/project_manager/finance) isn't ownership —
    without this, any staff member with the right role could attach a
    file/report to any client, not just the ones they're actually assigned
    to manage (a real IDOR-adjacent gap found during a documentation
    review, not caught by the existing RBAC matrix since that only tests
    role gating, not per-resource ownership). admin/super_admin bypass,
    matching require_roles()'s own bypass convention elsewhere."""
    if current_user.role in ("admin", "super_admin"):
        return
    employee = (await db.execute(select(Employee).where(Employee.user_id == current_user.id))).scalar_one_or_none()
    if employee is None or client.account_manager_id != employee.id:
        raise ApiError.forbidden("You are not the assigned account manager for this client")


# ---------- Client self-service (Client Portal) ----------
@router.get("/me/profile", response_model=dict)
async def my_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    client_data = ClientOut.model_validate(client).model_dump()
    client_data["contact_name"] = current_user.name
    client_data["email"] = current_user.email
    return success_response(data=client_data)


@router.get("/me/projects", response_model=dict)
async def my_projects(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Project).where(Project.client_id == client.id).order_by(Project.created_at.desc())
        )
    )
    projects = result.scalars().unique().all()

    # D12 (UAT_REPORT.md): the client view must not include the internal
    # team roster (see ClientProjectOut's docstring) — just resolve the PM's
    # name as the one designated point of contact the doc calls for.
    pm_ids = {p.project_manager_id for p in projects if p.project_manager_id}
    pm_names: dict = {}
    if pm_ids:
        pm_result = await db.execute(select(User.id, User.name).where(User.id.in_(pm_ids)))
        pm_names = dict(pm_result.all())

    out = []
    for p in projects:
        data = ClientProjectOut.model_validate(p).model_dump()
        data["project_manager_name"] = pm_names.get(p.project_manager_id)
        out.append(data)
    return success_response(data=out)


@router.get("/me/projects/{project_id}/updates", response_model=dict)
async def my_project_updates(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Workflow doc §8/§16: the client sees only the PM-approved subset of
    daily updates, with no internal employee IDs/codes — see
    ProjectUpdate's model docstring. Ownership-checked: 404 (not 403) if
    the project isn't this client's own."""
    client = await _get_client_for_user(db, current_user)
    project = (await db.execute(select(Project).where(Project.id == project_id, Project.client_id == client.id))).scalar_one_or_none()
    if project is None:
        raise ApiError.not_found("Project not found")

    result = await db.execute(
        select(ProjectUpdateModel, User.name)
        .join(Employee, Employee.id == ProjectUpdateModel.employee_id)
        .join(User, User.id == Employee.user_id)
        .where(ProjectUpdateModel.project_id == project_id, ProjectUpdateModel.client_visible.is_(True))
        .order_by(ProjectUpdateModel.created_at.desc())
    )
    out = [
        ClientProjectUpdateOut(id=u.id, update_text=u.update_text, created_at=u.created_at, author_name=name).model_dump()
        for u, name in result.all()
    ]
    return success_response(data=out)


async def _get_own_project(db: AsyncSession, client: Client, project_id: uuid.UUID) -> Project:
    project = (await db.execute(select(Project).where(Project.id == project_id, Project.client_id == client.id))).scalar_one_or_none()
    if project is None:
        raise ApiError.not_found("Project not found")
    return project


@router.get("/me/projects/{project_id}/milestones", response_model=dict)
async def my_project_milestones(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    await _get_own_project(db, client, project_id)
    result = await db.execute(
        select(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id, ProjectMilestone.client_visible.is_(True))
        .order_by(ProjectMilestone.order, ProjectMilestone.due_date)
    )
    return success_response(data=[ProjectMilestoneOut.model_validate(m) for m in result.scalars().all()])


@router.get("/me/projects/{project_id}/deliverables", response_model=dict)
async def my_project_deliverables(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    await _get_own_project(db, client, project_id)
    # Only deliverables actually submitted for review are shown — a
    # deliverable staff are still drafting internally isn't "shared" yet.
    result = await db.execute(
        select(ProjectDeliverable)
        .where(ProjectDeliverable.project_id == project_id, ProjectDeliverable.status != "pending")
        .order_by(ProjectDeliverable.created_at.desc())
    )
    return success_response(data=[ProjectDeliverableOut.model_validate(d) for d in result.scalars().all()])


@router.post("/me/projects/{project_id}/deliverables/{deliverable_id}/review", response_model=dict)
async def review_deliverable(
    project_id: uuid.UUID, deliverable_id: uuid.UUID, payload: ProjectDeliverableReviewRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    client = await _get_client_for_user(db, current_user)
    await _get_own_project(db, client, project_id)
    deliverable = (await db.execute(
        select(ProjectDeliverable).where(ProjectDeliverable.id == deliverable_id, ProjectDeliverable.project_id == project_id)
    )).scalar_one_or_none()
    if deliverable is None:
        raise ApiError.not_found("Deliverable not found")
    if deliverable.status != "submitted":
        raise ApiError.bad_request("Only a submitted deliverable can be reviewed")
    deliverable.status = "approved" if payload.approved else "rejected"
    deliverable.client_comment = payload.client_comment
    if payload.approved:
        deliverable.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(deliverable)
    return success_response(data=ProjectDeliverableOut.model_validate(deliverable), message=f"Deliverable {deliverable.status}")


@router.post("/me/projects/{project_id}/approve-delivery", response_model=dict)
async def approve_project_delivery(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Client Review -> Client Approval: the final sign-off on a completed
    project's delivery."""
    client = await _get_client_for_user(db, current_user)
    project = await _get_own_project(db, client, project_id)
    if project.client_review_status != "pending":
        raise ApiError.bad_request("This project is not currently awaiting your review")
    project.client_review_status = "approved"
    project.client_approved_at = datetime.now(UTC)
    project.final_delivery_version += 1
    await db.commit()
    await db.refresh(project)
    await notify_roles(
        db, ["admin", "project_manager"], "Client approved project delivery",
        f"{client.company_name or current_user.name} approved the final delivery of '{project.title}'.",
        NotificationType.success, f"/employee-portal?tab=projects&project={project.id}",
    )
    return success_response(data=ClientProjectOut.model_validate(project).model_dump(), message="Delivery approved")


@router.post("/me/projects/{project_id}/request-changes", response_model=dict)
async def request_project_changes(project_id: uuid.UUID, payload: ProposalRejectRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Client Review -> Request Changes: the workflow doc's alternate
    branch to Client Approval. Reuses ProposalRejectRequest's shape
    (an optional `reason`) rather than defining a near-identical schema."""
    client = await _get_client_for_user(db, current_user)
    project = await _get_own_project(db, client, project_id)
    if project.client_review_status != "pending":
        raise ApiError.bad_request("This project is not currently awaiting your review")
    project.client_review_status = "changes_requested"
    project.client_feedback = payload.reason
    await db.commit()
    await db.refresh(project)
    await notify_roles(
        db, ["admin", "project_manager"], "Client requested changes to project delivery",
        f"{client.company_name or current_user.name} requested changes on '{project.title}'" + (f": {payload.reason}" if payload.reason else "."),
        NotificationType.warning, f"/employee-portal?tab=projects&project={project.id}",
    )
    return success_response(data=ClientProjectOut.model_validate(project).model_dump(), message="Change request submitted")


@router.get("/me/invoices", response_model=dict)
async def my_invoices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(select(Invoice).where(Invoice.client_id == client.id).order_by(Invoice.issue_date.desc()))
    )
    return success_response(data=[InvoiceOut.model_validate(i) for i in result.scalars().all()])


@router.get("/me/tickets", response_model=dict)
async def my_tickets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(bounded_select(select(Ticket).where(Ticket.client_id == client.id).order_by(Ticket.created_at.desc())))
    return success_response(data=[TicketOut.model_validate(t) for t in result.scalars().all()])


@router.post("/me/tickets", response_model=dict, status_code=201)
async def create_ticket(payload: TicketCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    ticket_number = f"TCK-{int(datetime.utcnow().timestamp())}"
    ticket = Ticket(
        **payload.model_dump(), client_id=client.id, ticket_number=ticket_number,
        sla_due_at=compute_sla_due_at(TicketPriority(payload.priority)),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return success_response(data=TicketOut.model_validate(ticket), message="Support ticket created", status_code=201)


# Workflow doc §7 requires the client to review and Accept/Reject a proposal
# themselves from the Client Portal — previously /proposals/{id}/accept and
# /reject were staff-only (require_roles("sales","admin","project_manager",
# "marketing")), so a client could never do this step at all. A Proposal has
# no direct client_id (it belongs to the Lead that preceded client
# conversion — see app/models/proposal.py), so ownership here is: the
# proposal's lead must have converted to *this* logged-in client.
@router.get("/me/proposals", response_model=dict)
async def my_proposals(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Proposal).join(Lead, Proposal.lead_id == Lead.id)
            .where(Lead.converted_client_id == client.id).order_by(Proposal.created_at.desc())
        )
    )
    return success_response(data=[ProposalOut.model_validate(p) for p in result.scalars().all()])


@router.get("/me/contracts", response_model=dict)
async def my_contracts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Surfaces the contract(s) generated from this client's own proposals —
    shown alongside them under the Proposals section so the client can see
    generation/signature status even though the actual signing is recorded
    by staff (see contracts.py::sign_contract), not done through this
    portal."""
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Contract).join(Proposal, Contract.proposal_id == Proposal.id).join(Lead, Proposal.lead_id == Lead.id)
            .where(Lead.converted_client_id == client.id).order_by(Contract.created_at.desc())
        )
    )
    return success_response(data=[ContractOut.model_validate(c) for c in result.scalars().all()])


async def _get_own_sent_proposal(db: AsyncSession, client: Client, proposal_id: uuid.UUID) -> Proposal:
    proposal = (
        await db.execute(
            select(Proposal).join(Lead, Proposal.lead_id == Lead.id)
            .where(Proposal.id == proposal_id, Lead.converted_client_id == client.id)
        )
    ).scalar_one_or_none()
    if proposal is None:
        # 404, not 403 — don't confirm to a client that a proposal ID exists
        # but belongs to someone else.
        raise ApiError.not_found("Proposal not found")
    if proposal.status != ProposalStatus.sent:
        raise ApiError.bad_request("Only a sent proposal can be accepted or rejected")
    return proposal


@router.post("/me/proposals/{proposal_id}/accept", response_model=dict)
async def accept_my_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    proposal = await _get_own_sent_proposal(db, client, proposal_id)
    proposal.status = ProposalStatus.accepted
    # UAT closure pass §3: the staff-facing POST /proposals/{id}/accept updates
    # Lead.status to proposal_approved, but this client-facing mirror never did
    # — a client accepting their own proposal left the lead stuck at
    # proposal_sent forever, invisible to the sales pipeline.
    lead = (await db.execute(select(Lead).where(Lead.id == proposal.lead_id))).scalar_one_or_none()
    if lead is not None:
        lead.status = LeadStatus.proposal_approved
    await db.commit()
    await db.refresh(proposal)
    await notify_roles(
        db, ["admin", "project_manager"], "Proposal accepted",
        f"{client.company_name or current_user.name} accepted proposal v{proposal.version} — ready to start the project.",
        NotificationType.success, f"/employee-portal?tab=proposals&proposal={proposal.id}",
    )
    # Workflow doc's end-to-end diagram: "Client Accepts Proposal -> Project
    # Created" — this is the path an actual client uses to accept, so the
    # auto-creation has to live here too, not just the staff-side mirror.
    await provision_project_for_accepted_proposal(db, proposal)
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal accepted")


@router.post("/me/proposals/{proposal_id}/reject", response_model=dict)
async def reject_my_proposal(
    proposal_id: uuid.UUID, payload: ProposalRejectRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    client = await _get_client_for_user(db, current_user)
    proposal = await _get_own_sent_proposal(db, client, proposal_id)
    proposal.status = ProposalStatus.rejected
    proposal.rejection_reason = payload.reason
    await db.commit()
    await db.refresh(proposal)
    reason_note = f" Reason: {payload.reason}" if payload.reason else ""
    await notify_roles(
        db, ["admin", "project_manager"], "Proposal rejected",
        f"{client.company_name or current_user.name} rejected proposal v{proposal.version}.{reason_note}",
        NotificationType.warning, f"/employee-portal?tab=proposals&proposal={proposal.id}",
    )
    return success_response(data=ProposalOut.model_validate(proposal), message="Proposal rejected")


@router.get("/me/payments", response_model=dict)
async def my_payments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Payment, Invoice.invoice_number)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(Invoice.client_id == client.id)
            .order_by(Payment.paid_at.desc())
        )
    )
    rows = result.all()
    out = []
    for payment, invoice_number in rows:
        item = ClientPaymentOut.model_validate(payment)
        item.invoice_number = invoice_number
        out.append(item)
    return success_response(data=out)


@router.get("/me/meetings", response_model=dict)
async def my_meetings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    # Eager-load the organizer in the same query instead of one extra
    # per-meeting lookup (CF-AUD-011 N+1).
    result = await db.execute(
        bounded_select(
            select(Meeting)
            .options(selectinload(Meeting.organizer))
            .where(Meeting.client_id == client.id)
            .order_by(Meeting.scheduled_at.desc())
        )
    )
    meetings = result.scalars().all()
    data = []
    for m in meetings:
        meeting = MeetingOut.model_validate(m).model_dump()
        meeting["attendees"] = [m.organizer.name] if m.organizer else []
        data.append(meeting)
    return success_response(data=data)


@router.get("/me/files", response_model=dict)
async def my_files(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(select(ClientFile).where(ClientFile.client_id == client.id).order_by(ClientFile.created_at.desc()))
    )
    return success_response(data=[ClientFileOut.model_validate(f) for f in result.scalars().all()])


# Workflow doc §11 requires document exchange in BOTH directions (Company ->
# Client and Client -> Company). Previously there was no working upload path
# at all here — this "/me/files" POST existed but only accepted a pre-existing
# file_url in a JSON body (no actual byte-upload endpoint ever produced one
# for this flow), and there was no client-facing upload route whatsoever. Both
# gaps fixed below using the same private-storage + ownership-checked-download
# pattern already established for career-application resumes
# (app/utils/uploads.py's save_upload/load_private_file, app/routers/career.py).
CLIENT_FILE_SUBFOLDER = "client-files"


# NOTE ON ORDERING: fixed-string routes ("/me/files", "/files/...") MUST be
# declared before the dynamic "/{client_id}/files" route below. FastAPI/
# Starlette matches path patterns in registration order, and "me" is a
# syntactically valid value for {client_id} — declaring the dynamic route
# first previously caused every request to "/clients/me/files" to be
# swallowed by "/{client_id}/files" (client_id="me"), hitting that route's
# staff-only require_roles dependency and 403ing real clients. Caught via
# live UAT (see UAT_REPORT.md), not by the unit tests, since those call the
# handler functions directly and never exercise Starlette's own routing.
@router.post("/me/files", response_model=dict, status_code=201)
async def upload_my_file(
    name: str = Form(...), category: str = Form(...), file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Client -> Company direction: the client uploads their own file."""
    client = await _get_client_for_user(db, current_user)
    reference = await save_upload(file, CLIENT_FILE_SUBFOLDER)
    f = ClientFile(
        client_id=client.id, name=name, category=category, file_url=reference,
        size_bytes=file.size, uploaded_by=current_user.name,
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return success_response(data=ClientFileOut.model_validate(f), message="File uploaded", status_code=201)


@router.get("/files/{file_id}/download")
async def download_client_file(file_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = (await db.execute(select(ClientFile).where(ClientFile.id == file_id))).scalar_one_or_none()
    if record is None:
        raise ApiError.not_found("File not found")
    client = (await db.execute(select(Client).where(Client.id == record.client_id))).scalar_one_or_none()
    is_owner = client is not None and client.user_id == current_user.id
    if not is_owner and current_user.role not in ("admin", "super_admin"):
        if current_user.role == "project_manager":
            await _require_assigned_account_manager(db, current_user, client)
        else:
            raise ApiError.not_found("File not found")
    content, filename, content_type = await load_private_file(record.file_url, CLIENT_FILE_SUBFOLDER)
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{client_id}/files", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "project_manager"))])
async def staff_upload_client_file(
    client_id: uuid.UUID, name: str = Form(...), category: str = Form(...),
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Company -> Client direction: staff attaches a file to a specific client's record."""
    client = await crud.get(db, client_id)
    await _require_assigned_account_manager(db, current_user, client)
    reference = await save_upload(file, CLIENT_FILE_SUBFOLDER)
    f = ClientFile(
        client_id=client_id, name=name, category=category, file_url=reference,
        size_bytes=file.size, uploaded_by=current_user.name,
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return success_response(data=ClientFileOut.model_validate(f), message="File uploaded", status_code=201)


@router.get("/me/reports", response_model=dict)
async def my_reports(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await _get_client_for_user(db, current_user)
    result = await db.execute(
        bounded_select(select(ClientReport).where(ClientReport.client_id == client.id).order_by(ClientReport.created_at.desc()))
    )
    return success_response(data=[ClientReportOut.model_validate(r) for r in result.scalars().all()])


@router.post("/me/reports", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "finance"))])
async def create_client_report(client_id: uuid.UUID, payload: ClientReportCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = await crud.get(db, client_id)
    await _require_assigned_account_manager(db, current_user, client)
    r = ClientReport(**payload.model_dump(), client_id=client_id)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return success_response(data=ClientReportOut.model_validate(r), message="Report created", status_code=201)


# ---------- Admin / Sales management ----------
@router.get("", response_model=dict, dependencies=[Depends(require_roles("admin", "sales", "project_manager", "finance"))])
async def list_clients(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {}
    if industry := request.query_params.get("industry"):
        filters["industry"] = industry
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[ClientOut.model_validate(c) for c in items], message="Clients fetched", meta=meta)


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "sales"))])
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = await crud.create(db, payload.model_dump())
    return success_response(data=ClientOut.model_validate(client), message="Client created successfully", status_code=201)
