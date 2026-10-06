from app.crud.base import CRUDBase
from app.models.award import Award
from app.schemas.cms import AwardCreate, AwardOut, AwardUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Award, searchable_fields=["title", "issued_by"])

router = build_crud_router(
    crud, AwardCreate, AwardUpdate, AwardOut,
    prefix="/awards", tags=["Awards"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["year", "is_published"],
)
