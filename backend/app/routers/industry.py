from slugify import slugify

from app.crud.base import CRUDBase
from app.models.industry import Industry
from app.schemas.cms import IndustryCreate, IndustryOut, IndustryUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Industry, searchable_fields=["name"])

router = build_crud_router(
    crud, IndustryCreate, IndustryUpdate, IndustryOut,
    prefix="/industries", tags=["Industries"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["name"])},
)
