import uuid

from pydantic import BaseModel

from app.schemas.common import TimestampedRead


class DepartmentCreate(BaseModel):
    name: str
    description: str | None = None
    head_employee_id: uuid.UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    head_employee_id: uuid.UUID | None = None


class DepartmentOut(TimestampedRead):
    name: str
    description: str | None = None
    head_employee_id: uuid.UUID | None = None
