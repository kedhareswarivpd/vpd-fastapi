"""Automated ROLE x ENDPOINT x ACTION matrix — generated from the app's own
resolved dependency graph at runtime, not hand-maintained.

Why runtime introspection instead of parsing `require_roles(...)` calls out
of source text: some routers declare the dependency at the router level
(`APIRouter(dependencies=[Depends(require_roles(...))])`), which a per-route
decorator regex misses entirely. Walking `app.routes[i].dependant.dependencies`
after FastAPI has already resolved everything (including router-level and
nested dependencies) is the only reliable source of truth for "what does
this endpoint actually require".

For every route carrying a `require_roles(*roles)` dependency, and for every
one of the 13 roles in `UserRole`, this asserts:
  - a role IN the allowed set is never rejected for authorization (may still
    404/422/other on business logic — that's fine, this test only asserts
    the AuthZ decision, not full request success)
  - a role NOT in the allowed set gets 403
  - no token at all gets 401
  - `super_admin` always passes (bypasses require_roles by design — see
    core/dependencies.py) regardless of the endpoint's configured role list

This does not exercise object-level/tenant ownership checks (those are
covered separately by tests/test_authorization_regression.py and
tests/real_db_verification.py) — this is specifically the ROLE layer.
"""
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio.exc import AsyncMethodRequired

from app.core.dependencies import get_current_user
from app.main import app
from app.models.enums import UserRole

ALL_ROLES = [r.value for r in UserRole]


def _extract_roles(dep_call):
    if not hasattr(dep_call, "__closure__") or dep_call.__closure__ is None:
        return None
    freevars = dep_call.__code__.co_freevars
    if "roles" not in freevars:
        return None
    idx = freevars.index("roles")
    return dep_call.__closure__[idx].cell_contents


def _iter_role_restricted_routes():
    for route in app.routes:
        if not hasattr(route, "dependant"):
            continue
        roles = None
        for d in route.dependant.dependencies:
            r = _extract_roles(d.call)
            if r:
                roles = r
        if roles is None:
            continue
        for method in route.methods or ["GET"]:
            if method in ("HEAD", "OPTIONS"):
                continue
            yield (method, route.path, tuple(roles))


ROLE_RESTRICTED_ROUTES = sorted(set(_iter_role_restricted_routes()))


def _placeholder_path(path: str) -> str:
    """Fill {param} placeholders with a syntactically valid UUID so routing
    matches — the specific value doesn't matter since we're asserting the
    AuthZ decision (401/403 vs "got past AuthZ"), not the business result."""
    import re
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _fake_user(role: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), role=role, is_active=True)


_PASSED_AUTHZ_MOCK_ARTIFACT = -1  # sentinel: request got past require_roles() into query
# execution, where the mocked MagicMock-backed engine (see tests/conftest.py) then chokes on
# some query shapes with AsyncMethodRequired — a known, pre-existing test-harness limitation
# unrelated to authorization (same root cause as TestBlogEndpoints::test_list_blogs). Since this
# file is specifically testing the AuthZ decision, reaching query execution at all already proves
# authorization passed, regardless of what the mocked DB does afterward.


async def _authz_status(client: AsyncClient, method: str, path: str) -> int:
    try:
        resp = await client.request(method, path)
        return resp.status_code
    except AsyncMethodRequired:
        return _PASSED_AUTHZ_MOCK_ARTIFACT


class TestRBACMatrix:
    @pytest.mark.parametrize("method,path,allowed_roles", ROLE_RESTRICTED_ROUTES)
    async def test_no_token_is_rejected(self, client, method, path, allowed_roles):
        async with client as c:
            status = await _authz_status(c, method, _placeholder_path(path))
        assert status == 401, f"{method} {path} allowed an unauthenticated request (expected 401, got {status})"

    @pytest.mark.parametrize("method,path,allowed_roles", ROLE_RESTRICTED_ROUTES)
    async def test_super_admin_always_passes_authz(self, client, method, path, allowed_roles):
        app.dependency_overrides[get_current_user] = lambda: _fake_user("super_admin")
        try:
            async with client as c:
                status = await _authz_status(c, method, _placeholder_path(path))
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert status not in (401, 403), (
            f"{method} {path}: super_admin was rejected at the AuthZ layer (status={status}) — "
            "super_admin must bypass require_roles() by design"
        )

    @pytest.mark.parametrize("method,path,allowed_roles", ROLE_RESTRICTED_ROUTES)
    async def test_disallowed_roles_get_403(self, client, method, path, allowed_roles):
        disallowed = [r for r in ALL_ROLES if r not in allowed_roles and r != "super_admin"]
        for role in disallowed:
            app.dependency_overrides[get_current_user] = lambda role=role: _fake_user(role)
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    status = await _authz_status(c, method, _placeholder_path(path))
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert status == 403, (
                f"{method} {path}: role={role!r} (not in allowed={allowed_roles}) got status={status}, expected 403"
            )

    @pytest.mark.parametrize("method,path,allowed_roles", ROLE_RESTRICTED_ROUTES)
    async def test_allowed_roles_pass_authz(self, client, method, path, allowed_roles):
        for role in allowed_roles:
            app.dependency_overrides[get_current_user] = lambda role=role: _fake_user(role)
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    status = await _authz_status(c, method, _placeholder_path(path))
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert status not in (401, 403), (
                f"{method} {path}: allowed role={role!r} was rejected at the AuthZ layer (status={status})"
            )


def test_matrix_is_not_empty():
    """Guard against the introspection itself silently breaking (e.g. after
    a require_roles() signature change) and this whole file going quiet."""
    assert len(ROLE_RESTRICTED_ROUTES) >= 20, (
        f"Only found {len(ROLE_RESTRICTED_ROUTES)} role-restricted routes — "
        "expected 30+; the runtime introspection may be broken."
    )
