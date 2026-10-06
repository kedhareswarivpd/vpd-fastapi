from slugify import slugify

from app.crud.base import CRUDBase
from app.models.category import Category
from app.schemas.cms import CategoryCreate, CategoryOut, CategoryUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Category, searchable_fields=["name"])

router = build_crud_router(
    crud, CategoryCreate, CategoryUpdate, CategoryOut,
    prefix="/categories", tags=["Categories"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["type"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["name"])},
)
