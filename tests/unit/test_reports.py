"""Unit tests for stock reports: quant score calculation, prediction audit, and SSE evidence streaming."""

import json
import time
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alphalens.api.deps import get_current_user, get_db
from alphalens.api.main import create_app
from alphalens.api.routes.auth import limiter as auth_limiter
from alphalens.api.routes.reports import limiter as reports_limiter
from alphalens.db.models import Base, PredictionLog, User, UserRole

# In-memory test DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    """Provide isolated test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database_and_limits() -> Generator[None, None, None]:
    """Reset schema and rate limits."""
    Base.metadata.create_all(bind=test_engine)
    auth_limiter.reset()
    reports_limiter.reset()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_user() -> User:
    """Create a persistent user in the test database."""
    with TestingSessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email="quantuser@example.com",
            password_hash="test-hash",
            role=UserRole.USER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.fixture
def auth_client(test_user: User) -> TestClient:
    """Create test client with authenticated user dependency override."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    return TestClient(app, raise_server_exceptions=False)


def test_quant_endpoint_latency_and_decoupling(auth_client: TestClient) -> None:
    """Quant endpoint responds in < 300 ms, uses only precomputed metrics, and logs prediction."""
    start_time = time.perf_counter()
    res = auth_client.get("/api/reports/RELIANCE.NS/quant")
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert res.status_code == 200
    assert elapsed_ms < 300.0, (
        f"Quant endpoint responded in {elapsed_ms:.2f} ms (expected < 300 ms)"
    )

    data = res.json()
    assert data["ticker"] == "RELIANCE.NS"
    assert data["probability"] == 0.68
    assert data["decision_label"] == "Overweight"
    assert "factor_contributions" in data
    assert len(data["factor_contributions"]) > 0
    assert "scenarios" in data

    # Verify append-only prediction log entry was created
    with TestingSessionLocal() as db:
        log_entry = db.scalar(select(PredictionLog).where(PredictionLog.ticker == "RELIANCE.NS"))
        assert log_entry is not None
        assert log_entry.probability == 0.68
        assert log_entry.decision_label == "Overweight"


def test_unauthenticated_requests_return_401() -> None:
    """Quant and evidence stream endpoints must reject unauthenticated requests with 401."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    anon_client = TestClient(app, raise_server_exceptions=False)

    res_quant = anon_client.get("/api/reports/RELIANCE.NS/quant")
    assert res_quant.status_code == 401

    res_stream = anon_client.get("/api/reports/RELIANCE.NS/evidence/stream")
    assert res_stream.status_code == 401


def test_evidence_stream_verified_claims_and_domain_allowlist(auth_client: TestClient) -> None:
    """Evidence stream emits status, claims, and done; filters unverified claims & untrusted URLs."""
    res = auth_client.get("/api/reports/RELIANCE.NS/evidence/stream")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    raw_text = res.text
    blocks = raw_text.strip().split("\r\n\r\n" if "\r\n\r\n" in raw_text else "\n\n")
    events: list[dict[str, str]] = []

    for block in blocks:
        if not block.strip():
            continue
        event_name = ""
        data_str = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.replace("event: ", "").strip()
            elif line.startswith("data: "):
                data_str = line.replace("data: ", "").strip()
        if event_name and data_str:
            events.append({"event": event_name, "data": data_str})

    # Verify event progression
    event_names = [e["event"] for e in events]
    assert "status" in event_names
    assert "claim" in event_names
    assert "done" in event_names

    # Check verified filtering and domain allowlist sanitization
    claim_events = [e for e in events if e["event"] == "claim"]
    for c in claim_events:
        claim_obj = json.loads(c["data"])
        # Unverified claims must never be emitted
        assert claim_obj["verified"] is True
        assert "Unverified market rumor" not in claim_obj["claim_text"]

        # Disallowed domains must have url stripped to None
        for src in claim_obj["sources"]:
            if src.get("url"):
                assert any(
                    domain in src["url"]
                    for domain in ["bseindia.com", "nseindia.com", "rbi.org.in"]
                )
            if src["id"] == "src-untrusted-news":
                assert src["url"] is None


def test_evidence_stream_rate_limiting(auth_client: TestClient) -> None:
    """Exceeding 10 stream requests per hour triggers 429 Too Many Requests."""
    status_codes: list[int] = []
    for _ in range(12):
        res = auth_client.get("/api/reports/RELIANCE.NS/evidence/stream")
        status_codes.append(res.status_code)

    assert 429 in status_codes


def test_autocomplete_tickers(auth_client: TestClient) -> None:
    """GET /api/tickers returns matching Nifty 100 constituents up to 10."""
    res = auth_client.get("/api/tickers?q=TCS")
    assert res.status_code == 200
    tickers = res.json()
    assert len(tickers) >= 1
    assert tickers[0]["symbol"] == "TCS.NS"
