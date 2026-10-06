import uuid

from app.core.database import AsyncSessionLocal
from app.models.audit_log import AuditLog


async def log_audit(
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    log_metadata: dict | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
            log_metadata=log_metadata or {},
        )
        db.add(entry)
        await db.commit()
