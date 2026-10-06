from slugify import slugify

from app.crud.base import CRUDBase
from app.models.portfolio import Portfolio
from app.schemas.cms import PortfolioCreate, PortfolioOut, PortfolioUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Portfolio, searchable_fields=["title", "category"])

router = build_crud_router(
    crud, PortfolioCreate, PortfolioUpdate, PortfolioOut,
    prefix="/portfolio", tags=["Portfolio"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["category", "is_featured"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["title"])},
)
