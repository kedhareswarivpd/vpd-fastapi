"""Enforces the Lead pipeline as a one-way state machine driven entirely by
the actions that produce evidence of progress (call logged, requirement
gathering, proposal created/sent/approved, client converted) — there is no
UI control that lets staff freely pick an arbitrary status any more.

Forward order: new -> contacted -> requirement_gathering -> proposal_created
-> proposal_sent -> proposal_approved -> converted, with `disqualified`
reachable as a terminal "closed lost" branch from any non-terminal stage.
Both `converted` and `disqualified` are terminal — nothing advances past them.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.lead_activity import LeadActivity

PIPELINE_ORDER = [
    LeadStatus.new,
    LeadStatus.contacted,
    LeadStatus.requirement_gathering,
    LeadStatus.proposal_created,
    LeadStatus.proposal_sent,
    LeadStatus.proposal_approved,
    LeadStatus.converted,
]
TERMINAL_STATUSES = {LeadStatus.converted, LeadStatus.disqualified}


def can_advance_to(current: LeadStatus, target: LeadStatus) -> bool:
    if current in TERMINAL_STATUSES:
        return False
    if target == LeadStatus.disqualified:
        return True
    if target not in PIPELINE_ORDER or current not in PIPELINE_ORDER:
        return False
    return PIPELINE_ORDER.index(target) > PIPELINE_ORDER.index(current)


async def advance_lead_status(db: AsyncSession, lead: Lead, target: LeadStatus) -> None:
    """No-op (not an error) when the lead is already at or past `target` —
    callers fire this as a side effect of an idempotent action (e.g. logging
    a second call after the proposal already went out must not regress or
    reject the status), so only a genuine forward move actually writes."""
    if can_advance_to(lead.status, target):
        lead.status = target
        await db.commit()
        await db.refresh(lead)


async def log_lead_activity(
    db: AsyncSession, lead_id: uuid.UUID, activity_type: str, description: str | None = None, actor_id: uuid.UUID | None = None,
) -> None:
    db.add(LeadActivity(lead_id=lead_id, activity_type=activity_type, description=description, actor_id=actor_id))
    await db.commit()
