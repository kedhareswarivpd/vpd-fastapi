from slugify import slugify

from app.crud.base import CRUDBase
from app.models.solution import Solution
from app.schemas.solution import SolutionCreate, SolutionOut, SolutionUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Solution, searchable_fields=["name", "overview"])

router = build_crud_router(
    crud, SolutionCreate, SolutionUpdate, SolutionOut,
    prefix="/solutions", tags=["Solutions"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["name"])},
)
