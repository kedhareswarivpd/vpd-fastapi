import uuid
from datetime import date, time

from pydantic import BaseModel, field_serializer

from app.models.enums import DocumentType, EmployeeStatus, EmploymentType, LeaveStatus, LeaveType, TimesheetStatus
from app.schemas.common import TimestampedRead


class EmployeeCreate(BaseModel):
    user_id: uuid.UUID
    employee_code: str
    department_id: uuid.UUID | None = None
    designation: str | None = None
    date_of_joining: date | None = None
    date_of_birth: date | None = None
    employment_type: EmploymentType = EmploymentType.full_time
    status: EmployeeStatus = EmployeeStatus.active
    office_location: str | None = None
    reporting_manager_id: uuid.UUID | None = None
    salary: float | None = None
    address: str | None = None


class EmployeeUpdate(BaseModel):
    department_id: uuid.UUID | None = None
    designation: str | None = None
    employment_type: EmploymentType | None = None
    status: EmployeeStatus | None = None
    office_location: str | None = None
    reporting_manager_id: uuid.UUID | None = None
    salary: float | None = None
    address: str | None = None


class EmployeeOut(TimestampedRead):
    user_id: uuid.UUID
    employee_code: str
    department_id: uuid.UUID | None = None
    designation: str | None = None
    date_of_joining: date | None = None
    date_of_birth: date | None = None
    employment_type: EmploymentType
    status: EmployeeStatus
    office_location: str | None = None
    reporting_manager_id: uuid.UUID | None = None
    salary: float | None = None
    address: str | None = None


LEAVE_TYPE_ALIASES = {
    "annual": LeaveType.earned,
    "personal": LeaveType.casual,
    "sick": LeaveType.sick,
    "casual": LeaveType.casual,
    "earned": LeaveType.earned,
    "unpaid": LeaveType.unpaid,
    "maternity": LeaveType.maternity,
    "paternity": LeaveType.paternity,
}


class LeaveApply(BaseModel):
    type: LeaveType
    start_date: date
    end_date: date
    reason: str | None = None

    model_config = {"use_enum_values": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict) and "type" in obj:
            obj = {**obj, "type": LEAVE_TYPE_ALIASES.get(str(obj["type"]).lower(), LeaveType.casual)}
        return super().model_validate(obj, **kwargs)


class LeaveOut(TimestampedRead):
    employee_id: uuid.UUID
    type: str
    start_date: date
    end_date: date
    reason: str | None = None
    status: str


class LeaveStatusUpdate(BaseModel):
    status: LeaveStatus


class TimesheetCreate(BaseModel):
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    date: date
    hours: float
    description: str | None = None


class TimesheetOut(TimestampedRead):
    employee_id: uuid.UUID
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    date: date
    hours: float
    description: str | None = None
    status: str


class TimesheetStatusUpdate(BaseModel):
    status: TimesheetStatus


class PayslipOut(TimestampedRead):
    employee_id: uuid.UUID
    month: int
    year: int
    basic: float
    allowances: float
    deductions: float
    net_pay: float
    file_url: str | None = None
    status: str


class AttendanceOut(TimestampedRead):
    employee_id: uuid.UUID
    date: date
    status: str
    check_in: time | None = None
    check_out: time | None = None

    @field_serializer('check_in', 'check_out')
    def serialize_time(self, v: time | None) -> str | None:
        return v.strftime('%I:%M %p') if v else None


class EmployeeDocumentCreate(BaseModel):
    title: str
    type: DocumentType = DocumentType.other
    file_url: str


class EmployeeDocumentOut(TimestampedRead):
    employee_id: uuid.UUID
    title: str
    type: DocumentType
    file_url: str
