"""Standalone real-Postgres verification script (NOT pytest-collected).

Why this exists: tests/conftest.py unconditionally mocks
`sqlalchemy.ext.asyncio.create_async_engine` for the entire pytest session
(see CF-AUD-008), so no pytest-collected test in this repo — including the
ones that set real DB_HOST/DB_PORT env vars — ever actually executes SQL
against a real database. Even CI's Postgres service (.github/workflows/backend.yml)
is not exercised by `pytest -v`. This script runs OUTSIDE that mock (it never
imports tests/conftest.py) so it genuinely hits Postgres, mirroring the
pattern already used by tests/test_workflows.py.

Usage:
    ENV=test DB_HOST=localhost DB_PORT=55432 DB_NAME=corefusion_test \
    DB_USER=test_user DB_PASS=test_pass python tests/real_db_verification.py

Verifies, against real data and real SQL:
  1. list_employees no longer N+1s (query count is bounded, not linear in
     employee count) — CF-AUD-011 / CF-BE employees N+1 fix.
  2. Task-status IDOR fix holds against real persisted rows — CF-AUD-005.
  3. Lead-ownership IDOR fix holds against real persisted rows — CF-AUD-005.
  4. Client tenant isolation: client A cannot read client B's invoices.
"""
import asyncio
import statistics
import time
import uuid
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.dependencies import get_current_user
from app.core.password import hash_password
from app.main import app
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.lead import Lead
from app.models.leave import Leave
from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import Timesheet
from app.models.user import User

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"{'PASS' if passed else 'FAIL'} — {name}{': ' + detail if detail else ''}")


