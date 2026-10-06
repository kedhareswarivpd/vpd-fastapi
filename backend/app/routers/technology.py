from app.crud.base import CRUDBase
from app.models.technology import Technology
from app.schemas.cms import TechnologyCreate, TechnologyOut, TechnologyUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Technology, searchable_fields=["name"])

router = build_crud_router(
    crud, TechnologyCreate, TechnologyUpdate, TechnologyOut,
    prefix="/technologies", tags=["Technologies"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["category"],
)
