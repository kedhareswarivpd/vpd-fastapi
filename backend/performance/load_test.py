"""Reproducible concurrent load-test harness for CoreFusion (§16-25 of the
backend remediation directive).

No k6/Locust in this environment and no permission to install arbitrary
system tools mid-session — so this is a pure-Python asyncio+httpx harness
instead. It is a REAL harness, not a workaround: it drives a live uvicorn
process (not in-process ASGI), over real TCP sockets, against a real
Postgres, with real concurrency and a genuinely minted, signature-valid
Supabase-style JWT (HS256, signed with the same SUPABASE_JWT_SECRET the
server verifies against) — so authenticated endpoints are exercised for
real, not skipped.

Usage (server, DB, and dataset are all managed by this script):
    ENV=test DB_HOST=localhost DB_PORT=<port> DB_NAME=... DB_USER=... DB_PASS=... \
    SUPABASE_URL=http://localhost:1 SUPABASE_JWT_SECRET=load-test-secret \
    python performance/load_test.py

What it measures, honestly labeled:
  - Dataset size actually seeded (printed, not assumed).
  - Concurrency levels actually run: 1, 5, 10, 25, 50.
  - p50/p95/p99/max latency and error rate per endpoint per concurrency level.

What it does NOT claim:
  - This is single-machine, same-host client+server (no real network/CDN
    latency, no multi-region, no production hardware). Numbers are a lower
    bound on real production latency, not an upper bound — a slow endpoint
    here is real evidence of a problem; a fast endpoint here does not by
    itself guarantee production performance under WAN conditions.
"""
import argparse
import asyncio
import statistics
import subprocess
import sys
import time
import uuid

import httpx
from jose import jwt
from sqlalchemy import text

sys.path.insert(0, ".")

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.user import User  # noqa: E402

SERVER_PORT = 8951
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"


def mint_token(user_id: uuid.UUID) -> str:
    """A genuinely signature-valid token for decode_supabase_token()'s HS256
    path — signed with the same secret the server verifies against, exactly
    the trust boundary Supabase itself would produce, just without a real
    Supabase project."""
    payload = {"sub": str(user_id), "aud": "authenticated", "email": f"{user_id}@example.com",
               "exp": int(time.time()) + 3600}
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


