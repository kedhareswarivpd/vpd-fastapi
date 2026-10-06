from app.crud.base import CRUDBase
from app.models.announcement import Announcement
from app.schemas.cms import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Announcement, searchable_fields=["title", "body"])

router = build_crud_router(
    crud, AnnouncementCreate, AnnouncementUpdate, AnnouncementOut,
    prefix="/announcements", tags=["Announcements"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
)
