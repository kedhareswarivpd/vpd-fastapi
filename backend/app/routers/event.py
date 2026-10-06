from slugify import slugify

from app.crud.base import CRUDBase
from app.models.event import Event
from app.schemas.cms import EventCreate, EventOut, EventUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Event, searchable_fields=["title", "location"])

router = build_crud_router(
    crud, EventCreate, EventUpdate, EventOut,
    prefix="/events", tags=["Events"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_virtual", "is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["title"])},
)
