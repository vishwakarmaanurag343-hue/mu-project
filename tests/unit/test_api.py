"""Unit tests for FastAPI endpoints, security headers, SPA fallback, and exception handling."""

import pytest
from fastapi.testclient import TestClient

from alphalens.api.main import create_app
from alphalens.config import get_settings


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for unit tests."""
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint(client: TestClient) -> None:
    """GET /api/health should return 200 with status and version."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_security_headers_present(client: TestClient) -> None:
    """Security headers must be present on /api/health and on root."""
    response = client.get("/api/health")
    assert "content-security-policy" in response.headers
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "x-request-id" in response.headers

    # Root route
    root_response = client.get("/")
    assert "content-security-policy" in root_response.headers
    assert root_response.headers["x-content-type-options"] == "nosniff"


def test_strict_transport_security_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """HSTS header should only appear when app_env is prod."""
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")

    prod_app = create_app()
    prod_client = TestClient(prod_app)
    response = prod_client.get("/api/health")

    get_settings.cache_clear()
    assert "strict-transport-security" in response.headers
    assert "max-age=31536000" in response.headers["strict-transport-security"]


def test_unknown_api_route_returns_404_json(client: TestClient) -> None:
    """Unknown /api route must return 404 JSON, not HTML index."""
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "detail" in data


def test_global_exception_handler() -> None:
    """Global exception handler returns generic JSON without traceback."""
    get_settings.cache_clear()

    # Create app and register route BEFORE spa_fallback would intercept, or use route decorator
    app = create_app()

    # Prepend route to router so it evaluates before catch-all
    @app.get("/api/test-error")
    async def trigger_error() -> None:
        raise RuntimeError("Secret internal failure with sensitive details")

    # Move this new route before the catch-all in router routes
    error_route = app.router.routes.pop()
    app.router.routes.insert(0, error_route)

    err_client = TestClient(app, raise_server_exceptions=False)
    response = err_client.get("/api/test-error")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal error"
    assert "request_id" in data
    assert "Secret internal failure" not in response.text


def test_spa_fallback(client: TestClient) -> None:
    """Non-API routes should serve the SPA index.html when frontend/dist is built."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "AlphaLens" in response.text
