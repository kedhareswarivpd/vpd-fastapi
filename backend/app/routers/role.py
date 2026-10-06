from fastapi import APIRouter, Depends

from app.core.dependencies import require_roles
from app.crud.base import CRUDBase
from app.models.permission import Permission
from app.models.role import Role
from app.schemas.role import PermissionCreate, PermissionOut, PermissionUpdate, RoleCreate, RoleOut, RoleUpdate
from app.utils.router_factory import build_crud_router

router = APIRouter(prefix="/access-control", dependencies=[Depends(require_roles("admin"))])

role_crud = CRUDBase(Role, searchable_fields=["name"], relationships=["permissions"])
permission_crud = CRUDBase(Permission, searchable_fields=["name", "module"])

role_router = build_crud_router(
    role_crud, RoleCreate, RoleUpdate, RoleOut,
    prefix="/roles", tags=["Roles"], write_roles=["admin"],
)
permission_router = build_crud_router(
    permission_crud, PermissionCreate, PermissionUpdate, PermissionOut,
    prefix="/permissions", tags=["Permissions"], write_roles=["admin"],
    allowed_filters=["module"],
)

router.include_router(role_router)
router.include_router(permission_router)
