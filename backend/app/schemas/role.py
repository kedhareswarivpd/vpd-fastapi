from pydantic import BaseModel

from app.schemas.common import TimestampedRead


class RoleCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleOut(TimestampedRead):
    name: str
    slug: str
    description: str | None = None
    is_system: bool


class PermissionCreate(BaseModel):
    name: str
    module: str
    action: str
    description: str | None = None


class PermissionUpdate(BaseModel):
    module: str | None = None
    action: str | None = None
    description: str | None = None


class PermissionOut(TimestampedRead):
    name: str
    module: str
    action: str
    description: str | None = None
