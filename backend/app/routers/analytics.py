from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_client_ip, require_roles
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.core.logger import logger
from app.models.analytics import PageView
from app.schemas.analytics import AnalyticsSummary, PageViewCreate, PageViewStats
from app.utils.responses import success_response

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/track")
@limiter.limit("60/minute")
async def track_page_view(payload: PageViewCreate, request: Request, db: AsyncSession = Depends(get_db)):
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    view = PageView(
        path=payload.path,
        ip_address=payload.ip_address or ip,
        user_agent=payload.user_agent or ua,
        referrer=payload.referrer or referrer,
        country=payload.country,
    )
    db.add(view)
    try:
        await db.commit()
    except Exception as exc:
        # The only handler in this router that still needs a try/except: a
        # raw db.add()/commit() (not going through CRUDBase, which already
        # rolls back on failure) must roll back its own session on error or
        # the session is left unusable for the rest of the request.
        await db.rollback()
        logger.exception("Failed to record page view")
        raise ApiError.internal("Failed to record page view") from exc
    return success_response(data={"id": view.id}, message="Page view recorded")


@router.get("/summary", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    total_views = (await db.execute(select(func.count(PageView.id)))).scalar_one()
    unique_paths = (await db.execute(select(func.count(func.distinct(PageView.path))))).scalar_one()
    top_pages_result = await db.execute(
        select(PageView.path, func.count(PageView.id).label("count"))
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(20)
    )
    top_pages = [PageViewStats(path=row.path, count=row.count) for row in top_pages_result.all()]

    stats = AnalyticsSummary(total_views=total_views, unique_paths=unique_paths, top_pages=top_pages)
    return success_response(data=stats, message="Analytics summary fetched")
