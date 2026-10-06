from app.crud.base import CRUDBase
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Department, searchable_fields=["name"])

router = build_crud_router(
    crud, DepartmentCreate, DepartmentUpdate, DepartmentOut,
    prefix="/departments", tags=["Departments"],
    public_read=False, write_roles=["super_admin"],
)
