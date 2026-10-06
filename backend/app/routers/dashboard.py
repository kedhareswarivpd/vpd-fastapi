from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.application import Application
from app.models.blog import Blog
from app.models.client import Client
from app.models.contact_submission import ContactSubmission
from app.models.employee import Employee
from app.models.payment import Payment
from app.models.project import Project
from app.models.task import Task
from app.models.ticket import Ticket
from app.utils.responses import success_response

router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"],
    dependencies=[Depends(require_roles("admin", "project_manager", "finance", "sales"))],
)


@router.get("/overview", response_model=dict)
async def overview(db: AsyncSession = Depends(get_db)):
    async def count(query):
        return (await db.execute(query)).scalar_one()

    total_employees = await count(select(func.count()).select_from(Employee).where(Employee.status == "active"))
    total_clients = await count(select(func.count()).select_from(Client))
    total_projects = await count(select(func.count()).select_from(Project))
    active_projects = await count(select(func.count()).select_from(Project).where(Project.status == "in_progress"))
    open_tasks = await count(select(func.count()).select_from(Task).where(Task.status != "done"))
    total_revenue = (await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed"))).scalar_one()
    open_tickets = await count(select(func.count()).select_from(Ticket).where(Ticket.status.in_(["open", "in_progress"])))
    new_applications = await count(select(func.count()).select_from(Application).where(Application.status == "applied"))
    unresolved_contacts = await count(select(func.count()).select_from(ContactSubmission).where(ContactSubmission.status == "new"))
    published_blogs = await count(select(func.count()).select_from(Blog).where(Blog.status == "published"))

    return success_response(
        data={
            "total_employees": total_employees,
            "total_clients": total_clients,
            "total_projects": total_projects,
            "active_projects": active_projects,
            "open_tasks": open_tasks,
            "total_revenue": float(total_revenue or 0),
            "open_tickets": open_tickets,
            "new_applications": new_applications,
            "unresolved_contacts": unresolved_contacts,
            "published_blogs": published_blogs,
        },
        message="Dashboard overview fetched",
    )


@router.get("/projects/status-breakdown", response_model=dict)
async def project_status_breakdown(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project.status, func.count(Project.id)).group_by(Project.status))
    data = [{"status": status, "count": cnt} for status, cnt in result.all()]
    return success_response(data=data)
