import pytest
from httpx import ASGITransport, AsyncClient

import app
from app.main import app as main_app


def test_package_exports_fastapi_app():
    assert app.app is main_app


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_requires_valid_email():
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Test User", "email": "not-an-email", "password": "password123"},
        )
    assert response.status_code == 422
