import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user, is_staff, require_roles
from app.crud.base import CRUDBase
from app.models.blog import Blog
from app.models.user import User
from app.schemas.blog import BlogCreate, BlogOut, BlogUpdate
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/blogs", tags=["Blog"])

crud = CRUDBase(Blog, searchable_fields=["title", "excerpt", "content"], relationships=["author", "category"])


def _enrich_blog(blog: Blog) -> dict:
    data = BlogOut.model_validate(blog).model_dump()
    if blog.author:
        data["author_name"] = blog.author.name
        data["author_role"] = getattr(blog.author, "role", None)
    if blog.category:
        data["category_name"] = blog.category.name
    return data


@router.get("", response_model=dict)
async def list_blogs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(page_params),
    current_user: User | None = Depends(get_optional_user),
):
    filters = {k: request.query_params.get(k) for k in ("category_id", "author_id", "status") if request.query_params.get(k)}
    if not is_staff(current_user, "admin", "super_admin", "marketing"):
        filters["status"] = "published"

    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[_enrich_blog(b) for b in items], message="Blogs fetched", meta=meta)


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "marketing"))])
async def create_blog(payload: BlogCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    data = payload.model_dump()
    data["slug"] = data.get("slug") or slugify(data["title"])
    data["author_id"] = current_user.id
    data["published_at"] = datetime.now(UTC) if data.get("status") == "published" else None
    blog = await crud.create(db, data)
    return success_response(data=BlogOut.model_validate(blog), message="Blog created successfully", status_code=201)


@router.put("/{blog_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def update_blog(blog_id: uuid.UUID, payload: BlogUpdate, db: AsyncSession = Depends(get_db)):
    blog = await crud.update(db, blog_id, payload.model_dump(exclude_unset=True))
    return success_response(data=BlogOut.model_validate(blog), message="Blog updated successfully")


@router.delete("/{blog_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "marketing"))])
async def delete_blog(blog_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await crud.delete(db, blog_id)
    return success_response(message="Blog deleted successfully")
