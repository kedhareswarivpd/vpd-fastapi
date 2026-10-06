from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Patch create_async_engine at the source BEFORE any app module is imported
# This prevents the engine from trying to connect to a real PostgreSQL database
source_patcher = patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=MagicMock())
source_patcher.start()

from app.core.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402

# Disable the rate limiter for the mocked test suite entirely (not just point
# it at a fake host). `settings.redis_host` defaults to a real Redis port,
# so without this every pytest run in this repo was silently connecting to
# and accumulating hits against a real, unrelated Redis instance on this
# machine — eventually tripping a real 429 in an unrelated test after enough
# accumulated runs. Pointing at an unreachable host instead (tried first)
# fixed the contamination but made every single test pay a real connection-
# attempt cost via the global SlowAPIMiddleware, ~5x'ing total suite runtime.
# `enabled = False` skips all limiter logic before any network call is made —
# fixes both problems. Rate limiting itself is verified separately, for real,
# against a real Redis (tests/test_rate_limit_config.py,
# tests/real_db_verification.py, and the live-outage drill in status.md).
limiter.enabled = False

# backend/.env sets STORAGE_BACKEND=s3 (routing uploads through the local
# MinIO container per this deployment's setup) — but the existing disk-based
# upload tests (tests/test_uploads.py) intentionally exercise the "local"
# code path's validation logic directly against a tmp_path, not a real/mocked
# S3 endpoint. Forcing "local" for the whole mocked test session keeps that
# coverage meaningful; the S3 code path has its own dedicated tests
# (tests/test_storage_service.py) that mock boto3 instead of hitting a real
# bucket, and a real MinIO round trip is verified separately by hand against
# the live Docker stack (see status.md), not by this suite.
from app.core.config import settings as _settings  # noqa: E402

_settings.storage_backend = "local"

# backend/.env holds a REAL Brevo API key (Brevo serves both local dev and
# staging per explicit instruction). send_email() (app/services/email_service.py)
# already no-ops safely whenever brevo_api_key is blank — forcing it blank
# here is enough to prevent any real network call to api.brevo.com from the
# mocked test suite, with no need to patch httpx itself. (An earlier version
# of this fixture patched `app.services.email_service.httpx.AsyncClient`
# directly — that broke nearly every RBAC-matrix test, because
# email_service's `httpx` name IS the same shared `httpx` module every other
# test's `from httpx import AsyncClient` resolves to; patching an attribute
# on a shared module patches it everywhere, not just in email_service.)
_settings.brevo_api_key = ""


@pytest.fixture
def test_app():
    return app


@pytest.fixture
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


