from fastapi.testclient import TestClient

from app.main import app, normalize_allowed_origins


def test_normalize_allowed_origins_removes_trailing_slashes_and_duplicates():
    origins = [
        "https://cf-azure-eta.vercel.app/",
        " https://cf-azure-eta.vercel.app ",
        "http://localhost:5173",
        "",
        "http://localhost:5173/",
        "https://www.corefusiontech.com",
        "https://www.corefusiontech.com/",
    ]

    assert normalize_allowed_origins(origins) == [
        "https://cf-azure-eta.vercel.app",
        "http://localhost:5173",
        "https://www.corefusiontech.com",
    ]


def test_api_missing_route_returns_json_not_html():
    client = TestClient(app)
    response = client.get("/api/v1/definitely-not-real")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["success"] is False
    assert payload["status_code"] == 404
    assert "message" in payload
