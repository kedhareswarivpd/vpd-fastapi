"""Systematic pool_size × worker-count matrix test for CF-BE-009's remaining
gap. For each combination: hits GET /api/v1/employees?limit=100 at a fixed
concurrency (25 — the level where the previous benchmark first failed <200ms)
while sampling pg_stat_activity concurrently, to see whether Postgres
connections are actually saturated (pool exhaustion) or not (something else
— app CPU, event-loop scheduling, Docker Desktop virtualization overhead).

Requires: an already-running target server at --target-url, and the DB
credentials to open a monitoring connection.
"""
import argparse
import asyncio
import statistics
import time

import asyncpg
import httpx
from jose import jwt


async def sample_pg(dsn: str, duration: float, results: dict):
    conn = await asyncpg.connect(dsn)
    peak_total = 0
    peak_active = 0
    try:
        start = time.time()
        while time.time() - start < duration:
            row = await conn.fetchrow(
                "SELECT count(*) FILTER (WHERE state='active') AS active, count(*) AS total "
                "FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
            peak_total = max(peak_total, row["total"])
            peak_active = max(peak_active, row["active"])
            await asyncio.sleep(0.1)
    finally:
        await conn.close()
    results["peak_total_connections"] = peak_total
    results["peak_active_connections"] = peak_active


async def hammer(base_url: str, headers: dict, concurrency: int, total: int, results: dict):
    latencies = []
    errors = 0
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)
    async with httpx.AsyncClient(base_url=base_url, limits=limits, timeout=15) as client:
        sem = asyncio.Semaphore(concurrency)

        async def one():
            nonlocal errors
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.get("/api/v1/employees?limit=100", headers=headers)
                    if r.status_code != 200:
                        errors += 1
                except Exception:
                    errors += 1
                latencies.append((time.perf_counter() - t0) * 1000)

        await asyncio.gather(*[one() for _ in range(total)])
    latencies.sort()
    n = len(latencies)
    results["p50"] = statistics.median(latencies)
    results["p95"] = latencies[max(0, int(n * 0.95) - 1)]
    results["p99"] = latencies[max(0, int(n * 0.99) - 1)]
    results["max"] = max(latencies)
    results["errors"] = errors


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--admin-id", required=True)
    parser.add_argument("--jwt-secret", default="load-test-secret")
    parser.add_argument("--dsn", required=True, help="postgresql://user:pass@host:port/db for monitoring")
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    payload = {"sub": args.admin_id, "aud": "authenticated", "email": "admin@example.com", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, args.jwt_secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    results = {}
    pg_results = {}
    await asyncio.gather(
        hammer(args.target_url, headers, args.concurrency, args.requests, results),
        sample_pg(args.dsn, 15, pg_results),
    )

    print(f"\n=== {args.label} ===")
    print(f"  latency: p50={results['p50']:.1f}ms p95={results['p95']:.1f}ms p99={results['p99']:.1f}ms max={results['max']:.1f}ms errors={results['errors']}")
    print(f"  pg_stat_activity: peak_total_connections={pg_results['peak_total_connections']} peak_active={pg_results['peak_active_connections']}")
    status = "PASS" if results["p95"] < 200 and results["errors"] == 0 else "FAIL"
    print(f"  <200ms gate: {status}")
    return {"label": args.label, **results, **pg_results, "status": status}


if __name__ == "__main__":
    asyncio.run(main())
