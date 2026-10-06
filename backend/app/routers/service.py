from slugify import slugify

from app.crud.base import CRUDBase
from app.models.service import Service
from app.schemas.cms import ServiceCreate, ServiceOut, ServiceUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Service, searchable_fields=["name", "overview"])

router = build_crud_router(
    crud, ServiceCreate, ServiceUpdate, ServiceOut,
    prefix="/services", tags=["Services"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["name"])},
)
