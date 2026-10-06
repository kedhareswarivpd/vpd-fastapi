import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.models.notification import Notification
from app.models.user import User
from app.schemas.ops import NotificationCreate, NotificationOut
from app.services.notification_service import notify_roles, notify_user
from app.utils.pagination import bounded_select
from app.utils.responses import success_response

router = APIRouter(prefix="/notifications", tags=["Notifications"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=dict)
async def list_notifications(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        bounded_select(select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()), cap=50)
    )
    return success_response(data=[NotificationOut.model_validate(n) for n in result.scalars().all()])


@router.patch("/read-all", response_model=dict)
async def mark_all_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(
        sa_update(Notification).where(Notification.user_id == current_user.id, Notification.is_read.is_(False)).values(is_read=True)
    )
    await db.commit()
    return success_response(message="All notifications marked as read")


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_read(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(
        sa_update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await db.commit()
    return success_response(message="Marked as read")


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr", "marketing"))])
async def create_notification(payload: NotificationCreate, db: AsyncSession = Depends(get_db)):
    if not payload.user_id and not payload.roles:
        raise ApiError.bad_request("Provide either user_id or roles to target this notification")
    if payload.user_id:
        await notify_user(db, payload.user_id, payload.title, payload.message, payload.type, payload.link)
    if payload.roles:
        await notify_roles(db, payload.roles, payload.title, payload.message, payload.type, payload.link)
    return success_response(message="Notification sent", status_code=201)
