from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.crud.base import CRUDBase
from app.models.setting import Setting
from app.schemas.site_content import SiteContentUpsert
from app.utils.responses import success_response

# Two singleton "settings-style" content blobs — company profile (name,
# tagline, contact/HQ info — Footer.jsx) and about-page content (mission,
# core values, timeline, certifications — the About page sections). Both
# reuse the existing generic `Setting` model (key/value JSONB) rather than
# adding new single-row tables, since Setting's shape already fits this
# perfectly. This router only exposes these two specific keys though —
# unlike /settings (admin-only, used for internal app config), these are
# public-facing CMS content the website needs to render for anonymous
# visitors, so GET is public while PUT stays admin-gated.
router = APIRouter(prefix="/site-content", tags=["Site Content"])

crud = CRUDBase(Setting)

_KEYS = {
    "company-info": ("company_info", "company"),
    "about-content": ("about_content", "about"),
}


async def _get_value(db: AsyncSession, key: str):
    setting = await crud.get_optional(db, key=key)
    return setting.value if setting else None


async def _upsert(db: AsyncSession, key: str, group: str, value):
    existing = await crud.get_optional(db, key=key)
    if existing is None:
        setting = await crud.create(db, {"key": key, "value": value, "group": group})
    else:
        setting = await crud.update(db, existing.id, {"value": value})
    return setting.value


@router.get("/company-info", response_model=dict)
async def get_company_info(db: AsyncSession = Depends(get_db)):
    key, _ = _KEYS["company-info"]
    return success_response(data=await _get_value(db, key), message="Company info fetched")


@router.put("/company-info", dependencies=[Depends(require_roles("admin", "super_admin"))], response_model=dict)
async def update_company_info(payload: SiteContentUpsert, db: AsyncSession = Depends(get_db)):
    key, group = _KEYS["company-info"]
    value = await _upsert(db, key, group, payload.value)
    return success_response(data=value, message="Company info updated")


@router.get("/about-content", response_model=dict)
async def get_about_content(db: AsyncSession = Depends(get_db)):
    key, _ = _KEYS["about-content"]
    return success_response(data=await _get_value(db, key), message="About content fetched")


@router.put("/about-content", dependencies=[Depends(require_roles("admin", "super_admin"))], response_model=dict)
async def update_about_content(payload: SiteContentUpsert, db: AsyncSession = Depends(get_db)):
    key, group = _KEYS["about-content"]
    value = await _upsert(db, key, group, payload.value)
    return success_response(data=value, message="About content updated")
