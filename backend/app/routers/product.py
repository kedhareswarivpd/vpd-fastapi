from slugify import slugify

from app.crud.base import CRUDBase
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Product, searchable_fields=["name", "tagline"])

router = build_crud_router(
    crud, ProductCreate, ProductUpdate, ProductOut,
    prefix="/products", tags=["Products"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["name"])},
)
