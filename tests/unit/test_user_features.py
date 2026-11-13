"""Unit tests for uploads, user prediction history, profile with delete-my-data, and calibration."""

import io
import uuid
from collections.abc import Generator

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alphalens.api.deps import get_current_user, get_db
from alphalens.api.main import create_app
from alphalens.config import get_settings
from alphalens.db.models import Base, PredictionLog, UploadRecord, User, UserProfile, UserRole

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
def setup_database() -> Generator[None, None, None]:
    """Create fresh schema."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def create_minimal_pdf_bytes(page_count: int = 1) -> bytes:
    """Generate minimal valid PDF bytes."""
    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def users() -> tuple[User, User]:
    """Create two distinct users to verify authorization barriers."""
    with TestingSessionLocal() as db:
        user_a = User(
            id=uuid.uuid4(),
            email="user_a@example.com",
            password_hash="test-hash-a",
            role=UserRole.USER,
            is_active=True,
        )
        user_b = User(
            id=uuid.uuid4(),
            email="user_b@example.com",
            password_hash="test-hash-b",
            role=UserRole.USER,
            is_active=True,
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        return user_a, user_b


def test_upload_rejection_rules(users: tuple[User, User]) -> None:
    """Upload rejects non-PDF, >20 MB, and missing consent."""
    user_a, _ = users
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app, raise_server_exceptions=False)

    csrf_token = "test-csrf"
    client.cookies.set("csrf_token", csrf_token, domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": csrf_token}

    # 1. Missing consent -> 400 Bad Request
    valid_pdf = create_minimal_pdf_bytes()
    res_no_consent = client.post(
        "/api/uploads",
        files={"file": ("report.pdf", valid_pdf, "application/pdf")},
        data={"consent": "false"},
        headers=headers,
    )
    assert res_no_consent.status_code == 400
    assert "Consent is required" in res_no_consent.json()["detail"]

    # 2. Non-PDF disguised as .pdf -> 400 Bad Request (magic bytes fail)
    fake_pdf = b"NOT_A_PDF_MAGIC_BYTES_12345"
    res_magic_fail = client.post(
        "/api/uploads",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_magic_fail.status_code == 400
    assert "magic bytes check failed" in res_magic_fail.json()["detail"]

    # 3. > 20 MB payload -> 413
    huge_pdf = b"%PDF-" + (b"0" * (20 * 1024 * 1024 + 10))
    res_huge = client.post(
        "/api/uploads",
        files={"file": ("huge.pdf", huge_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_huge.status_code == 413

    # 4. Valid PDF with consent -> 200 OK (no internal paths leaked)
    res_valid = client.post(
        "/api/uploads",
        files={"file": ("valid.pdf", valid_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert "id" in data
    assert data["original_filename"] == "valid.pdf"
    assert "stored_filename" not in data
    assert "/" not in data["original_filename"]


def test_user_isolation_for_uploads_and_history(users: tuple[User, User]) -> None:
    """User A cannot list, view, or delete User B's uploads or history."""
    user_a, user_b = users
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    # Create upload and prediction log belonging to User B
    with TestingSessionLocal() as db:
        upload_b = UploadRecord(
            id=uuid.uuid4(),
            user_id=user_b.id,
            original_filename="secret_b.pdf",
            stored_filename="b_file.pdf",
            file_size_bytes=1024,
            page_count=2,
            consent_given_at=user_b.created_at,
        )
        pred_b = PredictionLog(
            id=uuid.uuid4(),
            user_id=user_b.id,
            ticker="TCS.NS",
            probability=0.72,
            decision_label="Overweight",
            model_version="v1.0.0-quant",
        )
        db.add_all([upload_b, pred_b])
        db.commit()
        upload_b_id = upload_b.id

    # Client logged in as User A
    app.dependency_overrides[get_current_user] = lambda: user_a
    client_a = TestClient(app, raise_server_exceptions=False)
    client_a.cookies.set("csrf_token", "csrf-a", domain="testserver.local", path="/")
    headers_a = {"X-CSRF-Token": "csrf-a"}

    # User A listing uploads should not see User B's file
    res_list_uploads = client_a.get("/api/uploads")
    assert res_list_uploads.status_code == 200
    assert len(res_list_uploads.json()) == 0

    # User A attempting to delete User B's upload must return 404 (not 403)
    res_del_b = client_a.delete(f"/api/uploads/{upload_b_id}", headers=headers_a)
    assert res_del_b.status_code == 404
    assert res_del_b.json()["detail"] == "Upload not found"

    # User A listing history should not see User B's prediction
    res_history_a = client_a.get("/api/history")
    assert res_history_a.status_code == 200
    assert len(res_history_a.json()) == 0


def test_delete_my_data_pseudonymisation(users: tuple[User, User]) -> None:
    """Delete-my-data removes files and account, and pseudonymises prediction logs."""
    user_a, _ = users
    settings = get_settings()

    # Create test physical file in cache directory
    upload_dir = settings.cache_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    fake_stored_filename = f"{uuid.uuid4()}.pdf"
    file_path = upload_dir / fake_stored_filename
    file_path.write_bytes(b"%PDF-1.4 test file")

    with TestingSessionLocal() as db:
        upload_a = UploadRecord(
            id=uuid.uuid4(),
            user_id=user_a.id,
            original_filename="user_a_doc.pdf",
            stored_filename=fake_stored_filename,
            file_size_bytes=100,
            page_count=1,
            consent_given_at=user_a.created_at,
        )
        pred_a = PredictionLog(
            id=uuid.uuid4(),
            user_id=user_a.id,
            ticker="RELIANCE.NS",
            probability=0.68,
            decision_label="Overweight",
            model_version="v1.0.0-quant",
        )
        profile_a = UserProfile(
            user_id=user_a.id,
            sector_exclusions=["Tobacco"],
        )
        db.add_all([upload_a, pred_a, profile_a])
        db.commit()
        pred_id = pred_a.id

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-token", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-token"}

    # 1. Invalid confirmation returns 400
    res_bad_confirm = client.request(
        "DELETE",
        "/api/me/data",
        json={"confirmation": "WRONG"},
        headers=headers,
    )
    assert res_bad_confirm.status_code == 400

    # 2. Exact confirmation "DELETE" succeeds
    res_delete = client.request(
        "DELETE",
        "/api/me/data",
        json={"confirmation": "DELETE"},
        headers=headers,
    )
    assert res_delete.status_code == 200

    # 3. Verify physical file is deleted
    assert not file_path.is_file()

    # 4. Verify user and profile records are removed
    with TestingSessionLocal() as db:
        assert db.scalar(select(User).where(User.id == user_a.id)) is None
        assert db.scalar(select(UserProfile).where(UserProfile.user_id == user_a.id)) is None

        # 5. Verify prediction log is PSEUDONYMISED (record preserved, user_id is NULL)
        preserved_pred = db.scalar(select(PredictionLog).where(PredictionLog.id == pred_id))
        assert preserved_pred is not None
        assert preserved_pred.user_id is None
        assert preserved_pred.ticker == "RELIANCE.NS"
        assert preserved_pred.probability == 0.68


def test_calibration_endpoint(users: tuple[User, User]) -> None:
    """GET /api/calibration returns calibration bins and Brier score trajectory."""
    user_a, _ = users
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app, raise_server_exceptions=False)

    res = client.get("/api/calibration")
    assert res.status_code == 200
    data = res.json()
    assert "bins" in data
    assert len(data["bins"]) == 10
    assert "brier_history" in data
    assert "overall_brier_score" in data
    assert data["overall_brier_score"] < 0.25
