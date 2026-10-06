from slugify import slugify

from app.crud.base import CRUDBase
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceOut, ResourceUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Resource, searchable_fields=["title", "description"])

router = build_crud_router(
    crud, ResourceCreate, ResourceUpdate, ResourceOut,
    prefix="/resources", tags=["Resources"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["resource_type", "is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["title"])},
)
