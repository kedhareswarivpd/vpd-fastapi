
from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole
from app.schemas.common import TimestampedRead


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.guest
    phone: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    avatar: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserOut(TimestampedRead):
    name: str
    email: EmailStr
    phone: str | None = None
    avatar: str | None = None
    role: UserRole
    is_active: bool
    is_email_verified: bool
