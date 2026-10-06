"""Regression test for the cross-worker rate-limit bypass fixed this session.

Root cause: slowapi's default Limiter storage is in-memory and therefore
per-process. gunicorn runs 4 workers (docker/Dockerfile), so an in-memory
limiter enforces "10/minute" independently in each worker — effectively
~4x more permissive than configured. Verified live with two real OS
processes sharing a real Redis: combined they were held to the single
configured limit, not 4x it (see status.md for the full drill).

This test can't spin up gunicorn workers, but it guards the one thing that
matters for regression purposes: the limiter must be configured to use a
shared (Redis) backend, not fall back to in-memory storage.
"""
from app.core.limiter import limiter


def test_limiter_uses_shared_redis_storage_not_in_memory():
    storage_type = type(limiter._storage).__name__
    assert "Redis" in storage_type, (
        f"Limiter storage is {storage_type}, not Redis-backed — in a multi-worker "
        "deployment this silently multiplies every rate limit by the worker count."
    )


def test_limiter_fails_open_on_storage_errors():
    # Availability > strict rate limiting during a Redis outage — every
    # endpoint still enforces auth/RBAC independently of rate limiting.
    assert limiter._swallow_errors is True
