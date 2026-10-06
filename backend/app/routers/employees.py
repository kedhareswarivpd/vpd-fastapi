import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.core.logger import logger
from app.crud.base import CRUDBase
from app.models.associations import project_members
from app.models.attendance import Attendance
from app.models.department import Department
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.models.enums import DocumentType, LeaveStatus, NotificationType, TimesheetStatus
from app.models.leave import Leave
from app.models.payslip import Payslip
from app.models.performance_feedback import PerformanceFeedback
from app.models.performance_goal import PerformanceGoal
from app.models.performance_review import PerformanceReview
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.employee import (
    AttendanceOut,
    EmployeeCreate,
    EmployeeDocumentOut,
    EmployeeOut,
    LeaveApply,
    LeaveOut,
    LeaveStatusUpdate,
    PayslipOut,
    TimesheetCreate,
    TimesheetOut,
    TimesheetStatusUpdate,
)
from app.schemas.performance import (
    PerformanceFeedbackCreate,
    PerformanceFeedbackOut,
    PerformanceGoalCreate,
    PerformanceGoalOut,
    PerformanceGoalUpdate,
    PerformanceReviewCreate,
    PerformanceReviewOut,
    PerformanceReviewUpdate,
)
from app.services.notification_service import notify_user
from app.utils.pagination import PageParams, bounded_select, page_params, paginate_query
from app.utils.responses import build_pagination_meta, success_response
from app.utils.uploads import load_private_file, save_upload

router = APIRouter(prefix="/employees", tags=["Employees"], dependencies=[Depends(get_current_user)])

crud = CRUDBase(Employee, searchable_fields=["employee_code", "designation"], relationships=["department", "user"])
leave_crud = CRUDBase(Leave, relationships=["employee"])
timesheet_crud = CRUDBase(Timesheet)


EMPLOYEE_ROLES = {"employee", "developer", "sales", "marketing", "project_manager", "qa", "support", "finance", "hr", "admin", "super_admin"}


def _parse_date_param(request: Request, name: str) -> date | None:
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ApiError.bad_request(f"Invalid {name}, expected YYYY-MM-DD") from None


async def _get_employee_for_user(db: AsyncSession, user: User) -> Employee:
    employee = (await db.execute(select(Employee).where(Employee.user_id == user.id))).scalar_one_or_none()
    if not employee:
        if user.role not in EMPLOYEE_ROLES:
            raise ApiError.not_found("Employee profile not found")
        # Auto-create a profile for existing users who don't have one yet
        short_id = str(user.id).replace("-", "")[:8].upper()
        employee = Employee(user_id=user.id, employee_code=f"EMP-{short_id}")
        db.add(employee)
        await db.commit()
        await db.refresh(employee)
    return employee


# ---------- Self-service (Employee Portal) ----------
@router.get("/me/profile", response_model=dict)
async def my_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    emp_data = EmployeeOut.model_validate(employee).model_dump()
    emp_data["name"] = current_user.name
    emp_data["email"] = current_user.email
    emp_data["role"] = current_user.role
    if employee.department_id:
        dept = (await db.execute(select(Department).where(Department.id == employee.department_id))).scalar_one_or_none()
        emp_data["department_name"] = dept.name if dept else None
    return success_response(data=emp_data)


@router.get("/me/attendance", response_model=dict)
async def my_attendance(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params), current_user: User = Depends(get_current_user)):
    # UAT closure pass §6: only "today" existed — an employee had no way to
    # see their own attendance history at all, let alone HR (workflow doc
    # §15: "Attendance information should be accessible to authorized HR
    # users" was entirely unimplemented; see list_attendance below).
    employee = await _get_employee_for_user(db, current_user)
    stmt = select(Attendance).where(Attendance.employee_id == employee.id)
    count_stmt = select(func.count()).select_from(Attendance).where(Attendance.employee_id == employee.id)
    start_date, end_date = _parse_date_param(request, "start_date"), _parse_date_param(request, "end_date")
    if start_date:
        stmt, count_stmt = stmt.where(Attendance.date >= start_date), count_stmt.where(Attendance.date >= start_date)
    if end_date:
        stmt, count_stmt = stmt.where(Attendance.date <= end_date), count_stmt.where(Attendance.date <= end_date)
    stmt = stmt.order_by(Attendance.date.desc())
    items, meta = await paginate_query(db, stmt, count_stmt, page)
    return success_response(data=[AttendanceOut.model_validate(a) for a in items], message="Attendance fetched", meta=meta)


