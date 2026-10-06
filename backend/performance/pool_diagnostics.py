"""Samples pg_stat_activity on a fixed interval from a connection OUTSIDE the
app's own pool, so it never competes with the load under test. Used to
directly answer "is the DB connection pool saturated during this benchmark,
or is something else the bottleneck?" — with numbers from Postgres' own
bookkeeping, not inference from application-side latency alone.

Usage:
    python performance/pool_diagnostics.py --host localhost --port 55450 \
        --db corefusion_test --user test_user --password test_pass \
        --duration 20 --interval 0.5
"""
import argparse
import asyncio
import json
import time

import asyncpg


async def sample_loop(dsn: str, duration: float, interval: float, out_path: str):
    samples = []
    conn = await asyncpg.connect(dsn)
    try:
        start = time.time()
        while time.time() - start < duration:
            rows = await conn.fetch(
                """
                SELECT state, count(*) AS n
                FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                GROUP BY state
                """
            )
            max_conn_row = await conn.fetchrow("SHOW max_connections")
            total_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
            samples.append({
                "t": round(time.time() - start, 2),
                "by_state": {r["state"]: r["n"] for r in rows},
                "total_connections": total_row["n"],
                "max_connections": int(max_conn_row["max_connections"]),
            })
            await asyncio.sleep(interval)
    finally:
        await conn.close()

    with open(out_path, "w") as f:
        json.dump(samples, f, indent=2)

    if samples:
        peak_total = max(s["total_connections"] for s in samples)
        peak_active = max(s["by_state"].get("active", 0) for s in samples)
        max_conn = samples[0]["max_connections"]
        print(f"pg_stat_activity summary over {len(samples)} samples:")
        print(f"  peak total connections from this app's DB user: {peak_total} / server max_connections={max_conn}")
        print(f"  peak 'active' (actually executing a query) connections: {peak_active}")
        print(f"  -> {'SATURATED' if peak_total >= max_conn * 0.9 else 'not saturated'} at server max_connections level")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--db", default="corefusion_test")
    parser.add_argument("--user", default="test_user")
    parser.add_argument("--password", default="test_pass")
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--out", default="pool_samples.json")
    args = parser.parse_args()

    dsn = f"postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
    asyncio.run(sample_loop(dsn, args.duration, args.interval, args.out))
