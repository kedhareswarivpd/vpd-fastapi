import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_optional_user, is_staff, require_roles
from app.core.limiter import limiter
from app.crud.base import CRUDBase
from app.models.comment import Comment
from app.models.enums import CommentStatus
from app.models.user import User
from app.schemas.blog import CommentCreate, CommentModerate, CommentOut
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/comments", tags=["Blog Comments"])

crud = CRUDBase(Comment)


@router.get("", response_model=dict)
async def list_comments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(page_params),
    current_user: User | None = Depends(get_optional_user),
):
    """Public callers only ever see approved comments; staff (admin/marketing)
    can pass `status=pending`/`spam` to moderate."""
    filters = {}
    if blog_id := request.query_params.get("blog_id"):
        filters["blog_id"] = blog_id
    if is_staff(current_user, "admin", "super_admin", "marketing"):
        if status := request.query_params.get("status"):
            filters["status"] = status
    else:
        filters["status"] = CommentStatus.approved.value
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[CommentOut.model_validate(c) for c in items], message="Comments fetched", meta=meta)


@router.post("", response_model=dict, status_code=201)
@limiter.limit("5/minute")
async def create_comment(request: Request, payload: CommentCreate, db: AsyncSession = Depends(get_db)):
    comment = await crud.create(db, payload.model_dump())
    return success_response(
        data=CommentOut.model_validate(comment),
        message="Comment submitted — it will appear once approved",
        status_code=201,
    )


@router.patch("/{comment_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def moderate_comment(comment_id: uuid.UUID, payload: CommentModerate, db: AsyncSession = Depends(get_db)):
    comment = await crud.update(db, comment_id, {"status": payload.status})
    return success_response(data=CommentOut.model_validate(comment), message="Comment status updated")


@router.delete("/{comment_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def delete_comment(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await crud.delete(db, comment_id)
    return success_response(message="Comment deleted")
