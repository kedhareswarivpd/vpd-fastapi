import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.crud.base import CRUDBase
from app.models.media import Media
from app.models.user import User
from app.schemas.ops import MediaOut
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response
from app.utils.uploads import save_upload

router = APIRouter(prefix="/media", tags=["Media"], dependencies=[Depends(require_roles("admin", "marketing", "hr"))])

crud = CRUDBase(Media)


@router.get("", response_model=dict)
async def list_media(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("folder", "mime_type") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[MediaOut.model_validate(m) for m in items], message="Media fetched", meta=meta)


@router.post("/upload", response_model=dict, status_code=201)
async def upload_files(
    files: list[UploadFile] = File(...),
    folder: str = Form("misc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = []
    for f in files:
        url = await save_upload(f, folder)
        media = Media(file_name=f.filename, url=url, mime_type=f.content_type, size_bytes=f.size, uploaded_by=current_user.id, folder=folder)
        db.add(media)
        records.append(media)
    await db.commit()
    for m in records:
        await db.refresh(m)
    return success_response(data=[MediaOut.model_validate(m) for m in records], message="Files uploaded successfully", status_code=201)


@router.delete("/{media_id}", response_model=dict)
async def delete_media(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await crud.delete(db, media_id)
    return success_response(message="Media deleted")