async def _mk_user(db, role: str, email: str) -> User:
    user = User(
        id=uuid.uuid4(), name=email.split("@")[0], email=email,
        password_hash=hash_password(uuid.uuid4().hex),  # unused placeholder — auth is dependency-overridden
        role=role, is_active=True, is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


async def verify_employees_n_plus_1():
    async with AsyncSessionLocal() as db:
        dept = Department(name=f"Eng-{uuid.uuid4().hex[:6]}")
        db.add(dept)
        await db.flush()

        for _ in range(25):
            u = await _mk_user(db, "employee", f"emp-{uuid.uuid4().hex[:8]}@example.com")
            emp = Employee(user_id=u.id, employee_code=f"EMP-{uuid.uuid4().hex[:8]}", department_id=dept.id, designation="Engineer")
            db.add(emp)
        await db.commit()

        admin_user = await _mk_user(db, "admin", f"admin-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()

    query_count = {"n": 0}

    def _count(*_a, **_kw):
        query_count["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _count)
    try:
        app.dependency_overrides[get_current_user] = lambda: admin_user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/employees?limit=100")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _count)
        app.dependency_overrides.pop(get_current_user, None)

    n = query_count["n"]
    # Bounded: 1 list query + 1 count query + department selectin + user
    # selectin (CRUDBase._with_relationships) — must not scale with row count.
    check(
        "employees list is not N+1 (25 rows, query count bounded)",
        resp.status_code == 200 and n <= 6,
        f"status={resp.status_code} query_count={n} (25 employees; pre-fix this was ~1+2N=~52)",
    )


async def verify_task_idor():
    async with AsyncSessionLocal() as db:
        dept = Department(name=f"Ops-{uuid.uuid4().hex[:6]}")
        db.add(dept)
        await db.flush()
        client_user = await _mk_user(db, "client", f"client-{uuid.uuid4().hex[:8]}@example.com")
        client = Client(user_id=client_user.id, company_name="Acme")
        db.add(client)
        await db.flush()
        proj_title = f"Proj-{uuid.uuid4().hex[:6]}"
        project = Project(title=proj_title, slug=proj_title.lower(), client_id=client.id, status="in_progress")
        db.add(project)
        await db.flush()

        assignee = await _mk_user(db, "employee", f"assignee-{uuid.uuid4().hex[:8]}@example.com")
        other = await _mk_user(db, "employee", f"other-{uuid.uuid4().hex[:8]}@example.com")
        task = Task(project_id=project.id, title="Do the thing", assigned_to=assignee.id, status="todo")
        db.add(task)
        await db.commit()
        task_id = task.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        app.dependency_overrides[get_current_user] = lambda: other
        resp_denied = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"})

        app.dependency_overrides[get_current_user] = lambda: assignee
        resp_allowed = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"})
    app.dependency_overrides.pop(get_current_user, None)

    check("non-assignee cannot update task status (real DB)", resp_denied.status_code == 403, f"got {resp_denied.status_code}")
    check("assignee can update own task status (real DB)", resp_allowed.status_code == 200, f"got {resp_allowed.status_code}")


async def verify_lead_idor():
    async with AsyncSessionLocal() as db:
        sales_a = await _mk_user(db, "sales", f"sales-a-{uuid.uuid4().hex[:8]}@example.com")
        sales_b = await _mk_user(db, "sales", f"sales-b-{uuid.uuid4().hex[:8]}@example.com")
        lead = Lead(contact_name="Prospect", email="prospect@example.com", source="website", status="new", owner_id=sales_a.id)
        db.add(lead)
        await db.commit()
        lead_id = lead.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        app.dependency_overrides[get_current_user] = lambda: sales_b
        resp_denied = await ac.get(f"/api/v1/leads/{lead_id}")

        app.dependency_overrides[get_current_user] = lambda: sales_a
        resp_allowed = await ac.get(f"/api/v1/leads/{lead_id}")
    app.dependency_overrides.pop(get_current_user, None)

    check("non-owner sales rep cannot read lead (real DB)", resp_denied.status_code == 403, f"got {resp_denied.status_code}")
    check("owning sales rep can read own lead (real DB)", resp_allowed.status_code == 200, f"got {resp_allowed.status_code}")


async def verify_client_tenant_isolation():
    async with AsyncSessionLocal() as db:
        user_a = await _mk_user(db, "client", f"tenant-a-{uuid.uuid4().hex[:8]}@example.com")
        user_b = await _mk_user(db, "client", f"tenant-b-{uuid.uuid4().hex[:8]}@example.com")
        client_a = Client(user_id=user_a.id, company_name="Tenant A")
        client_b = Client(user_id=user_b.id, company_name="Tenant B")
        db.add_all([client_a, client_b])
        await db.flush()
        invoice_b = Invoice(client_id=client_b.id, invoice_number=f"INV-{uuid.uuid4().hex[:8]}", amount=1000, total_amount=1000, issue_date=date.today(), due_date=date.today(), status="draft")
        db.add(invoice_b)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        app.dependency_overrides[get_current_user] = lambda: user_a
        resp = await ac.get("/api/v1/clients/me/invoices")
    app.dependency_overrides.pop(get_current_user, None)

    invoices = resp.json().get("data", []) if resp.status_code == 200 else None
    check(
        "client A's /me/invoices never returns client B's invoice (real DB)",
        resp.status_code == 200 and isinstance(invoices, list) and len(invoices) == 0,
        f"status={resp.status_code} returned={len(invoices) if invoices is not None else 'N/A'} rows",
    )


async def verify_leaves_timesheets_pagination():
    """CF-BE-006: employees.py's list_leaves/list_all_timesheets were refactored
    to share utils.pagination.paginate_query() instead of hand-rolled
    offset/limit + a separate count query. Prove the refactor still returns
    correct, paginated, filtered results against real Postgres."""
    async with AsyncSessionLocal() as db:
        dept = Department(name=f"Dept-{uuid.uuid4().hex[:6]}")
        db.add(dept)
        await db.flush()
        u = await _mk_user(db, "employee", f"pg-emp-{uuid.uuid4().hex[:8]}@example.com")
        emp = Employee(user_id=u.id, employee_code=f"EMP-{uuid.uuid4().hex[:8]}", department_id=dept.id)
        db.add(emp)
        await db.flush()

        for _ in range(7):
            db.add(Leave(employee_id=emp.id, type="casual", start_date=date.today(), end_date=date.today(), status="pending"))
            db.add(Timesheet(employee_id=emp.id, date=date.today(), hours=8, status="submitted"))
        await db.commit()

        admin_user = await _mk_user(db, "admin", f"pg-admin-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()

    transport = ASGITransport(app=app)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        leaves_resp = await ac.get(f"/api/v1/employees/leaves?employee_id={emp.id}&limit=5")
        ts_resp = await ac.get(f"/api/v1/employees/timesheets?employee_id={emp.id}&limit=5")
    app.dependency_overrides.pop(get_current_user, None)

    leaves_body = leaves_resp.json() if leaves_resp.status_code == 200 else {}
    ts_body = ts_resp.json() if ts_resp.status_code == 200 else {}
    check(
        "paginated /employees/leaves returns correct page size + total (real DB, post-refactor)",
        leaves_resp.status_code == 200 and len(leaves_body.get("data", [])) == 5 and leaves_body.get("meta", {}).get("total") == 7,
        f"status={leaves_resp.status_code} returned={len(leaves_body.get('data', []))} meta={leaves_body.get('meta')}",
    )
    check(
        "paginated /employees/timesheets returns correct page size + total (real DB, post-refactor)",
        ts_resp.status_code == 200 and len(ts_body.get("data", [])) == 5 and ts_body.get("meta", {}).get("total") == 7,
        f"status={ts_resp.status_code} returned={len(ts_body.get('data', []))} meta={ts_body.get('meta')}",
    )


async def measure_performance():
    """Honest, labeled latency measurement — NOT a substitute for a real load
    test. Conditions: single process, in-process ASGI transport (no network
    hop), local Docker Postgres on the same machine, sequential (concurrency=1)
    requests, warm connection pool, small dataset (see per-endpoint seed
    counts). Real numbers only — anything not measured here is not claimed."""
    async with AsyncSessionLocal() as db:
        admin_user = await _mk_user(db, "admin", f"perf-admin-{uuid.uuid4().hex[:8]}@example.com")
        await db.commit()

    endpoints = [
        ("GET /health", "GET", "/health"),
        ("GET /api/v1/auth/me", "GET", "/api/v1/auth/me"),
        ("GET /api/v1/employees (25 seeded rows)", "GET", "/api/v1/employees?limit=100"),
        ("GET /api/v1/projects", "GET", "/api/v1/projects"),
    ]

    transport = ASGITransport(app=app)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    results = []
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for label, method, path in endpoints:
            timings = []
            status = None
            for _ in range(20):
                t0 = time.perf_counter()
                resp = await ac.request(method, path)
                timings.append((time.perf_counter() - t0) * 1000)
                status = resp.status_code
            timings.sort()
            p50 = statistics.median(timings)
            p95 = timings[int(len(timings) * 0.95) - 1]
            results.append((label, status, p50, p95, max(timings)))
    app.dependency_overrides.pop(get_current_user, None)

    print("\n--- Latency (n=20, sequential, in-process ASGI, local Docker Postgres, warm pool) ---")
    print(f"{'Endpoint':<45} {'Status':<7} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for label, status, p50, p95, mx in results:
        print(f"{label:<45} {status:<7} {p50:>8.1f} {p95:>8.1f} {mx:>8.1f}")
        check(f"{label}: p95 < 200ms (n=20, local, no network hop, small dataset)", p95 < 200, f"p95={p95:.1f}ms max={mx:.1f}ms")
    print(
        "NOTE: this is an in-process, single-connection, small-dataset measurement — it proves "
        "these specific endpoints are not pathologically slow under the app's own real DB layer, "
        "but it is NOT a load test, NOT over-the-network, and NOT at production data volume. "
        "Do not treat this as the full <200ms performance gate."
    )


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await verify_employees_n_plus_1()
    await verify_task_idor()
    await verify_lead_idor()
    await verify_client_tenant_isolation()
    await verify_leaves_timesheets_pagination()
    await measure_performance()

    await engine.dispose()

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} real-DB checks passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
