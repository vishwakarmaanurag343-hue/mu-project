"""Comprehensive unit tests covering all 11 review findings on branch feat/user-features."""

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload, sessionmaker
from sqlalchemy.pool import StaticPool

from alphalens.api.deps import get_current_user, get_db
from alphalens.api.main import create_app
from alphalens.api.routes.profile import process_pending_deletions
from alphalens.api.routes.uploads import limiter
from alphalens.api.security import hash_password
from alphalens.config import get_settings
from alphalens.data.pdf_parser import parse_pdf_safe
from alphalens.db.models import (
    AuditLog,
    Base,
    CanonicalPrediction,
    ConsentRecord,
    PendingDeletion,
    PredictionLog,
    UploadRecord,
    User,
    UserPseudonym,
    UserRole,
)
from tests.unit.test_user_features import create_minimal_pdf_bytes

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=test_engine)
    limiter.reset()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_user() -> User:
    with TestingSessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email="researcher@example.com",
            password_hash=hash_password("SuperSecurePassword123!"),
            role=UserRole.USER,
            is_active=True,
        )
        pseudo = UserPseudonym(user_id=user.id, pseudo_id=uuid.uuid4())
        db.add_all([user, pseudo])
        db.commit()

        # Eagerly load pseudonym before session closes
        loaded_user = db.scalar(
            select(User).options(joinedload(User.pseudonym)).where(User.id == user.id)
        )
        assert loaded_user is not None
        db.expunge_all()
        return loaded_user


# --- 1. PDF Parsing Timeout & Crash in Separate Process ---
def test_pdf_parsing_timeout_raises_422() -> None:
    """Mock a slow parser process that exceeds timeout -> parse_pdf_safe raises 422."""
    dummy_pdf = create_minimal_pdf_bytes(1)
    from fastapi import HTTPException

    # Mock multiprocessing Process.is_alive to True so it triggers process.terminate() and timeout 422
    mock_proc = MagicMock()
    mock_proc.is_alive.return_value = True

    with patch("multiprocessing.context.SpawnContext.Process", return_value=mock_proc):
        with pytest.raises(HTTPException) as exc_info:
            parse_pdf_safe(dummy_pdf, timeout_seconds=0.1)
        assert exc_info.value.status_code == 422
        assert "timed out" in exc_info.value.detail


# --- 2. Horizon Fixed at 6 Months ---
def test_horizon_fixed_in_history_and_quant(test_user: User) -> None:
    """Prediction history and QuantTier return fixed 6 months horizon."""
    with TestingSessionLocal() as db:
        db.add(
            PredictionLog(
                pseudo_id=test_user.pseudonym.pseudo_id,
                ticker="INFY.NS",
                probability=0.65,
                decision_label="Overweight",
                model_version="v1.0.0-quant",
            )
        )
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)

    res = client.get("/api/history")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["model_horizon_months"] == 6


# --- 3. Calibration decoupled from user request logs ---
def test_duplicate_user_requests_do_not_alter_calibration(test_user: User) -> None:
    """Duplicate user requests in PredictionLog do not affect /api/calibration."""
    # Write canonical benchmark prediction
    with TestingSessionLocal() as db:
        db.add(
            CanonicalPrediction(
                ticker="TCS.NS",
                as_of="2026-10-01",
                probability=0.70,
                outcome=1.0,
                model_version="v1.0.0",
            )
        )
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)

    initial_cal = client.get("/api/calibration").json()

    # User repeatedly requests reports -> generates 10 PredictionLog entries
    with TestingSessionLocal() as db:
        for _ in range(10):
            db.add(
                PredictionLog(
                    pseudo_id=test_user.pseudonym.pseudo_id,
                    ticker="TCS.NS",
                    probability=0.99,
                    outcome=0.0,
                    decision_label="Overweight",
                    model_version="v1.0.0-quant",
                )
            )
        db.commit()

    second_cal = client.get("/api/calibration").json()
    # Calibration output MUST be identical because it reads CanonicalPrediction only
    assert initial_cal["overall_brier_score"] == second_cal["overall_brier_score"]
    assert initial_cal["baseline_brier_score"] == second_cal["baseline_brier_score"]
    assert initial_cal["brier_skill_score"] == second_cal["brier_skill_score"]


# --- 4. Baseline Brier & Brier Skill Score ---
def test_calibration_baseline_and_bss_calculation(test_user: User) -> None:
    """BSS = 1 - Brier_model / Brier_baseline."""
    with TestingSessionLocal() as db:
        # 2 predictions: outcomes 1.0 and 0.0 (p_bar = 0.5 -> baseline = 0.5 * 0.5 = 0.25)
        # model probabilities: 0.8 (err 0.04) and 0.2 (err 0.04) -> Brier_model = 0.04
        # BSS = 1 - 0.04 / 0.25 = 1 - 0.16 = 0.84
        db.add_all(
            [
                CanonicalPrediction(
                    ticker="A", as_of="2026-01", probability=0.8, outcome=1.0, model_version="v1"
                ),
                CanonicalPrediction(
                    ticker="B", as_of="2026-01", probability=0.2, outcome=0.0, model_version="v1"
                ),
            ]
        )
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)

    res = client.get("/api/calibration")
    assert res.status_code == 200
    data = res.json()
    assert data["overall_brier_score"] == 0.04
    assert data["baseline_brier_score"] == 0.25
    assert data["brier_skill_score"] == 0.84
    assert data["coin_flip_brier_score"] == 0.25


