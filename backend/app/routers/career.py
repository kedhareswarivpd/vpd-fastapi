import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import EmailStr
from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.crud.base import CRUDBase
from app.models.application import Application
from app.models.career import Career
from app.schemas.career import (
    ApplicationOut,
    ApplicationStatusUpdate,
    CareerCreate,
    CareerOut,
)
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response
from app.utils.uploads import load_private_file, save_upload

router = APIRouter(prefix="/careers", tags=["Careers"])

career_crud = CRUDBase(Career, searchable_fields=["title", "location", "department"])
application_crud = CRUDBase(Application, searchable_fields=["full_name", "email"])


# ---------- Public ----------
@router.get("", response_model=dict)
async def list_open_positions(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("department", "location", "employment_type") if request.query_params.get(k)}
    filters["status"] = "open"
    items, total = await career_crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[CareerOut.model_validate(c) for c in items], message="Open positions fetched", meta=meta)


@router.post("/{career_id}/apply", response_model=dict, status_code=201)
@limiter.limit("5/hour")
async def apply(
    request: Request,
    career_id: uuid.UUID,
    full_name: str = Form(...),
    email: EmailStr = Form(...),
    phone: str | None = Form(None),
    cover_letter: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    career = await career_crud.get(db, career_id)
    if career.status != "open":
        raise ApiError.bad_request("This position is not currently accepting applications")

    resume_url = await save_upload(resume, "careers")
    application = Application(
        career_id=career.id,
        full_name=full_name,
        email=email,
        phone=phone,
        cover_letter=cover_letter,
        linkedin_url=linkedin_url,
        resume_url=resume_url,
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return success_response(data=ApplicationOut.model_validate(application), message="Application submitted successfully", status_code=201)


# ---------- HR / Admin ----------
@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr"))])
async def create_position(payload: CareerCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = data.get("slug") or slugify(data["title"])
    career = await career_crud.create(db, data)
    return success_response(data=CareerOut.model_validate(career), message="Job posting created", status_code=201)


@router.get("/admin/applications", response_model=dict, dependencies=[Depends(require_roles("admin", "hr"))])
async def list_applications(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("career_id", "status") if request.query_params.get(k)}
    items, total = await application_crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[ApplicationOut.model_validate(a) for a in items], message="Applications fetched", meta=meta)


@router.patch("/admin/applications/{application_id}/status", response_model=dict, dependencies=[Depends(require_roles("admin", "hr"))])
async def update_application_status(application_id: uuid.UUID, payload: ApplicationStatusUpdate, db: AsyncSession = Depends(get_db)):
    application = await application_crud.update(db, application_id, payload.model_dump())
    return success_response(data=ApplicationOut.model_validate(application), message="Application status updated")


@router.get("/admin/applications/{application_id}/resume", dependencies=[Depends(require_roles("admin", "hr"))])
async def download_resume(application_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from fastapi import Response

    application = await application_crud.get(db, application_id)
    content, filename, content_type = await load_private_file(application.resume_url, "careers")
    return Response(
        content=content, media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
