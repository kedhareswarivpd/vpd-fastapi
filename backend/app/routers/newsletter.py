from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.limiter import limiter
from app.crud.base import CRUDBase
from app.models.newsletter import NewsletterSubscriber
from app.schemas.newsletter import NewsletterOut, NewsletterSubscribe
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])

crud = CRUDBase(NewsletterSubscriber, searchable_fields=["email", "name"])


@router.post("/subscribe", response_model=dict, status_code=201)
@limiter.limit("5/minute")
async def subscribe(request: Request, payload: NewsletterSubscribe, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_optional(db, email=payload.email)
    if existing:
        if not existing.is_active:
            existing = await crud.update(db, existing.id, {"is_active": True, "unsubscribed_at": None})
        return success_response(data=NewsletterOut.model_validate(existing), message="You're already subscribed")

    subscriber = await crud.create(db, payload.model_dump())
    return success_response(data=NewsletterOut.model_validate(subscriber), message="Subscribed successfully", status_code=201)


@router.post("/unsubscribe", response_model=dict)
@limiter.limit("5/minute")
async def unsubscribe(request: Request, payload: NewsletterSubscribe, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_optional(db, email=payload.email)
    if existing and existing.is_active:
        await crud.update(db, existing.id, {"is_active": False, "unsubscribed_at": datetime.now(UTC)})
    return success_response(message="You have been unsubscribed")


@router.get("", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def list_subscribers(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("is_active",) if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[NewsletterOut.model_validate(s) for s in items], message="Subscribers fetched", meta=meta)
