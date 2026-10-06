import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import project_members
from app.models.enums import EmployeeStatus, EmploymentType


class Employee(Base):
    __tablename__ = "employees"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), index=True)
    designation: Mapped[str | None] = mapped_column(String(150))
    date_of_joining: Mapped[date | None] = mapped_column(Date)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType, name="employment_type"), default=EmploymentType.full_time
    )
    status: Mapped[EmployeeStatus] = mapped_column(Enum(EmployeeStatus, name="employee_status"), default=EmployeeStatus.active)
    office_location: Mapped[str | None] = mapped_column(String(100))
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    salary: Mapped[float | None] = mapped_column(Numeric(12, 2))
    address: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="employee_profile")
    department = relationship("Department", back_populates="employees")
    manager = relationship("Employee", remote_side="Employee.id")
    attendance = relationship("Attendance", back_populates="employee")
    leaves = relationship("Leave", back_populates="employee")
    timesheets = relationship("Timesheet", back_populates="employee")
    payslips = relationship("Payslip", back_populates="employee")
    documents = relationship("EmployeeDocument", back_populates="employee")
    projects = relationship("Project", secondary=project_members, back_populates="team")
