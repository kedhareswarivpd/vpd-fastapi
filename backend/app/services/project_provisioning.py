"""Auto-creates the Project once a proposal is accepted — the workflow
doc's end-to-end diagram says "Client Accepts Proposal -> Project Created"
directly, with no manual step in between. Previously the accept endpoints
(both staff-side app/routers/proposals.py and client-side
app/routers/clients.py) only flipped the proposal's status and notified
staff, leaving actual project creation as a separate manual action.

Shared by both accept paths so the behavior — and its idempotency — is
identical regardless of who accepted the proposal.
"""
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.client import Client
from app.models.enums import NotificationType, ProjectStatus
from app.models.lead import Lead
from app.models.project import Project
from app.models.proposal import Proposal
from app.services.notification_service import notify_roles


async def provision_project_for_accepted_proposal(db: AsyncSession, proposal: Proposal) -> Project | None:
    """Idempotent: if a project already exists for this proposal (unique FK,
    same guard POST /projects itself uses), returns it unchanged rather than
    creating a second one. Returns None if the lead hasn't converted to a
    client yet — callers should treat that as "nothing to do", not an error,
    since a client can accept their own proposal, and by definition on that
    path the lead is always already converted.
    """
    existing = (await db.execute(select(Project).where(Project.proposal_id == proposal.id))).scalar_one_or_none()
    if existing is not None:
        return existing

    lead = (await db.execute(select(Lead).where(Lead.id == proposal.lead_id))).scalar_one_or_none()
    if lead is None or lead.converted_client_id is None:
        logger.warning("Proposal %s accepted but its lead has no converted client — skipping auto project creation", proposal.id)
        return None

    title = f"{lead.company or lead.contact_name} — {proposal.scope_summary[:80]}"
    slug = f"{slugify(title)}-{str(proposal.id)[:8]}"

    project = Project(
        title=title,
        slug=slug,
        client_id=lead.converted_client_id,
        proposal_id=proposal.id,
        overview=proposal.scope_summary,
        budget=proposal.price,
        service_id=proposal.service_id,
        industry_id=lead.industry_id,
        status=ProjectStatus.planning,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    try:
        client = (await db.execute(select(Client).where(Client.id == lead.converted_client_id))).scalar_one_or_none()
        client_name = (client.company_name if client else None) or lead.company or lead.contact_name
        details = (
            f"'{title}' was auto-created from accepted proposal v{proposal.version}.\n"
            f"Client: {client_name} ({lead.email})\n"
            f"Budget: {proposal.currency} {float(proposal.price):,.2f}\n"
            f"Scope: {proposal.scope_summary[:200]}"
        )
        # admin and project_manager land on different portals — each needs
        # its own deep link (a PM hitting /admin-panel is role-gated out).
        await notify_roles(
            db, ["admin"], "New project created from an accepted proposal", details,
            NotificationType.success, f"/admin-panel?tab=projects&project={project.id}",
        )
        await notify_roles(
            db, ["project_manager"], "New project needs a PM assigned", details,
            NotificationType.success, f"/project-manager?tab=projects&project={project.id}",
        )
    except Exception as exc:  # noqa: BLE001 — the project itself is already committed; a notify failure must not undo it
        logger.warning("Failed to notify staff of auto-created project %s: %s", project.id, exc)

    return project
