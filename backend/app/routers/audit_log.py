from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.crud.base import CRUDBase
from app.models.audit_log import AuditLog
from app.schemas.ops import AuditLogOut
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"], dependencies=[Depends(require_roles("admin"))])

crud = CRUDBase(AuditLog)


@router.get("", response_model=dict)
async def list_audit_logs(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("user_id", "action", "entity_type") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[AuditLogOut.model_validate(a) for a in items], message="Audit logs fetched", meta=meta)
