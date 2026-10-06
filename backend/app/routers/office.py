from app.crud.base import CRUDBase
from app.models.office import Office
from app.schemas.cms import OfficeCreate, OfficeOut, OfficeUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Office, searchable_fields=["city", "country"])

router = build_crud_router(
    crud, OfficeCreate, OfficeUpdate, OfficeOut,
    prefix="/offices", tags=["Offices"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["is_published", "is_headquarters"],
)
