import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.core.password import hash_password
from app.crud.base import CRUDBase
from app.models.employee import Employee
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth_service import revoke_all_sessions
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

EMPLOYEE_ROLES = {"employee", "developer", "sales", "marketing", "project_manager", "qa", "support", "finance", "hr", "admin", "super_admin"}

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(require_roles("admin", "hr"))])

crud = CRUDBase(User, searchable_fields=["name", "email"])


@router.get("", response_model=dict)
async def list_users(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {}
    if role := request.query_params.get("role"):
        filters["role"] = role
    if is_active := request.query_params.get("is_active"):
        filters["is_active"] = is_active.lower() == "true"
    items, total = await crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[UserOut.model_validate(u) for u in items], message="Users fetched", meta=meta)


@router.get("/{user_id}", response_model=dict)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await crud.get(db, user_id)
    return success_response(data=UserOut.model_validate(user))


@router.post("", response_model=dict, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Creates the local account directly — CoreFusion owns identity end to
    end, there is no external auth provider to also register with.

    Only a Super Admin may grant `admin`/`super_admin` — an Admin or HR caller
    (both allowed through this router by `require_roles`) can provision every
    other role but cannot mint another admin account for themselves or anyone else.
    """
    if payload.role in ("admin", "super_admin") and current_user.role != "super_admin":
        raise ApiError.forbidden("Only a Super Admin can create an Admin or Super Admin account")

    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise ApiError.conflict("An account with this email already exists")

    data = payload.model_dump(exclude={"password"})
    data["id"] = uuid.uuid4()
    data["password_hash"] = hash_password(payload.password)
    # An admin-provisioned account is pre-verified — the person didn't sign
    # themselves up through a link they'd need to click to prove ownership.
    data["is_email_verified"] = True
    user = await crud.create(db, data)

    if payload.role in EMPLOYEE_ROLES:
        existing_employee = (await db.execute(select(Employee).where(Employee.user_id == user.id))).scalar_one_or_none()
        if not existing_employee:
            # Generate a unique employee code from the user id
            short_id = str(user.id).replace("-", "")[:8].upper()
            employee_code = f"EMP-{short_id}"
            employee = Employee(user_id=user.id, employee_code=employee_code)
            db.add(employee)
            await db.commit()

    return success_response(data=UserOut.model_validate(user), message="User created successfully", status_code=201)


@router.put("/{user_id}", response_model=dict)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a user.

    Mirrors the `create_user` role restriction: only a Super Admin may grant
    `admin`/`super_admin`, preventing an Admin or HR caller from escalating
    their own (or anyone else's) privileges.
    """
    if payload.role in ("admin", "super_admin") and current_user.role != "super_admin":
        raise ApiError.forbidden("Only a Super Admin can grant Admin or Super Admin roles")
    # A real gap found during a security audit: the check above only
    # blocked *granting* admin/super_admin — it never checked whether the
    # TARGET already held one of those roles, so an HR caller (who cannot
    # create or promote an admin) could still edit an existing admin's
    # other fields, including flipping `is_active` to False via this same
    # endpoint (UserUpdate exposes is_active). Consistent with "only a
    # Super Admin manages admin/super_admin accounts," this now blocks any
    # modification to an existing admin/super_admin target by a non-Super-Admin.
    target = await crud.get(db, user_id)
    if target.role in ("admin", "super_admin") and current_user.role != "super_admin":
        raise ApiError.forbidden("Only a Super Admin can modify an Admin or Super Admin account")
    user = await crud.update(db, user_id, payload.model_dump(exclude_unset=True))
    return success_response(data=UserOut.model_validate(user), message="User updated successfully")


@router.patch("/{user_id}/deactivate", response_model=dict)
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deactivates the profile and revokes every active session — `is_active`
    is checked on every authenticated request (core/dependencies.py), and a
    revoked/expired session can't be silently kept alive by an already-issued
    access token, so both the current session and any future login attempt
    are blocked immediately.

    Same real gap fixed as update_user above, applied here too: this
    endpoint had zero role-hierarchy check, letting an HR caller (barred
    from creating/promoting admins) neutralize an existing admin/super_admin
    account outright."""
    target = await crud.get(db, user_id)
    if target.role in ("admin", "super_admin") and current_user.role != "super_admin":
        raise ApiError.forbidden("Only a Super Admin can deactivate an Admin or Super Admin account")
    user = await crud.update(db, user_id, {"is_active": False})
    await revoke_all_sessions(db, user_id)
    return success_response(data=UserOut.model_validate(user), message="User deactivated")


@router.delete("/{user_id}", response_model=dict, dependencies=[Depends(require_roles("admin"))])
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await crud.delete(db, user_id)
    return success_response(message="User deleted successfully")
