"""Unit tests for user registration, authentication, token rotation, and CSRF protection."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alphalens.api.deps import get_db
from alphalens.api.main import create_app
from alphalens.api.routes.auth import limiter
from alphalens.db.models import Base, RefreshToken, User

# In-memory SQLite engine isolated for tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    """Provide an isolated test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database_and_limits() -> Generator[None, None, None]:
    """Create fresh in-memory schema and reset rate limits for every test."""
    Base.metadata.create_all(bind=test_engine)
    limiter.reset()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> TestClient:
    """Create a test client with dependency overrides."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=False)


def test_register_login_me_logout_flow(client: TestClient) -> None:
    """Full lifecycle: Register -> Login -> Me -> Logout."""
    reg_payload = {"email": "trader@example.com", "password": "supersecretpassword123"}

    # 1. Register without CSRF fails
    res_no_csrf = client.post("/api/auth/register", json=reg_payload)
    assert res_no_csrf.status_code == 403

    # Set CSRF cookie and header
    csrf_token = "valid-test-csrf-token"
    client.cookies.set("csrf_token", csrf_token, domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": csrf_token}

    # 2. Register succeeds
    res_reg = client.post("/api/auth/register", json=reg_payload, headers=headers)
    assert res_reg.status_code == 200
    user_data = res_reg.json()
    assert user_data["email"] == "trader@example.com"
    assert "password_hash" not in user_data

    # 3. Login succeeds and sets cookies
    login_payload = {"email": "trader@example.com", "password": "supersecretpassword123"}
    res_login = client.post("/api/auth/login", json=login_payload, headers=headers)
    assert res_login.status_code == 200
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies

    # Find the issued CSRF token
    cookie_val = client.cookies.get("csrf_token", domain="testserver.local", path="/")
    assert cookie_val is not None
    auth_headers = {"X-CSRF-Token": cookie_val}

    # 4. GET /api/auth/me succeeds with cookie
    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "trader@example.com"

    # 5. Logout clears cookies and revokes session
    res_logout = client.post("/api/auth/logout", headers=auth_headers)
    assert res_logout.status_code == 200


def test_invalid_credentials_generic_error(client: TestClient) -> None:
    """Login failures must return an identical generic error message."""
    client.cookies.set("csrf_token", "test-csrf", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "test-csrf"}

    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123456"},
        headers=headers,
    )

    # Wrong password
    res_wrong_pw = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrongpassword123"},
        headers=headers,
    )
    assert res_wrong_pw.status_code == 401
    assert res_wrong_pw.json()["detail"] == "Invalid email or password"

    # Nonexistent email
    res_wrong_email = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123456"},
        headers=headers,
    )
    assert res_wrong_email.status_code == 401
    assert res_wrong_email.json()["detail"] == "Invalid email or password"


def test_password_policy_min_12_chars(client: TestClient) -> None:
    """Passwords with fewer than 12 characters are rejected."""
    client.cookies.set("csrf_token", "test-csrf", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "test-csrf"}

    res = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short"},
        headers=headers,
    )
    assert res.status_code == 422


def test_password_is_argon2_and_never_leaked(client: TestClient) -> None:
    """Password hash in the DB uses Argon2id format and is never exposed in API responses."""
    client.cookies.set("csrf_token", "test-csrf", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "test-csrf"}

    res = client.post(
        "/api/auth/register",
        json={"email": "argon2user@example.com", "password": "securepassword123"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "password_hash" not in res.json()

    with TestingSessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "argon2user@example.com"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")


def test_expired_access_token_rejected(client: TestClient) -> None:
    """Expired access token raises 401."""
    client.cookies.set("access_token", "invalid-or-expired-token")
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_refresh_token_rotation_and_reuse_revocation(client: TestClient) -> None:
    """Refresh tokens are rotated on each refresh; replaying an old token revokes all sessions."""
    client.cookies.set("csrf_token", "test-csrf", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "test-csrf"}

    # Register & login
    client.post(
        "/api/auth/register",
        json={"email": "rotator@example.com", "password": "strongpassword123"},
        headers=headers,
    )
    res_login = client.post(
        "/api/auth/login",
        json={"email": "rotator@example.com", "password": "strongpassword123"},
        headers=headers,
    )
    assert res_login.status_code == 200

    initial_refresh = client.cookies.get(
        "refresh_token", domain="testserver.local", path="/api/auth/refresh"
    )
    assert initial_refresh is not None

    csrf_val = client.cookies.get("csrf_token", domain="testserver.local", path="/")
    assert csrf_val is not None
    refresh_headers = {"X-CSRF-Token": csrf_val}

    # First refresh: succeeds and rotates token
    res_refresh = client.post("/api/auth/refresh", headers=refresh_headers)
    assert res_refresh.status_code == 200
    rotated_refresh = client.cookies.get(
        "refresh_token", domain="testserver.local", path="/api/auth/refresh"
    )
    assert rotated_refresh != initial_refresh

    # REUSE ATTACK SIMULATION: Replay the initial refresh token
    new_csrf = client.cookies.get("csrf_token", domain="testserver.local", path="/")
    assert new_csrf is not None
    client.cookies.set(
        "refresh_token", initial_refresh, domain="testserver.local", path="/api/auth/refresh"
    )
    res_reuse = client.post("/api/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert res_reuse.status_code == 401
    assert "Token reuse detected" in res_reuse.json()["detail"]

    # Verify all tokens for user are now revoked in DB
    with TestingSessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "rotator@example.com"))
        assert user is not None
        tokens = db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
        assert all(t.revoked for t in tokens)


def test_csrf_protection_on_mutating_requests(client: TestClient) -> None:
    """POST/PUT/PATCH/DELETE without matching X-CSRF-Token must return 403 Forbidden."""
    client.cookies.set("csrf_token", "cookie-csrf", domain="testserver.local", path="/")

    # Mismatched header
    res_mismatch = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "password123"},
        headers={"X-CSRF-Token": "wrong-csrf"},
    )
    assert res_mismatch.status_code == 403

    # Missing header
    res_missing = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert res_missing.status_code == 403


def test_login_rate_limiting(client: TestClient) -> None:
    """Exceeding 5 login attempts per minute triggers HTTP 429 Too Many Requests."""
    client.cookies.set("csrf_token", "test-csrf", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "test-csrf"}

    status_codes: list[int] = []
    for _ in range(7):
        res = client.post(
            "/api/auth/login",
            json={"email": "rate@example.com", "password": "wrongpassword123"},
            headers=headers,
        )
        status_codes.append(res.status_code)

    assert 429 in status_codes
