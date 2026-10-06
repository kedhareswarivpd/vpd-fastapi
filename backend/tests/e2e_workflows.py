"""Real end-to-end backend workflow suite: real Postgres, real Redis, the
actual FastAPI app served over real HTTP (ASGI transport) — no mocked
persistence. Standalone (not pytest-collected) for the same reason as
tests/real_db_verification.py: tests/conftest.py mocks the SQLAlchemy engine
for the whole pytest session, so nothing in this repo's mocked suite ever
touches a real database.

Authentication is simulated via dependency_override on get_current_user
(this exercises authorization/business-logic/tenant-isolation for real
without needing a real login round trip), but every subsequent layer —
authorization, business logic, persistence, tenant/ownership checks — runs
for real against a real database. Each workflow below includes at least one
negative/unauthorized case, not just the happy path.

Usage:
    ENV=test DB_HOST=localhost DB_PORT=<port> DB_NAME=... DB_USER=... DB_PASS=... \
    REDIS_HOST=localhost REDIS_PORT=<port> \
    python -m tests.e2e_workflows
"""
import asyncio
import uuid
from datetime import date

from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.dependencies import get_current_user
from app.core.password import hash_password
from app.main import app
from app.models.career import Career
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.project import Project
from app.models.task import Task
from app.models.user import User

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"{'PASS' if passed else 'FAIL'} — {name}{': ' + detail if detail else ''}")