async def seed(n_employees: int, n_projects: int, n_tasks: int) -> uuid.UUID:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        dept = Department(name=f"LoadTest-{uuid.uuid4().hex[:6]}")
        db.add(dept)
        await db.flush()

        admin_id = uuid.uuid4()
        await db.execute(text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": str(admin_id)})
        admin = User(id=admin_id, name="Load Test Admin", email=f"loadtest-admin-{admin_id.hex[:8]}@example.com", role="admin", is_active=True, is_email_verified=True)
        db.add(admin)

        employees = []
        for _ in range(n_employees):
            uid = uuid.uuid4()
            await db.execute(text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": str(uid)})
            u = User(id=uid, name=f"Emp {uid.hex[:6]}", email=f"emp-{uid.hex[:8]}@example.com", role="employee", is_active=True, is_email_verified=True)
            db.add(u)
            await db.flush()
            e = Employee(user_id=u.id, employee_code=f"EMP-{uid.hex[:8]}", department_id=dept.id, designation="Engineer")
            db.add(e)
            employees.append(e)
        await db.flush()

        client_uid = uuid.uuid4()
        await db.execute(text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": str(client_uid)})
        client_user = User(id=client_uid, name="Load Test Client", email=f"client-{client_uid.hex[:8]}@example.com", role="client", is_active=True, is_email_verified=True)
        db.add(client_user)
        await db.flush()
        client = Client(user_id=client_user.id, company_name="Load Test Co")
        db.add(client)
        await db.flush()

        projects = []
        for i in range(n_projects):
            title = f"Load Test Project {i}-{uuid.uuid4().hex[:6]}"
            p = Project(title=title, slug=title.lower().replace(" ", "-"), client_id=client.id, status="in_progress", is_published=True)
            db.add(p)
            projects.append(p)
        await db.flush()

        for i in range(n_tasks):
            db.add(Task(project_id=projects[i % len(projects)].id, title=f"Task {i}", assigned_to=employees[i % len(employees)].user_id, status="todo"))

        await db.commit()
        print(f"Seeded: {n_employees} employees, {n_projects} projects, {n_tasks} tasks, 1 admin user")
        return admin.id


async def hit(client: httpx.AsyncClient, method: str, path: str, headers: dict) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, path, headers=headers, timeout=10)
        return resp.status_code, (time.perf_counter() - t0) * 1000, ""
    except Exception as exc:
        return -1, (time.perf_counter() - t0) * 1000, f"{type(exc).__name__}: {exc}"


async def run_concurrency_level(client: httpx.AsyncClient, endpoint_path: str, headers: dict, concurrency: int, total_requests: int):
    latencies = []
    errors = 0
    error_samples = []
    sem = asyncio.Semaphore(concurrency)

    async def one():
        nonlocal errors
        async with sem:
            status, ms, err = await hit(client, "GET", endpoint_path, headers)
            if status != 200:
                errors += 1
                if len(error_samples) < 3:
                    error_samples.append(f"status={status} {err}")
            latencies.append(ms)

    await asyncio.gather(*[one() for _ in range(total_requests)])
    if error_samples:
        print(f"    sample errors: {error_samples}")

    latencies.sort()
    n = len(latencies)
    return {
        "concurrency": concurrency,
        "requests": total_requests,
        "errors": errors,
        "p50": statistics.median(latencies),
        "p95": latencies[max(0, int(n * 0.95) - 1)],
        "p99": latencies[max(0, int(n * 0.99) - 1)],
        "max": max(latencies),
    }


async def main():
    global BASE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--employees", type=int, default=500)
    parser.add_argument("--projects", type=int, default=200)
    parser.add_argument("--tasks", type=int, default=1000)
    parser.add_argument("--requests-per-level", type=int, default=40)
    parser.add_argument("--target-url", default=None, help="Hit an already-running server (e.g. the real gunicorn+4-worker Docker container) instead of spawning a local dev uvicorn process.")
    args = parser.parse_args()

    admin_id = await seed(args.employees, args.projects, args.tasks)
    await engine.dispose()
    token = mint_token(admin_id)
    headers = {"Authorization": f"Bearer {token}"}

    proc = None
    if args.target_url:
        BASE_URL = args.target_url
        print(f"\nTargeting already-running server at {BASE_URL} (not spawning a local process)...")
    else:
        print(f"\nStarting live uvicorn server on :{SERVER_PORT} (real TCP, real Postgres, single dev-mode uvicorn process)...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(SERVER_PORT), "--log-level", "warning"],
        )
    try:
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            for _ in range(60):
                try:
                    r = await client.get("/health", timeout=2)
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            else:
                raise RuntimeError("Server did not become healthy in time")

        endpoints = [
            ("GET /health (no auth, no DB)", "/health", {}),
            ("GET /ready (DB check)", "/ready", {}),
            (f"GET /api/v1/employees?limit=100 ({args.employees} seeded rows)", "/api/v1/employees?limit=100", headers),
            (f"GET /api/v1/projects ({args.projects} seeded rows)", "/api/v1/projects", headers),
            ("GET /api/v1/auth/me", "/api/v1/auth/me", headers),
        ]

        print(f"\n{'='*100}")
        print(f"Dataset: {args.employees} employees, {args.projects} projects, {args.tasks} tasks")
        print(f"{'='*100}")

        all_results = []
        limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)
        async with httpx.AsyncClient(base_url=BASE_URL, limits=limits, timeout=15) as load_client:
            for label, path, hdrs in endpoints:
                print(f"\n--- {label} ---")
                print(f"{'Concurrency':>12} {'p50 ms':>10} {'p95 ms':>10} {'p99 ms':>10} {'max ms':>10} {'errors':>8}")
                for concurrency in (1, 5, 10, 25, 50):
                    result = await run_concurrency_level(load_client, path, hdrs, concurrency, args.requests_per_level)
                    status = "PASS" if result["p95"] < 200 and result["errors"] == 0 else "FAIL"
                    print(f"{concurrency:>12} {result['p50']:>10.1f} {result['p95']:>10.1f} {result['p99']:>10.1f} {result['max']:>10.1f} {result['errors']:>8}  {status}")
                    all_results.append((label, result, status))

        print(f"\n{'='*100}")
        failures = [r for r in all_results if r[2] == "FAIL"]
        print(f"{len(all_results) - len(failures)}/{len(all_results)} (endpoint, concurrency) combinations PASS (p95 < 200ms, 0 errors)")
        if failures:
            print("FAILING combinations:")
            for label, result, _ in failures:
                print(f"  {label} @ concurrency={result['concurrency']}: p95={result['p95']:.1f}ms errors={result['errors']}")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
