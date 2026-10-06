from app.crud.base import CRUDBase
from app.models.leadership import Leadership
from app.schemas.cms import LeadershipCreate, LeadershipOut, LeadershipUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Leadership, searchable_fields=["name", "title"])

router = build_crud_router(
    crud, LeadershipCreate, LeadershipUpdate, LeadershipOut,
    prefix="/leadership", tags=["Leadership"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published"],
)