async def _mk_user(db, role: str, email: str) -> User:
    user = User(
        id=uuid.uuid4(), name=email.split("@")[0], email=email,
        password_hash=hash_password(uuid.uuid4().hex),  # unused placeholder — auth is dependency-overridden below
        role=role, is_active=True, is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


def _client_for(user) -> AsyncClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def workflow_client_portal():
    """CLIENT: login (simulated) -> view own projects -> create a support
    ticket -> view own invoices. Negative: a second, unrelated client cannot
    see the first client's tickets/invoices (tenant isolation)."""
    async with AsyncSessionLocal() as db:
        user_a = await _mk_user(db, "client", f"e2e-client-a-{uuid.uuid4().hex[:8]}@example.com")
        user_b = await _mk_user(db, "client", f"e2e-client-b-{uuid.uuid4().hex[:8]}@example.com")
        client_a = Client(user_id=user_a.id, company_name="E2E Client A")
        db.add(client_a)
        await db.flush()
        title = f"E2E Project {uuid.uuid4().hex[:6]}"
        project = Project(title=title, slug=title.lower().replace(" ", "-"), client_id=client_a.id, status="in_progress")
        db.add(project)
        await db.commit()

    async with _client_for(user_a) as ac:
        r1 = await ac.get("/api/v1/clients/me/projects")
        check("client A sees their own project", r1.status_code == 200 and len(r1.json()["data"]) == 1, f"status={r1.status_code}")

        r2 = await ac.post("/api/v1/clients/me/tickets", json={"subject": "E2E ticket", "description": "test", "priority": "medium"})
        check("client A creates a support ticket", r2.status_code == 201, f"status={r2.status_code}")

        r3 = await ac.get("/api/v1/clients/me/tickets")
        check("client A sees their own ticket", r3.status_code == 200 and len(r3.json()["data"]) == 1, f"status={r3.status_code}")
    app.dependency_overrides.pop(get_current_user, None)

    # Negative: client B must not see client A's data via the same "me" endpoints
    async with _client_for(user_b) as ac:
        r4 = await ac.get("/api/v1/clients/me/projects")
        check("NEGATIVE: client B's /me/projects never returns client A's project", r4.status_code == 200 and len(r4.json()["data"]) == 0, f"returned {len(r4.json().get('data', []))} rows")

        r5 = await ac.get("/api/v1/clients/me/tickets")
        check("NEGATIVE: client B's /me/tickets never returns client A's ticket", r5.status_code == 200 and len(r5.json()["data"]) == 0, f"returned {len(r5.json().get('data', []))} rows")
    app.dependency_overrides.pop(get_current_user, None)


async def workflow_employee_portal():
    """EMPLOYEE: check in -> apply for leave -> HR approves -> task status
    update. Negative: a different employee cannot approve the leave (role
    boundary) and cannot update a task assigned to someone else (ownership)."""
    async with AsyncSessionLocal() as db:
        dept = Department(name=f"E2E-Dept-{uuid.uuid4().hex[:6]}")
        db.add(dept)
        await db.flush()
        emp_user = await _mk_user(db, "employee", f"e2e-emp-{uuid.uuid4().hex[:8]}@example.com")
        employee = Employee(user_id=emp_user.id, employee_code=f"E2E-{uuid.uuid4().hex[:8]}", department_id=dept.id)
        db.add(employee)
        other_emp_user = await _mk_user(db, "employee", f"e2e-emp2-{uuid.uuid4().hex[:8]}@example.com")
        other_employee = Employee(user_id=other_emp_user.id, employee_code=f"E2E-{uuid.uuid4().hex[:8]}", department_id=dept.id)
        db.add(other_employee)
        hr_user = await _mk_user(db, "hr", f"e2e-hr-{uuid.uuid4().hex[:8]}@example.com")

        client_user = await _mk_user(db, "client", f"e2e-pclient-{uuid.uuid4().hex[:8]}@example.com")
        client = Client(user_id=client_user.id, company_name="E2E Task Co")
        db.add(client)
        await db.flush()
        title = f"E2E Task Project {uuid.uuid4().hex[:6]}"
        project = Project(title=title, slug=title.lower().replace(" ", "-"), client_id=client.id, status="in_progress")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, title="E2E task", assigned_to=emp_user.id, status="todo")
        db.add(task)
        await db.commit()
        task_id = task.id

    async with _client_for(emp_user) as ac:
        r1 = await ac.post("/api/v1/employees/me/attendance/check-in")
        check("employee checks in", r1.status_code == 200, f"status={r1.status_code}")

        r2 = await ac.post("/api/v1/employees/me/leaves", json={"type": "casual", "start_date": str(date.today()), "end_date": str(date.today()), "reason": "E2E test"})
        check("employee applies for leave", r2.status_code == 201, f"status={r2.status_code}")
        leave_id = r2.json()["data"]["id"] if r2.status_code == 201 else None

        r3 = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"})
        check("assignee updates own task status", r3.status_code == 200, f"status={r3.status_code}")
    app.dependency_overrides.pop(get_current_user, None)

    # Negative: a different employee cannot update this task (ownership boundary)
    async with _client_for(other_emp_user) as ac:
        r4 = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "done"})
        check("NEGATIVE: non-assignee employee cannot update this task", r4.status_code == 403, f"status={r4.status_code}")

        r5 = await ac.patch(f"/api/v1/employees/leaves/{leave_id}/approve", json={"status": "approved"})
        check("NEGATIVE: employee (non-HR) cannot approve leave", r5.status_code == 403, f"status={r5.status_code}")
    app.dependency_overrides.pop(get_current_user, None)

    # HR approves the leave — the legitimate path
    async with _client_for(hr_user) as ac:
        r6 = await ac.patch(f"/api/v1/employees/leaves/{leave_id}/approve", json={"status": "approved"})
        check("HR approves the leave request", r6.status_code == 200 and r6.json()["data"]["status"] == "approved", f"status={r6.status_code}")
    app.dependency_overrides.pop(get_current_user, None)


