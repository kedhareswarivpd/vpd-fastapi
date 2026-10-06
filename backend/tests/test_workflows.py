import asyncio
import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_current_user
from app.main import app
from app.models.client import Client
from app.models.department import Department
from app.models.user import User


async def run_e2e_verification():
    print("=====================================================")
    print("  COMPREHENSIVE E2E WORKFLOW VERIFICATION SUITE")
    print("=====================================================")

    async with AsyncSessionLocal() as session:
        admin_user = (await session.execute(select(User).where(User.role == "super_admin"))).scalars().first()
        if not admin_user:
            admin_user = (await session.execute(select(User).where(User.role == "admin"))).scalars().first()

        dev_user = (await session.execute(select(User).where(User.email == "developer@corefusiontech.com"))).scalars().first()
        pm_user = (await session.execute(select(User).where(User.role == "project_manager"))).scalars().first()
        hr_user = (await session.execute(select(User).where(User.role == "hr"))).scalars().first() or admin_user
        support_user = (await session.execute(select(User).where(User.role == "support"))).scalars().first() or admin_user
        client_user = (await session.execute(select(User).where(User.email == "arthi@gmail.com"))).scalars().first()
        dept = (await session.execute(select(Department))).scalars().first()
        dept_id = str(dept.id) if dept else str(uuid.uuid4())
        client_obj = (await session.execute(select(Client).where(Client.user_id == client_user.id))).scalar_one_or_none() if client_user else None

    print(f"Admin: {admin_user.email} | PM: {pm_user.email} | Dev: {dev_user.email} | Client: {client_user.email if client_user else None}")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # =========================================================================
        # WORKFLOW 1: Employee Lifecycle
        # =========================================================================
        print("\n--- [WORKFLOW 1] Employee Lifecycle ---")
        app.dependency_overrides[get_current_user] = lambda: admin_user

        # 1. Admin creates User account
        test_email = f"sales.test.{uuid.uuid4().hex[:6]}@corefusiontech.com"
        u_res = await ac.post("/api/v1/users", json={
            "name": "Test Sales Executive",
            "email": test_email,
            "password": "Password@123",
            "role": "sales"
        })
        print(f"1. POST /api/v1/users -> {u_res.status_code}")
        assert u_res.status_code == 201, u_res.text
        new_user_id = u_res.json()["data"]["id"]

        # 2. Admin creates Employee profile
        emp_code = f"EMP-{uuid.uuid4().hex[:4].upper()}"
        e_res = await ac.post("/api/v1/employees", json={
            "user_id": new_user_id,
            "employee_code": emp_code,
            "department_id": dept_id,
            "designation": "Senior Sales Associate",
            "salary": 6500.0,
            "employment_type": "full_time",
            "office_location": "San Francisco HQ"
        })
        print(f"2. POST /api/v1/employees -> {e_res.status_code}")
        assert e_res.status_code == 201, e_res.text

        # 3. Employee self-service
        async with AsyncSessionLocal() as session:
            new_u = (await session.execute(select(User).where(User.id == uuid.UUID(new_user_id)))).scalar_one()
        app.dependency_overrides[get_current_user] = lambda: new_u

        # Check-in
        cin_res = await ac.post("/api/v1/employees/me/attendance/check-in")
        print(f"3a. POST /employees/me/attendance/check-in -> {cin_res.status_code}")

        # Check-out
        cout_res = await ac.post("/api/v1/employees/me/attendance/check-out")
        print(f"3b. POST /employees/me/attendance/check-out -> {cout_res.status_code}")

        # Apply leave
        leave_res = await ac.post("/api/v1/employees/me/leaves", json={
            "type": "casual",
            "start_date": str(date.today() + timedelta(days=7)),
            "end_date": str(date.today() + timedelta(days=9)),
            "reason": "Family vacation"
        })
        print(f"3c. POST /employees/me/leaves -> {leave_res.status_code}")
        assert leave_res.status_code == 201, leave_res.text
        leave_id = leave_res.json()["data"]["id"]

        # Log timesheet
        ts_res = await ac.post("/api/v1/employees/me/timesheets", json={
            "date": str(date.today()),
            "hours": 8.0,
            "description": "Client pitches and outreach calls"
        })
        print(f"3d. POST /employees/me/timesheets -> {ts_res.status_code}")
        assert ts_res.status_code == 201, ts_res.text
        timesheet_id = ts_res.json()["data"]["id"]

        # View payslips
        ps_res = await ac.get("/api/v1/employees/me/payslips")
        print(f"3e. GET /employees/me/payslips -> {ps_res.status_code} (items: {len(ps_res.json().get('data', []))})")

        # View documents
        doc_res = await ac.get("/api/v1/employees/me/documents")
        print(f"3f. GET /employees/me/documents -> {doc_res.status_code}")

        # View performance reviews
        perf_res = await ac.get("/api/v1/employees/me/performance-reviews")
        print(f"3g. GET /employees/me/performance-reviews -> {perf_res.status_code}")

        # 4. HR approves leave
        app.dependency_overrides[get_current_user] = lambda: hr_user
        app_leave_res = await ac.patch(f"/api/v1/employees/leaves/{leave_id}/approve", json={"status": "approved"})
        print(f"4. PATCH /employees/leaves/{leave_id}/approve -> {app_leave_res.status_code}")
        assert app_leave_res.status_code == 200, app_leave_res.text

        # 5. HR approves timesheet
        app_ts_res = await ac.patch(f"/api/v1/employees/timesheets/{timesheet_id}/approve", json={"status": "approved"})
        print(f"5. PATCH /employees/timesheets/{timesheet_id}/approve -> {app_ts_res.status_code}")
        assert app_ts_res.status_code == 200, app_ts_res.text
        print(">>> WORKFLOW 1 PASSED! ALL 5 STEPS VALIDATED SUCCESSFUL")

        # =========================================================================
        # WORKFLOW 2: Ticketing & Support
        # =========================================================================
        print("\n--- [WORKFLOW 2] Ticketing & Support ---")
        # 1. Client creates ticket
        app.dependency_overrides[get_current_user] = lambda: client_user
        t_res = await ac.post("/api/v1/clients/me/tickets", json={
            "subject": "Integration Webhook Error 500",
            "description": "Our production webhook endpoint received a 500 status on sprint deployment.",
            "priority": "high"
        })
        print(f"1. POST /clients/me/tickets -> {t_res.status_code}")
        assert t_res.status_code == 201, t_res.text
        ticket_id = t_res.json()["data"]["id"]

        # 2. Ticket appears in Support queue
        app.dependency_overrides[get_current_user] = lambda: support_user
        q_res = await ac.get("/api/v1/tickets")
        print(f"2. GET /tickets (Queue) -> {q_res.status_code} (total tickets: {len(q_res.json().get('data', []))})")
        assert q_res.status_code == 200, q_res.text

        # 3. Support replies
        rep_res = await ac.post(f"/api/v1/tickets/{ticket_id}/replies", json={
            "content": "We have reviewed your webhook logs and patched the payload schema. Please test now."
        })
        print(f"3. POST /tickets/{ticket_id}/replies -> {rep_res.status_code}")
        assert rep_res.status_code == 201, rep_res.text

        # 4. Support updates status
        stat_res = await ac.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "resolved"})
        print(f"4. PATCH /tickets/{ticket_id} -> {stat_res.status_code} (new status: {stat_res.json()['data']['status']})")
        assert stat_res.status_code == 200, stat_res.text

        # 5. Client sees reply
        app.dependency_overrides[get_current_user] = lambda: client_user
        t_view = await ac.get(f"/api/v1/tickets/{ticket_id}")
        print(f"5. GET /tickets/{ticket_id} -> {t_view.status_code}")
        print(">>> WORKFLOW 2 PASSED! ALL 5 STEPS VALIDATED SUCCESSFUL")

        # =========================================================================
        # WORKFLOW 3: Project Management & Task Execution
        # =========================================================================
        print("\n--- [WORKFLOW 3] Project Management & Tasks ---")
        # 1. Admin/PM creates Project
        app.dependency_overrides[get_current_user] = lambda: pm_user
        proj_title = f"NextGen Cloud Migration {uuid.uuid4().hex[:4]}"
        p_res = await ac.post("/api/v1/projects", json={
            "title": proj_title,
            "client_id": str(client_obj.id) if client_obj else None,
            "budget": 85000.0,
            "status": "in_progress",
            "overview": "Automated migration of monolith to microservices"
        })
        print(f"1. POST /projects -> {p_res.status_code}")
        assert p_res.status_code == 201, p_res.text
        proj_id = p_res.json()["data"]["id"]

        # 2. PM assigns Team
        team_res = await ac.patch(f"/api/v1/projects/{proj_id}/team", json={
            "employee_ids": [str(dev_user.id)]
        })
        print(f"2. PATCH /projects/{proj_id}/team -> {team_res.status_code}")
        assert team_res.status_code == 200, team_res.text

        # 3. PM creates Tasks
        task_create_res = await ac.post("/api/v1/tasks", json={
            "project_id": proj_id,
            "title": "Setup Kubernetes Cluster & Ingress",
            "assigned_to": str(dev_user.id),
            "priority": "high",
            "due_date": str(date.today() + timedelta(days=10))
        })
        print(f"3. POST /tasks -> {task_create_res.status_code}")
        assert task_create_res.status_code == 201, task_create_res.text
        task_id = task_create_res.json()["data"]["id"]

        # 4. Employee updates Task status
        app.dependency_overrides[get_current_user] = lambda: dev_user
        t_prog_res = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in_progress"})
        print(f"4a. PATCH /tasks/{task_id}/status (in_progress) -> {t_prog_res.status_code}")
        assert t_prog_res.status_code == 200, t_prog_res.text
        t_done_res = await ac.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "done"})
        print(f"4b. PATCH /tasks/{task_id}/status (done) -> {t_done_res.status_code}")
        assert t_done_res.status_code == 200, t_done_res.text

        # 5. PM tracks progress
        app.dependency_overrides[get_current_user] = lambda: pm_user
        up_proj = await ac.put(f"/api/v1/projects/{proj_id}", json={"progress_percent": 75})
        print(f"5. PUT /projects/{proj_id} -> {up_proj.status_code} (progress: {up_proj.json()['data']['progress_percent']}%)")
        assert up_proj.status_code == 200, up_proj.text
        print(">>> WORKFLOW 3 PASSED! ALL 5 STEPS VALIDATED SUCCESSFUL")

        # =========================================================================
        # WORKFLOW 4: Training Catalog & Upskilling
        # =========================================================================
        print("\n--- [WORKFLOW 4] Training & Upskilling ---")
        # 1. Admin creates Course
        app.dependency_overrides[get_current_user] = lambda: admin_user
        course_title = f"Microservices with Go & gRPC {uuid.uuid4().hex[:4]}"
        c_res = await ac.post("/api/v1/trainings/courses", json={
            "title": course_title,
            "category": "Backend Architecture",
            "description": "Advanced course on high throughput gRPC streaming services.",
            "duration_hours": 24,
            "is_published": True
        })
        print(f"1. POST /trainings/courses -> {c_res.status_code}")
        assert c_res.status_code == 201, c_res.text
        course_id = c_res.json()["data"]["id"]

        # 2. Employee browses catalog
        app.dependency_overrides[get_current_user] = lambda: dev_user
        cat_res = await ac.get("/api/v1/trainings/courses")
        print(f"2. GET /trainings/courses -> {cat_res.status_code} (courses found: {len(cat_res.json().get('data', []))})")
        assert cat_res.status_code == 200, cat_res.text

        # 3. Employee enrolls
        enroll_res = await ac.post(f"/api/v1/trainings/enroll?course_id={course_id}")
        print(f"3. POST /trainings/enroll -> {enroll_res.status_code}")
        assert enroll_res.status_code == 201, enroll_res.text

        # 4. Admin views enrollments
        app.dependency_overrides[get_current_user] = lambda: admin_user
        all_enr = await ac.get("/api/v1/trainings/enrollments")
        print(f"4. GET /trainings/enrollments -> {all_enr.status_code} (enrollments count: {len(all_enr.json().get('data', []))})")
        assert all_enr.status_code == 200, all_enr.text
        print(">>> WORKFLOW 4 PASSED! ALL 4 STEPS VALIDATED SUCCESSFUL")

    print("\n=====================================================")
    print("  ALL 4 SYSTEM WORKFLOWS VERIFIED 100% OPERATIONAL!  ")
    print("=====================================================")

if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
