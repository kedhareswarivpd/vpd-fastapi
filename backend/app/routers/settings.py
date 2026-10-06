from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.crud.base import CRUDBase
from app.models.setting import Setting
from app.schemas.ops import SettingOut, SettingUpsert
from app.utils.responses import success_response

# System settings are internal configuration, not CMS content — no public_read,
# and looked up by their unique `key` rather than a UUID id (that's how every
# caller actually wants to address a setting: settings.get("site_maintenance_mode"),
# not settings.get(some_uuid)).
router = APIRouter(prefix="/settings", tags=["Settings"], dependencies=[Depends(require_roles("admin", "super_admin"))])

crud = CRUDBase(Setting)


@router.get("", response_model=dict)
async def list_settings(request: Request, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    query = select(Setting)
    if group := request.query_params.get("group"):
        query = query.where(Setting.group == group)
    items = (await db.execute(query)).scalars().all()
    return success_response(data=[SettingOut.model_validate(s) for s in items], message="Settings fetched")


@router.get("/{key}", response_model=dict)
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    from app.core.errors import ApiError

    setting = await crud.get_optional(db, key=key)
    if setting is None:
        raise ApiError.not_found(f"Setting '{key}' not found")
    return success_response(data=SettingOut.model_validate(setting))


@router.put("/{key}", response_model=dict)
async def upsert_setting(key: str, payload: SettingUpsert, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_optional(db, key=key)
    data = payload.model_dump()
    data["key"] = key
    if existing is None:
        setting = await crud.create(db, data)
        return success_response(data=SettingOut.model_validate(setting), message="Setting created", status_code=201)
    setting = await crud.update(db, existing.id, {"value": data["value"], "group": data["group"]})
    return success_response(data=SettingOut.model_validate(setting), message="Setting updated")


@router.delete("/{key}", response_model=dict)
async def delete_setting(key: str, db: AsyncSession = Depends(get_db)):
    from app.core.errors import ApiError

    existing = await crud.get_optional(db, key=key)
    if existing is None:
        raise ApiError.not_found(f"Setting '{key}' not found")
    await crud.delete(db, existing.id)
    return success_response(message="Setting deleted")