async def workflow_admin_user_management():
    """ADMIN: create a user -> the new user shows up in the user list.
    Negative: a non-admin cannot create users."""
    async with AsyncSessionLocal() as db:
        admin_user = await _mk_user(db, "admin", f"e2e-admin-{uuid.uuid4().hex[:8]}@example.com")
        employee_user = await _mk_user(db, "employee", f"e2e-nonadmin-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()

    # POST /users creates the account entirely locally (Argon2id hash,
    # app-generated UUID) — no external identity provider involved since the
    # Supabase Auth -> CoreFusion Auth migration, so nothing needs stubbing
    # here anymore; this runs for real end to end against Postgres.
    new_email = f"e2e-created-{uuid.uuid4().hex[:8]}@example.com"
    async with _client_for(admin_user) as ac:
        r1 = await ac.post("/api/v1/users", json={"name": "E2E Created User", "email": new_email, "password": "Password123!", "role": "sales"})
        check("admin creates a new user", r1.status_code == 201, f"status={r1.status_code} body={r1.text[:200]}")
    app.dependency_overrides.pop(get_current_user, None)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        created = (await db.execute(text("SELECT id, role FROM users WHERE email = :e"), {"e": new_email})).fetchone()
        check("created user actually persisted in Postgres with correct role", created is not None and created[1] == "sales", f"row={created}")

    # Negative: a non-admin role must not be able to create users
    async with _client_for(employee_user) as ac:
        r2 = await ac.post("/api/v1/users", json={"name": "Should Not Exist", "email": f"e2e-blocked-{uuid.uuid4().hex[:8]}@example.com", "password": "Password123!", "role": "admin"})
        check("NEGATIVE: non-admin cannot create users", r2.status_code == 403, f"status={r2.status_code}")
    app.dependency_overrides.pop(get_current_user, None)


async def workflow_careers():
    """CAREERS: public applicant applies to an open position with a resume
    upload -> HR reviews the application and downloads the resume.
    Negative: an unauthenticated caller cannot download the private resume,
    and cannot apply to a closed position."""
    async with AsyncSessionLocal() as db:
        title = f"E2E Open Role {uuid.uuid4().hex[:6]}"
        open_career = Career(title=title, slug=title.lower().replace(" ", "-"), status="open")
        db.add(open_career)
        closed_title = f"E2E Closed Role {uuid.uuid4().hex[:6]}"
        closed_career = Career(title=closed_title, slug=closed_title.lower().replace(" ", "-"), status="closed")
        db.add(closed_career)
        hr_user = await _mk_user(db, "hr", f"e2e-career-hr-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()
        open_id, closed_id = open_career.id, closed_career.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"resume": ("resume.pdf", b"%PDF-1.4 fake resume content for e2e test", "application/pdf")}
        data = {"full_name": "E2E Applicant", "email": "applicant@example.com"}
        r1 = await ac.post(f"/api/v1/careers/{open_id}/apply", data=data, files=files)
        check("applicant applies to an open position with resume upload", r1.status_code == 201, f"status={r1.status_code} body={r1.text[:200]}")
        application_id = r1.json()["data"]["id"] if r1.status_code == 201 else None

        r2 = await ac.post(f"/api/v1/careers/{closed_id}/apply", data=data, files=files)
        check("NEGATIVE: cannot apply to a closed position", r2.status_code == 400, f"status={r2.status_code}")

        if application_id:
            r3 = await ac.get(f"/api/v1/careers/admin/applications/{application_id}/resume")
            check("NEGATIVE: unauthenticated caller cannot download the private resume", r3.status_code == 401, f"status={r3.status_code}")

    if application_id:
        async with _client_for(hr_user) as ac:
            r4 = await ac.get(f"/api/v1/careers/admin/applications/{application_id}/resume")
            check("HR downloads the applicant's resume", r4.status_code == 200 and r4.content.startswith(b"%PDF"), f"status={r4.status_code}")
        app.dependency_overrides.pop(get_current_user, None)


async def workflow_content_publishing():
    """CONTENT/CMS: marketing creates and publishes a blog post -> an
    unauthenticated visitor can read it. Negative: an unauthenticated
    visitor cannot see an unpublished draft in the list."""
    async with AsyncSessionLocal() as db:
        marketing_user = await _mk_user(db, "marketing", f"e2e-marketing-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()

    async with _client_for(marketing_user) as ac:
        title = f"E2E Blog Post {uuid.uuid4().hex[:6]}"
        r1 = await ac.post("/api/v1/blogs", json={"title": title, "slug": title.lower().replace(" ", "-"), "content": "E2E test content", "status": "published"})
        check("marketing creates a published blog post", r1.status_code == 201, f"status={r1.status_code} body={r1.text[:200]}")

        draft_title = f"E2E Draft Post {uuid.uuid4().hex[:6]}"
        r2 = await ac.post("/api/v1/blogs", json={"title": draft_title, "slug": draft_title.lower().replace(" ", "-"), "content": "should not be public", "status": "draft"})
        check("marketing creates a draft blog post", r2.status_code == 201, f"status={r2.status_code}")
    app.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r3 = await ac.get("/api/v1/blogs")
        titles = [b["title"] for b in r3.json()["data"]]
        check("unauthenticated visitor can see the published post in the public list", title in titles, f"public list has {len(titles)} posts")
        check("NEGATIVE: unauthenticated visitor never sees the draft in the public list", draft_title not in titles, "draft leaked into public list" if draft_title in titles else "")


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await workflow_client_portal()
    await workflow_employee_portal()
    await workflow_admin_user_management()
    await workflow_careers()
    await workflow_content_publishing()

    await engine.dispose()

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} E2E checks passed")
    if failed:
        print("FAILED:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
