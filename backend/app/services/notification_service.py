import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.user import User


async def notify_user(db: AsyncSession, user_id: uuid.UUID, title: str, message: str | None = None, type: NotificationType = NotificationType.info, link: str | None = None) -> None:
    db.add(Notification(user_id=user_id, title=title, message=message, type=type, link=link))
    await db.commit()


async def notify_roles(db: AsyncSession, roles: list[str], title: str, message: str | None = None, type: NotificationType = NotificationType.info, link: str | None = None) -> None:
    """Fan a notification out to every active user holding one of the given roles."""
    result = await db.execute(select(User.id).where(User.role.in_(roles), User.is_active.is_(True)))
    user_ids = result.scalars().all()
    for user_id in user_ids:
        db.add(Notification(user_id=user_id, title=title, message=message, type=type, link=link))
    if user_ids:
        await db.commit()