@router.get("/me/attendance/today", response_model=dict)
async def today_attendance(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    today = date.today()
    record = (
        await db.execute(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.date == today))
    ).scalar_one_or_none()
    if not record:
        return success_response(data=None)
    return success_response(data=AttendanceOut.model_validate(record))


@router.post("/me/attendance/check-in", response_model=dict)
async def check_in(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    today = date.today()
    record = (
        await db.execute(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.date == today))
    ).scalar_one_or_none()
    if not record:
        record = Attendance(employee_id=employee.id, date=today, check_in=datetime.now(UTC).time(), status="present")
        db.add(record)
        await db.commit()
        await db.refresh(record)
    return success_response(data=AttendanceOut.model_validate(record), message="Checked in")


@router.post("/me/attendance/check-out", response_model=dict)
async def check_out(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    today = date.today()
    record = (
        await db.execute(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.date == today))
    ).scalar_one_or_none()
    if not record:
        raise ApiError.bad_request("You have not checked in today")
    record.check_out = datetime.now(UTC).time()
    await db.commit()
    await db.refresh(record)
    return success_response(data=AttendanceOut.model_validate(record), message="Checked out")


@router.get("/me/leaves", response_model=dict)
async def my_leaves(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(bounded_select(select(Leave).where(Leave.employee_id == employee.id).order_by(Leave.id.desc())))
    return success_response(data=[LeaveOut.model_validate(leave) for leave in result.scalars().all()])


@router.post("/me/leaves", response_model=dict, status_code=201)
async def apply_leave(payload: LeaveApply, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    leave = Leave(
        employee_id=employee.id,
        type=payload.type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status="pending",
    )
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return success_response(data=LeaveOut.model_validate(leave), message="Leave request submitted", status_code=201)


@router.get("/me/timesheets", response_model=dict)
async def my_timesheets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(bounded_select(select(Timesheet).where(Timesheet.employee_id == employee.id).order_by(Timesheet.date.desc())))
    return success_response(data=[TimesheetOut.model_validate(t) for t in result.scalars().all()])


@router.get("/me/payslips", response_model=dict)
async def my_payslips(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Employee self-service payslip history — only ever returns the calling
    employee's own payslips, scoped by employee_id, never anyone else's.
    Salary amounts are already excluded from the list-employees route for
    non-admin/HR callers (employees.py list_employees); this endpoint is the
    safe per-employee surface: you only ever see your own net_pay breakdown,
    not a peer's salary column in a shared list."""
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(
        bounded_select(
            select(Payslip)
            .where(Payslip.employee_id == employee.id)
            .order_by(Payslip.year.desc(), Payslip.month.desc())
        )
    )
    return success_response(data=[PayslipOut.model_validate(p) for p in result.scalars().all()])


@router.post("/me/timesheets", response_model=dict, status_code=201)
async def submit_timesheet(payload: TimesheetCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    # UAT closure pass §7: nothing checked that the employee was actually
    # assigned to payload.project_id — any employee could log (and get
    # paid/billed for) hours against a project they have no assignment to.
    if payload.project_id:
        is_member = (await db.execute(
            select(project_members.c.employee_id).where(
                project_members.c.project_id == payload.project_id, project_members.c.employee_id == employee.id,
            )
        )).scalar_one_or_none()
        if is_member is None:
            raise ApiError.forbidden("You can only log timesheet hours against a project you're assigned to")
    # UAT closure pass §7: TimesheetStatus.submitted was defined but nothing
    # ever set it — this endpoint left every entry at the ORM default
    # (draft) forever, since there's no separate employee-facing edit/submit
    # action to advance it later. The PM dashboard's "pending review" widget
    # (frontend fetchAllTimesheets({status:'submitted'})) was permanently
    # stuck at 0 as a result. This endpoint IS the employee's submit action
    # (the frontend already calls it submitTimesheet), so it should land the
    # entry directly in "submitted", not an unreachable "draft".
    entry = Timesheet(**payload.model_dump(), employee_id=employee.id, status=TimesheetStatus.submitted)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return success_response(data=TimesheetOut.model_validate(entry), message="Timesheet entry logged", status_code=201)


@router.get("/me/payslips", response_model=dict)
async def my_payslips(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(
        bounded_select(select(Payslip).where(Payslip.employee_id == employee.id).order_by(Payslip.year.desc(), Payslip.month.desc()))
    )
    payslips = result.scalars().all()
    return success_response(data=[PayslipOut.model_validate(p) for p in payslips])


PAYSLIP_SUBFOLDER = "payslips"


@router.get("/me/payslips/{payslip_id}/download")
async def download_my_payslip(payslip_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Payslips previously had no secured download path at all — only the
    metadata list (GET /me/payslips) existed. Ownership-checked (404, not
    403, on a mismatch) same as the equivalent employee-document download."""
    employee = await _get_employee_for_user(db, current_user)
    payslip = (await db.execute(select(Payslip).where(Payslip.id == payslip_id, Payslip.employee_id == employee.id))).scalar_one_or_none()
    if payslip is None or not payslip.file_url:
        raise ApiError.not_found("Payslip not found")
    content, filename, content_type = await load_private_file(payslip.file_url, PAYSLIP_SUBFOLDER)
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{employee_id}/payslips", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr", "finance"))])
async def create_payslip(
    employee_id: uuid.UUID, month: int = Form(...), year: int = Form(...),
    basic: float = Form(...), allowances: float = Form(0), deductions: float = Form(0),
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
):
    reference = await save_upload(file, PAYSLIP_SUBFOLDER)
    net_pay = basic + allowances - deductions
    payslip = Payslip(
        employee_id=employee_id, month=month, year=year, basic=basic,
        allowances=allowances, deductions=deductions, net_pay=net_pay, file_url=reference,
    )
    db.add(payslip)
    await db.commit()
    await db.refresh(payslip)
    return success_response(data=PayslipOut.model_validate(payslip), message="Payslip created", status_code=201)


@router.get("/me/documents", response_model=dict)
async def my_documents(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(bounded_select(select(EmployeeDocument).where(EmployeeDocument.employee_id == employee.id)))
    return success_response(data=[EmployeeDocumentOut.model_validate(d) for d in result.scalars().all()])


# Workflow doc §20 requires employees to "upload or download documents based
# on their permissions" — no create/upload endpoint existed at all for
# EmployeeDocument before this (only the list route above), meaning these
# records could never actually be produced through the app. Two directions,
# same private-storage pattern as career resumes and client files.
EMPLOYEE_DOCUMENT_SUBFOLDER = "employee-documents"


@router.post("/me/documents", response_model=dict, status_code=201)
async def upload_my_document(
    title: str = Form(...), type: DocumentType = Form(DocumentType.other),
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Employee self-upload (e.g. certificates)."""
    employee = await _get_employee_for_user(db, current_user)
    reference = await save_upload(file, EMPLOYEE_DOCUMENT_SUBFOLDER)
    doc = EmployeeDocument(employee_id=employee.id, title=title, type=type, file_url=reference)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return success_response(data=EmployeeDocumentOut.model_validate(doc), message="Document uploaded", status_code=201)


@router.post("/{employee_id}/documents", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr"))])
async def assign_employee_document(
    employee_id: uuid.UUID, title: str = Form(...), type: DocumentType = Form(DocumentType.other),
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
):
    """HR/admin assigns a document to an employee (policies, contracts, etc.)."""
    reference = await save_upload(file, EMPLOYEE_DOCUMENT_SUBFOLDER)
    doc = EmployeeDocument(employee_id=employee_id, title=title, type=type, file_url=reference)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return success_response(data=EmployeeDocumentOut.model_validate(doc), message="Document uploaded", status_code=201)


@router.get("/documents/{document_id}/download")
async def download_employee_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = (await db.execute(select(EmployeeDocument).where(EmployeeDocument.id == document_id))).scalar_one_or_none()
    if doc is None:
        raise ApiError.not_found("Document not found")
    if current_user.role not in ("admin", "hr", "super_admin"):
        employee = await _get_employee_for_user(db, current_user)
        if employee.id != doc.employee_id:
            raise ApiError.not_found("Document not found")
    content, filename, content_type = await load_private_file(doc.file_url, EMPLOYEE_DOCUMENT_SUBFOLDER)
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/me/performance-reviews", response_model=dict)
async def my_performance_reviews(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(
        bounded_select(select(PerformanceReview).where(PerformanceReview.employee_id == employee.id).order_by(PerformanceReview.review_date.desc()))
    )
    return success_response(data=[PerformanceReviewOut.model_validate(r) for r in result.scalars().all()])


@router.post("/me/performance-reviews/{review_id}/acknowledge", response_model=dict)
async def acknowledge_performance_review(review_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Review-acknowledgment lifecycle: the employee confirming they've
    read a finalized review."""
    employee = await _get_employee_for_user(db, current_user)
    review = (await db.execute(select(PerformanceReview).where(PerformanceReview.id == review_id, PerformanceReview.employee_id == employee.id))).scalar_one_or_none()
    if review is None:
        raise ApiError.not_found("Performance review not found")
    review.acknowledged_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(review)
    return success_response(data=PerformanceReviewOut.model_validate(review), message="Review acknowledged")


@router.post("/performance-reviews", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def create_performance_review(payload: PerformanceReviewCreate, db: AsyncSession = Depends(get_db)):
    review = PerformanceReview(**payload.model_dump())
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return success_response(data=PerformanceReviewOut.model_validate(review), message="Performance review created", status_code=201)


@router.get("/performance-reviews", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def list_performance_reviews(request: Request, db: AsyncSession = Depends(get_db)):
    filters = {}
    if emp_id := request.query_params.get("employee_id"):
        filters["employee_id"] = emp_id
    stmt = select(PerformanceReview).order_by(PerformanceReview.review_date.desc())
    for k, v in filters.items():
        stmt = stmt.where(getattr(PerformanceReview, k) == v)
    result = await db.execute(bounded_select(stmt))
    return success_response(data=[PerformanceReviewOut.model_validate(r) for r in result.scalars().all()])


@router.patch("/performance-reviews/{review_id}", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def update_performance_review(review_id: uuid.UUID, payload: PerformanceReviewUpdate, db: AsyncSession = Depends(get_db)):
    review = (await db.execute(select(PerformanceReview).where(PerformanceReview.id == review_id))).scalar_one_or_none()
    if review is None:
        raise ApiError.not_found("Performance review not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    await db.commit()
    await db.refresh(review)
    return success_response(data=PerformanceReviewOut.model_validate(review), message="Performance review updated")


# ---------- Performance goals & continuous feedback ----------
@router.post("/performance-goals", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def create_performance_goal(payload: PerformanceGoalCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    goal = PerformanceGoal(**payload.model_dump(), created_by=current_user.id)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return success_response(data=PerformanceGoalOut.model_validate(goal), message="Goal created", status_code=201)


@router.get("/me/performance-goals", response_model=dict)
async def my_performance_goals(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(bounded_select(select(PerformanceGoal).where(PerformanceGoal.employee_id == employee.id).order_by(PerformanceGoal.target_date)))
    return success_response(data=[PerformanceGoalOut.model_validate(g) for g in result.scalars().all()])


@router.get("/performance-goals", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def list_performance_goals(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(PerformanceGoal).order_by(PerformanceGoal.target_date)
    if emp_id := request.query_params.get("employee_id"):
        stmt = stmt.where(PerformanceGoal.employee_id == emp_id)
    result = await db.execute(bounded_select(stmt))
    return success_response(data=[PerformanceGoalOut.model_validate(g) for g in result.scalars().all()])


@router.patch("/performance-goals/{goal_id}", response_model=dict)
async def update_performance_goal(goal_id: uuid.UUID, payload: PerformanceGoalUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Staff can edit any field; the goal's own employee may only update
    their own progress/status — title/description/target_date stay
    staff-controlled, matching how goals are meant to be set by a
    manager and then progressed by the employee."""
    goal = (await db.execute(select(PerformanceGoal).where(PerformanceGoal.id == goal_id))).scalar_one_or_none()
    if goal is None:
        raise ApiError.not_found("Goal not found")
    is_staff_editor = current_user.role in ("admin", "hr", "project_manager")
    if not is_staff_editor:
        employee = await _get_employee_for_user(db, current_user)
        if employee.id != goal.employee_id:
            raise ApiError.forbidden("You can only update your own goals")
        allowed_fields = {"status", "progress_percent"}
        if set(payload.model_dump(exclude_unset=True)) - allowed_fields:
            raise ApiError.forbidden("You can only update status and progress on your own goal")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return success_response(data=PerformanceGoalOut.model_validate(goal), message="Goal updated")


@router.post("/{employee_id}/feedback", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def give_performance_feedback(employee_id: uuid.UUID, payload: PerformanceFeedbackCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    feedback = PerformanceFeedback(employee_id=employee_id, given_by=current_user.id, feedback_text=payload.feedback_text, feedback_type=payload.feedback_type)
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return success_response(data=PerformanceFeedbackOut.model_validate(feedback), message="Feedback recorded", status_code=201)


@router.get("/me/feedback", response_model=dict)
async def my_performance_feedback(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _get_employee_for_user(db, current_user)
    result = await db.execute(bounded_select(select(PerformanceFeedback).where(PerformanceFeedback.employee_id == employee.id).order_by(PerformanceFeedback.created_at.desc())))
    return success_response(data=[PerformanceFeedbackOut.model_validate(f) for f in result.scalars().all()])


# ---------- Leave & timesheet approval (HR reviews all; PM reviews their team's) ----------
# NOTE: These static routes MUST be registered before /{employee_id} to avoid
# FastAPI matching the literal string "leaves"/"timesheets" as a UUID path param.
async def _pm_team_employee_ids(db: AsyncSession, pm_user: User) -> list[uuid.UUID]:
    """A real gap found during a security audit: this router's own comment
    says "PM reviews their team's" leaves/timesheets, but until this fix
    NOTHING scoped a project_manager's list/approve access to their actual
    reports — any PM could view or approve any employee's leave/timesheet
    company-wide, not just their own team's, a horizontal privilege
    escalation within the project_manager role. Team = employees whose
    reporting_manager_id is this PM's own Employee.id."""
    pm_employee = (await db.execute(select(Employee).where(Employee.user_id == pm_user.id))).scalar_one_or_none()
    if pm_employee is None:
        return []
    result = await db.execute(select(Employee.id).where(Employee.reporting_manager_id == pm_employee.id))
    return list(result.scalars().all())


@router.get("/attendance", response_model=dict, dependencies=[Depends(require_roles("admin", "hr"))])
async def list_attendance(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    # UAT closure pass §6: workflow doc §15 — "Attendance information
    # should be accessible to authorized HR users" — had no backing
    # endpoint at all.
    stmt = select(Attendance).options(selectinload(Attendance.employee))
    count_stmt = select(func.count()).select_from(Attendance)
    emp_id = request.query_params.get("employee_id")
    start_date, end_date = _parse_date_param(request, "start_date"), _parse_date_param(request, "end_date")
    if emp_id:
        stmt, count_stmt = stmt.where(Attendance.employee_id == emp_id), count_stmt.where(Attendance.employee_id == emp_id)
    if start_date:
        stmt, count_stmt = stmt.where(Attendance.date >= start_date), count_stmt.where(Attendance.date >= start_date)
    if end_date:
        stmt, count_stmt = stmt.where(Attendance.date <= end_date), count_stmt.where(Attendance.date <= end_date)
    stmt = stmt.order_by(Attendance.date.desc())
    items, meta = await paginate_query(db, stmt, count_stmt, page)
    data = []
    for a in items:
        out_dict = AttendanceOut.model_validate(a).model_dump()
        out_dict["employee_code"] = a.employee.employee_code if a.employee else None
        data.append(out_dict)
    return success_response(data=data, message="Attendance fetched", meta=meta)


@router.get("/leaves", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def list_leaves(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params), current_user: User = Depends(get_current_user)):
    status_filter = request.query_params.get("status")
    requested_employee_id = request.query_params.get("employee_id")

    stmt = select(Leave).options(selectinload(Leave.employee))
    count_stmt = select(func.count()).select_from(Leave)

    if current_user.role == "project_manager":
        # CRUDBase.list() only supports equality filters, not IN — this
        # endpoint needs an IN-over-team-ids filter, so it builds its own
        # query rather than going through leave_crud.list() (same reasoning
        # list_all_timesheets below already uses its own query for).
        team_ids = await _pm_team_employee_ids(db, current_user)
        if requested_employee_id and uuid.UUID(requested_employee_id) not in team_ids:
            raise ApiError.forbidden("You can only view leave requests for your own team")
        if not team_ids:
            return success_response(data=[], message="Leave requests fetched", meta=build_pagination_meta(0, page.page, page.limit))
        target_ids = [uuid.UUID(requested_employee_id)] if requested_employee_id else team_ids
        stmt = stmt.where(Leave.employee_id.in_(target_ids))
        count_stmt = count_stmt.where(Leave.employee_id.in_(target_ids))
    elif requested_employee_id:
        stmt = stmt.where(Leave.employee_id == requested_employee_id)
        count_stmt = count_stmt.where(Leave.employee_id == requested_employee_id)

    if status_filter:
        stmt = stmt.where(Leave.status == status_filter)
        count_stmt = count_stmt.where(Leave.status == status_filter)

    stmt = stmt.order_by(Leave.created_at.desc())
    items, meta = await paginate_query(db, stmt, count_stmt, page)
    data = []
    for leave in items:
        out_dict = LeaveOut.model_validate(leave).model_dump()
        out_dict["employee_code"] = leave.employee.employee_code if leave.employee else None
        out_dict["designation"] = leave.employee.designation if leave.employee else None
        data.append(out_dict)
    return success_response(data=data, message="Leave requests fetched", meta=meta)


@router.patch("/leaves/{leave_id}/approve", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def review_leave(leave_id: uuid.UUID, payload: LeaveStatusUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = await leave_crud.get(db, leave_id)
    if current_user.role == "project_manager":
        team_ids = await _pm_team_employee_ids(db, current_user)
        if target.employee_id not in team_ids:
            raise ApiError.forbidden("You can only approve leave requests for your own team")

    # UAT closure pass (P3 follow-up): a repeated/concurrent approve call
    # re-ran the notification every time even though the leave was already
    # decided — the state itself stayed correct (idempotent), but the
    # employee got a duplicate notification per repeat click. Only the
    # request that actually moves the leave out of "pending" notifies.
    already_decided = target.status != LeaveStatus.pending
    leave = await leave_crud.update(db, leave_id, {"status": payload.status, "approved_by": current_user.id})
    if already_decided:
        return success_response(data=LeaveOut.model_validate(leave), message="Leave request updated")

    # Workflow doc §15: "The employee should receive the corresponding
    # notification" — approve_leave only updated the row, no notification
    # was ever sent. Best-effort: the leave decision itself already
    # committed by the time this runs, so a notify failure shouldn't undo it.
    try:
        employee = await db.get(Employee, leave.employee_id)
        if employee and employee.user_id:
            verb = "approved" if payload.status == LeaveStatus.approved else "rejected"
            await notify_user(
                db, employee.user_id, f"Leave request {verb}",
                f"Your {leave.type.value} leave request ({leave.start_date} to {leave.end_date}) was {verb}.",
                NotificationType.success if payload.status == LeaveStatus.approved else NotificationType.warning,
                "/employee-portal?tab=leaves",
            )
    except Exception as exc:  # noqa: BLE001 — the leave decision must not fail over notification delivery
        logger.warning("Failed to notify employee of leave review %s: %s", leave_id, exc)

    return success_response(data=LeaveOut.model_validate(leave), message="Leave request updated")


@router.get("/timesheets", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def list_all_timesheets(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params), current_user: User = Depends(get_current_user)):
    filters = {k: request.query_params.get(k) for k in ("employee_id", "project_id", "status") if request.query_params.get(k)}
    # Nested selectinload for employee.user avoids a per-row User re-query
    # below (CF-AUD-011 N+1, same pattern as list_employees/my_meetings).
    stmt = select(Timesheet).options(selectinload(Timesheet.employee).selectinload(Employee.user))
    count_stmt = select(func.count()).select_from(Timesheet)

    if current_user.role == "project_manager":
        # Same real gap as list_leaves above: nothing previously scoped a
        # PM's timesheet visibility to their own team.
        team_ids = await _pm_team_employee_ids(db, current_user)
        requested_employee_id = filters.get("employee_id")
        if requested_employee_id and uuid.UUID(requested_employee_id) not in team_ids:
            raise ApiError.forbidden("You can only view timesheets for your own team")
        if not team_ids:
            return success_response(data=[], message="Timesheets fetched", meta=build_pagination_meta(0, page.page, page.limit))
        target_ids = [uuid.UUID(requested_employee_id)] if requested_employee_id else team_ids
        stmt = stmt.where(Timesheet.employee_id.in_(target_ids))
        count_stmt = count_stmt.where(Timesheet.employee_id.in_(target_ids))
        filters.pop("employee_id", None)

    for field, value in filters.items():
        column = getattr(Timesheet, field, None)
        if column is not None:
            stmt = stmt.where(column == value)
            count_stmt = count_stmt.where(column == value)
    stmt = stmt.order_by(Timesheet.date.desc())
    items, meta = await paginate_query(db, stmt, count_stmt, page)
    data = []
    for t in items:
        out = TimesheetOut.model_validate(t).model_dump()
        emp = t.employee
        out["employee_code"] = emp.employee_code if emp else None
        out["designation"] = emp.designation if emp else None
        out["employee_name"] = emp.user.name if emp and emp.user else None
        data.append(out)
    return success_response(data=data, message="Timesheets fetched", meta=meta)


@router.patch("/timesheets/{timesheet_id}/approve", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def review_timesheet(timesheet_id: uuid.UUID, payload: TimesheetStatusUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "project_manager":
        target = await timesheet_crud.get(db, timesheet_id)
        team_ids = await _pm_team_employee_ids(db, current_user)
        if target.employee_id not in team_ids:
            raise ApiError.forbidden("You can only approve timesheets for your own team")
    timesheet = await timesheet_crud.update(db, timesheet_id, {"status": payload.status})
    return success_response(data=TimesheetOut.model_validate(timesheet), message="Timesheet updated")


# ---------- HR / Admin management ----------
@router.get("", response_model=dict, dependencies=[Depends(require_roles("admin", "hr", "project_manager"))])
async def list_employees(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params), current_user: User = Depends(get_current_user)):
    filters = {k: request.query_params.get(k) for k in ("department_id", "status", "employment_type") if request.query_params.get(k)}
    items, total = await crud.list(db, page, filters)
    # Compensation is payroll-sensitive: only admin/hr should see it here, not
    # every role that can browse the employee directory (e.g. project_manager).
    can_view_salary = current_user.role in ("admin", "super_admin", "hr")
    # `crud.list()` above eager-loads `department`/`user` via selectinload
    # (2 bounded queries total), so this loop must read those relationships
    # directly rather than re-querying per row — the previous per-employee
    # Department/User lookups were an N+1 (CF-AUD-011).
    data = []
    for e in items:
        out = EmployeeOut.model_validate(e).model_dump()
        if not can_view_salary:
            out.pop("salary", None)
        out["department_name"] = e.department.name if e.department else None
        out["name"] = e.user.name if e.user else None
        out["email"] = e.user.email if e.user else None
        data.append(out)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=data, message="Employees fetched", meta=meta)


@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr"))])
async def create_employee(payload: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    user_id = data.get("user_id")
    if user_id:
        existing = (await db.execute(select(Employee).where(Employee.user_id == user_id))).scalar_one_or_none()
        if existing:
            # A real gap found during a security audit: this "re-POST to
            # update" branch was applying every EmployeeCreate field to the
            # existing record, including the identity fields `user_id`/
            # `employee_code` — a caller could smuggle a changed
            # `employee_code` (or, since `existing` was already looked up
            # BY `user_id`, at least a redundant identity-mutation surface)
            # through what's semantically an update, not a create. Excluded
            # here since neither should ever change once an Employee row
            # exists — the row's user_id is fixed by the lookup itself.
            update_data = {k: v for k, v in data.items() if k not in ("user_id", "employee_code")}
            for k, v in update_data.items():
                setattr(existing, k, v)
            await db.commit()
            await db.refresh(existing)
            return success_response(data=EmployeeOut.model_validate(existing), message="Employee profile updated successfully", status_code=201)
    employee = await crud.create(db, data)
    return success_response(data=EmployeeOut.model_validate(employee), message="Employee created successfully", status_code=201)

