import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.errors import ApiError
from app.models.client import Client
from app.models.user import User
from app.utils.responses import success_response

router = APIRouter(prefix="/users", tags=["GDPR"])


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _str(value) -> str | None:
    return str(value) if value else None


def _profile_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "avatar": user.avatar,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
        "updated_at": _iso(user.updated_at),
    }


def _employee_payload(emp) -> dict | None:
    if emp is None:
        return None
    return {
        "employee_code": emp.employee_code,
        "department_id": _str(emp.department_id),
        "designation": emp.designation,
        "status": emp.status.value if emp.status else None,
        "employment_type": emp.employment_type.value if emp.employment_type else None,
        "date_of_joining": _iso(emp.date_of_joining),
        "office_location": emp.office_location,
        "reporting_manager_id": _str(emp.reporting_manager_id),
    }


def _client_payload(cli) -> dict | None:
    if cli is None:
        return None
    return {
        "company_name": cli.company_name,
        "industry": cli.industry,
        "country": cli.country,
        "website": cli.website,
    }


def _projects_payload(projects) -> list[dict] | None:
    if not projects:
        return None
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "status": p.status.value if p.status else None,
            "start_date": _iso(p.start_date),
            "end_date": _iso(p.end_date),
        }
        for p in projects
    ]


def _invoices_payload(invoices) -> list[dict] | None:
    if not invoices:
        return None
    return [
        {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "amount": float(inv.amount),
            "total_amount": float(inv.total_amount),
            "currency": inv.currency,
            "status": inv.status.value if inv.status else None,
            "issue_date": _iso(inv.issue_date),
            "due_date": _iso(inv.due_date),
        }
        for inv in invoices
    ]


def _tickets_payload(tickets) -> list[dict] | None:
    if not tickets:
        return None
    return [
        {
            "id": str(t.id),
            "ticket_number": t.ticket_number,
            "subject": t.subject,
            "priority": t.priority.value if t.priority else None,
            "status": t.status.value if t.status else None,
        }
        for t in tickets
    ]


def _testimonials_payload(testimonials) -> list[dict] | None:
    if not testimonials:
        return None
    return [
        {
            "id": str(t.id),
            "content": t.content if hasattr(t, "content") else None,
        }
        for t in testimonials
    ]


def _notifications_payload(notifications) -> list[dict] | None:
    if not notifications:
        return None
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "type": n.type.value if n.type else None,
            "is_read": n.is_read,
            "created_at": _iso(n.created_at),
        }
        for n in notifications
    ]


def _audit_logs_payload(audit_logs) -> list[dict] | None:
    if not audit_logs:
        return None
    return [
        {
            "id": str(a.id),
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": _str(a.entity_id),
            "created_at": _iso(a.created_at),
        }
        for a in audit_logs
    ]


async def _export_user_data(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.employee_profile),
            selectinload(User.client_profile).selectinload(Client.projects),
            selectinload(User.client_profile).selectinload(Client.invoices),
            selectinload(User.client_profile).selectinload(Client.tickets),
            selectinload(User.client_profile).selectinload(Client.testimonials),
            selectinload(User.notifications),
            selectinload(User.audit_logs),
        )
    )
    user = result.scalar_one()
    cli = user.client_profile

    return {
        "profile": _profile_payload(user),
        "employee_profile": _employee_payload(user.employee_profile),
        "client_profile": _client_payload(cli),
        "projects": _projects_payload(cli.projects if cli else None),
        "invoices": _invoices_payload(cli.invoices if cli else None),
        "tickets": _tickets_payload(cli.tickets if cli else None),
        "testimonials": _testimonials_payload(cli.testimonials if cli else None),
        "notifications": _notifications_payload(user.notifications),
        "audit_logs": _audit_logs_payload(user.audit_logs),
    }


async def _anonymize_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError.not_found("User not found")
    uuid_str = str(uuid.uuid4())
    user.name = "Deleted User"
    user.email = f"deleted-{uuid_str}@vpdtechnologies.com"
    user.phone = None
    user.avatar = None
    user.is_active = False
    await db.commit()


# ---------- Super Admin: act on behalf of another user (GDPR requests) ----------
@router.get("/{user_id}/export", response_model=dict, dependencies=[Depends(require_roles("super_admin"))])
async def export_user_data(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    data = await _export_user_data(db, user_id)
    return success_response(data=data, message="User data exported")


@router.post("/{user_id}/anonymize", response_model=dict, dependencies=[Depends(require_roles("super_admin"))])
async def anonymize_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _anonymize_user(db, user_id)
    return success_response(message="User data has been anonymized")
