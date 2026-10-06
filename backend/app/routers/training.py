import uuid
from contextlib import suppress

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.training import Course, TrainingEnrollment
from app.models.user import User
from app.schemas.training import CourseCreate, CourseOut, TrainingEnrollmentOut
from app.utils.pagination import PageParams, bounded_select, page_params, paginate_query
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/trainings", tags=["Training"])

course_crud = CRUDBase(Course, searchable_fields=["title", "category"])


# ---------- Public / authenticated listing ----------
@router.get("/courses", response_model=dict)
async def list_courses(
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(page_params),
):
    filters = {"is_published": True}
    items, total = await course_crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[CourseOut.model_validate(c) for c in items], message="Courses fetched", meta=meta)


@router.get("/courses/{course_id}", response_model=dict)
async def get_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await course_crud.get(db, course_id)
    return success_response(data=CourseOut.model_validate(course))


# ---------- Employee enrollment (self-service) ----------
@router.post("/enroll", response_model=dict, status_code=201)
async def enroll(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.employee import Employee
    employee = (await db.execute(select(Employee).where(Employee.user_id == current_user.id))).scalar_one_or_none()
    if not employee:
        raise ApiError.not_found("Employee profile not found")

    existing = await db.execute(
        select(TrainingEnrollment).where(
            TrainingEnrollment.employee_id == employee.id,
            TrainingEnrollment.course_id == course_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ApiError.conflict("Already enrolled in this course")

    enrollment = TrainingEnrollment(employee_id=employee.id, course_id=course_id)
    db.add(enrollment)
    try:
        await db.commit()
    except IntegrityError:
        # The query-then-insert check above narrows the common case, but a
        # genuine race (two concurrent enroll requests for the same
        # employee/course) is only actually prevented by the database's own
        # unique constraint (training_enrollments' uq_training_enrollment_
        # employee_course) — this translates that constraint violation into
        # the same friendly 409 the pre-check gives, rather than a raw 500.
        await db.rollback()
        raise ApiError.conflict("Already enrolled in this course") from None
    await db.refresh(enrollment)
    return success_response(data=TrainingEnrollmentOut.model_validate(enrollment), message="Enrolled successfully", status_code=201)


@router.get("/my-enrollments", response_model=dict)
async def my_enrollments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.employee import Employee
    employee = (await db.execute(select(Employee).where(Employee.user_id == current_user.id))).scalar_one_or_none()
    if not employee:
        raise ApiError.not_found("Employee profile not found")
    result = await db.execute(
        bounded_select(
            select(TrainingEnrollment).options(selectinload(TrainingEnrollment.course))
            .where(TrainingEnrollment.employee_id == employee.id)
            .order_by(TrainingEnrollment.enrolled_at.desc())
        )
    )
    return success_response(data=[TrainingEnrollmentOut.model_validate(e) for e in result.scalars().all()])


# ---------- Admin course creation & enrollment management ----------
@router.post("", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr"))])
@router.post("/courses", response_model=dict, status_code=201, dependencies=[Depends(require_roles("admin", "hr"))])
async def create_course(payload: CourseCreate, db: AsyncSession = Depends(get_db)):
    from slugify import slugify
    data = payload.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(payload.title)
    course = await course_crud.create(db, data)
    return success_response(data=CourseOut.model_validate(course), message="Course created successfully", status_code=201)



@router.get("/enrollments", response_model=dict, dependencies=[Depends(require_roles("admin", "hr"))])
async def list_enrollments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(page_params),
):
    filters = {}
    emp_id = request.query_params.get("employee_id")
    if emp_id:
        with suppress(ValueError):
            filters["employee_id"] = uuid.UUID(emp_id)
    stmt = select(TrainingEnrollment).options(selectinload(TrainingEnrollment.course))
    count_stmt = select(func.count()).select_from(TrainingEnrollment)
    for k, v in filters.items():
        stmt = stmt.where(getattr(TrainingEnrollment, k) == v)
        count_stmt = count_stmt.where(getattr(TrainingEnrollment, k) == v)
    stmt = stmt.order_by(TrainingEnrollment.enrolled_at.desc())
    items, meta = await paginate_query(db, stmt, count_stmt, page)
    return success_response(data=[TrainingEnrollmentOut.model_validate(e) for e in items], message="Enrollments fetched", meta=meta)

