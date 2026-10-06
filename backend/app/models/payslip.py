import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PayslipStatus


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("employee_id", "month", "year", name="uq_payslip_employee_period"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    basic: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    allowances: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    deductions: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[PayslipStatus] = mapped_column(Enum(PayslipStatus, name="payslip_status"), default=PayslipStatus.generated)

    employee = relationship("Employee", back_populates="payslips")