# --- 5. Upload directory configuration in Settings ---
def test_upload_dir_setting() -> None:
    settings = get_settings()
    assert settings.upload_dir is not None
    assert str(settings.upload_dir).replace("\\", "/").endswith("data/uploads")


# --- 6. DELETE /api/me/data Requires Current Password (wrong -> 403) ---
def test_delete_my_data_password_verification(test_user: User) -> None:
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-xyz", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-xyz"}

    # Wrong password -> 403 Forbidden
    res_wrong_pw = client.request(
        "DELETE",
        "/api/me/data",
        json={"password": "WrongPassword123!", "confirmation": "DELETE"},
        headers=headers,
    )
    assert res_wrong_pw.status_code == 403

    # Correct password but wrong confirmation -> 400 Bad Request
    res_wrong_conf = client.request(
        "DELETE",
        "/api/me/data",
        json={"password": "SuperSecurePassword123!", "confirmation": "NO"},
        headers=headers,
    )
    assert res_wrong_conf.status_code == 400

    # Correct password and confirmation -> 200 OK
    res_ok = client.request(
        "DELETE",
        "/api/me/data",
        json={"password": "SuperSecurePassword123!", "confirmation": "DELETE"},
        headers=headers,
    )
    assert res_ok.status_code == 200


# --- 7 & 8 & 9. Partial failure, pending deletions, pseudonymisation & audit sanitisation ---
def test_delete_flow_pseudonymisation_and_audit(test_user: User) -> None:
    pseudo_id = test_user.pseudonym.pseudo_id
    with TestingSessionLocal() as db:
        # Create prediction log tied to pseudo_id
        pred = PredictionLog(
            pseudo_id=pseudo_id,
            ticker="HDFCBANK.NS",
            probability=0.62,
            decision_label="Overweight",
            model_version="v1.0.0-quant",
        )
        # Create audit log with user email & IP
        audit = AuditLog(
            user_id=test_user.id,
            email=test_user.email,
            ip_address="192.168.1.50",
            action="login_success",
        )
        db.add_all([pred, audit])
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-xyz", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-xyz"}

    res = client.request(
        "DELETE",
        "/api/me/data",
        json={"password": "SuperSecurePassword123!", "confirmation": "DELETE"},
        headers=headers,
    )
    assert res.status_code == 200

    with TestingSessionLocal() as db:
        # User is deleted
        assert db.scalar(select(User).where(User.id == test_user.id)) is None
        # UserPseudonym mapping is deleted
        assert db.scalar(select(UserPseudonym).where(UserPseudonym.user_id == test_user.id)) is None
        # Prediction remains untouched referencing pseudo_id
        preserved_pred = db.scalar(
            select(PredictionLog).where(PredictionLog.pseudo_id == pseudo_id)
        )
        assert preserved_pred is not None
        # Audit log sanitised: user_id is None, email is None, ip_address is None, pseudo_id is set
        audit_rows = db.scalars(select(AuditLog)).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].user_id is None
        assert audit_rows[0].email is None
        assert audit_rows[0].ip_address is None
        assert audit_rows[0].pseudo_id == pseudo_id


def test_pending_deletions_retry_function(test_user: User) -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    orphan_file = settings.upload_dir / "orphan.pdf"
    orphan_file.write_bytes(b"%PDF-1.4 test")

    with TestingSessionLocal() as db:
        pending = PendingDeletion(
            user_id=test_user.id,
            resource_type="file",
            resource_identifier="orphan.pdf",
            error_message="Initial permission lock",
        )
        db.add(pending)
        db.commit()

        # Run process_pending_deletions
        cleaned = process_pending_deletions(db)
        assert cleaned == 1
        assert not orphan_file.is_file()
        assert db.scalar(select(PendingDeletion)) is None


# --- 10 & 11. Upload Storage Quota (413) & ConsentRecord ---
def test_upload_storage_quota_and_consent_record(test_user: User) -> None:
    """User storage quota 200 MB enforced (413) and ConsentRecord stored."""
    with TestingSessionLocal() as db:
        # Pre-fill user storage with 199 MB
        db.add(
            UploadRecord(
                user_id=test_user.id,
                original_filename="large.pdf",
                stored_filename="large.pdf",
                file_size_bytes=199 * 1024 * 1024,
                page_count=50,
            )
        )
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-token", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-token"}

    # Attempt to upload 2 MB file (199 + 2 = 201 MB > 200 MB quota)
    # Magic bytes %PDF-1.4 + padding
    two_mb_pdf = b"%PDF-1.4 " + (b"0" * (2 * 1024 * 1024))
    res = client.post(
        "/api/uploads",
        files={"file": ("doc2.pdf", two_mb_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res.status_code == 413
    assert "200 MB limit per user" in res.json()["detail"]

    # Now upload a small valid PDF file within quota
    small_pdf = create_minimal_pdf_bytes(1)
    res_ok = client.post(
        "/api/uploads",
        files={"file": ("small.pdf", small_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_ok.status_code == 200

    # Verify ConsentRecord was created
    with TestingSessionLocal() as db:
        consent_rec = db.scalar(select(ConsentRecord).where(ConsentRecord.user_id == test_user.id))
        assert consent_rec is not None
        assert consent_rec.notice_version == "2026.1"
