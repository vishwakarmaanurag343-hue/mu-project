"""Comprehensive unit tests covering all review findings on branch feat/user-features."""

import multiprocessing as mp
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


# ==============================================================================
# REVIEW ITEM 1: PDF Worker Isolation, Spawn Context & Timeout
# ==============================================================================
def test_pdf_worker_uses_spawn_context() -> None:
    """PDF parser worker uses multiprocessing.get_context('spawn') to avoid deadlock."""
    dummy_pdf = create_minimal_pdf_bytes(1)

    with patch("multiprocessing.get_context", wraps=mp.get_context) as mock_get_context:
        pages = parse_pdf_safe(dummy_pdf)
        assert pages == 1
        mock_get_context.assert_called_with("spawn")


def test_pdf_parsing_timeout_raises_422() -> None:
    """Mock a slow parser process that exceeds timeout -> parse_pdf_safe raises 422."""
    dummy_pdf = create_minimal_pdf_bytes(1)
    from fastapi import HTTPException

    mock_proc = MagicMock()
    mock_proc.is_alive.return_value = True

    with patch("multiprocessing.context.SpawnContext.Process", return_value=mock_proc):
        with pytest.raises(HTTPException) as exc_info:
            parse_pdf_safe(dummy_pdf, timeout_seconds=0.1)
        assert exc_info.value.status_code == 422
        assert "timed out" in exc_info.value.detail


# ==============================================================================
# REVIEW ITEM 2: Model Horizon Fixed at 6 Months
# ==============================================================================
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


# ==============================================================================
# REVIEW ITEM 3: Decoupled Calibration Analytics
# ==============================================================================
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


# ==============================================================================
# REVIEW ITEM 4: Baseline Brier & Brier Skill Score
# ==============================================================================
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


# ==============================================================================
# REVIEW ITEM 5: Upload directory configuration in Settings
# ==============================================================================
def test_upload_dir_setting() -> None:
    settings = get_settings()
    assert settings.upload_dir is not None
    assert str(settings.upload_dir).replace("\\", "/").endswith("data/uploads")


# ==============================================================================
# REVIEW ITEM 6: Password Required on DELETE /api/me/data (wrong -> 403)
# ==============================================================================
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


# ==============================================================================
# REVIEW ITEM 7: Pending Deletions partial failure queue and recovery
# ==============================================================================
def test_pending_deletions_failure_queued_and_cleared_by_retry(test_user: User) -> None:
    """Simulated file-delete failure is queued in pending_deletions, and later removed by retry."""
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}.pdf"
    fake_file = settings.upload_dir / stored_name
    fake_file.write_bytes(b"%PDF-1.4 test")

    with TestingSessionLocal() as db:
        upload = UploadRecord(
            id=uuid.uuid4(),
            user_id=test_user.id,
            original_filename="locked.pdf",
            stored_filename=stored_name,
            file_size_bytes=100,
            page_count=1,
        )
        db.add(upload)
        db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-xyz", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-xyz"}

    # Simulate unlink failure during deletion
    with patch.object(type(fake_file), "unlink", side_effect=PermissionError("File locked by OS")):
        res = client.request(
            "DELETE",
            "/api/me/data",
            json={"password": "SuperSecurePassword123!", "confirmation": "DELETE"},
            headers=headers,
        )
        assert res.status_code == 200

    # Verify failure was recorded in pending_deletions
    with TestingSessionLocal() as db:
        pending_records = db.scalars(select(PendingDeletion)).all()
        assert len(pending_records) >= 1
        failed_item = next(p for p in pending_records if p.resource_identifier == stored_name)
        assert failed_item.resource_type == "file"
        assert "File locked by OS" in (failed_item.error_message or "")

        # Now simulate file lock freed, and run process_pending_deletions()
        cleaned_count = process_pending_deletions(db)
        assert cleaned_count >= 1
        assert not fake_file.is_file()
        assert (
            db.scalar(select(PendingDeletion).where(PendingDeletion.id == failed_item.id)) is None
        )


# ==============================================================================
# REVIEW ITEM 8 & 9: Pseudonymisation of predictions and audit logs
# ==============================================================================
def test_audit_log_pseudonymised_after_deletion(test_user: User) -> None:
    """Audit log rows are pseudonymised after deletion (no email, IP, user_id)."""
    pseudo_id = test_user.pseudonym.pseudo_id
    with TestingSessionLocal() as db:
        audit = AuditLog(
            user_id=test_user.id,
            email=test_user.email,
            ip_address="203.0.113.195",
            action="login_success",
        )
        db.add(audit)
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
        # User record is gone
        assert db.scalar(select(User).where(User.id == test_user.id)) is None
        # Audit log has user identifiers cleared and pseudo_id preserved
        sanitized_audit = db.scalar(select(AuditLog).where(AuditLog.pseudo_id == pseudo_id))
        assert sanitized_audit is not None
        assert sanitized_audit.user_id is None
        assert sanitized_audit.email is None
        assert sanitized_audit.ip_address is None


# ==============================================================================
# REVIEW ITEM 10: Upload Quota (413) & Rate Limit (429)
# ==============================================================================
def test_upload_storage_quota_exceeded_413(test_user: User) -> None:
    """Uploading beyond 200 MB quota returns HTTP 413."""
    with TestingSessionLocal() as db:
        # Pre-fill storage with 199 MB
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

    # Attempt to upload 2 MB file (199 + 2 = 201 MB > 200 MB limit)
    two_mb_pdf = b"%PDF-1.4 " + (b"0" * (2 * 1024 * 1024))
    res = client.post(
        "/api/uploads",
        files={"file": ("doc2.pdf", two_mb_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res.status_code == 413
    assert "200 MB limit per user" in res.json()["detail"]


def test_upload_eleventh_in_a_day_rate_limit_429(test_user: User) -> None:
    """11th upload in a day triggers rate limiting -> HTTP 429."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-token", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-token"}

    small_pdf = create_minimal_pdf_bytes(1)

    # 10 allowed uploads
    for _ in range(10):
        res = client.post(
            "/api/uploads",
            files={"file": ("small.pdf", small_pdf, "application/pdf")},
            data={"consent": "true"},
            headers=headers,
        )
        assert res.status_code == 200

    # 11th upload within the same day -> 429 Too Many Requests
    res_eleventh = client.post(
        "/api/uploads",
        files={"file": ("small.pdf", small_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_eleventh.status_code == 429


# ==============================================================================
# REVIEW ITEM 11: Consent Record Created & Pseudonymised After Deletion
# ==============================================================================
def test_consent_record_created_on_upload_and_pseudonymised_on_deletion(
    test_user: User,
) -> None:
    """Consent record is created on upload and pseudonymised with pseudo_id after deletion."""
    pseudo_id = test_user.pseudonym.pseudo_id
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("csrf_token", "csrf-token", domain="testserver.local", path="/")
    headers = {"X-CSRF-Token": "csrf-token"}

    # Upload document with consent
    small_pdf = create_minimal_pdf_bytes(1)
    res_upload = client.post(
        "/api/uploads",
        files={"file": ("report.pdf", small_pdf, "application/pdf")},
        data={"consent": "true"},
        headers=headers,
    )
    assert res_upload.status_code == 200

    # Verify ConsentRecord created with user_id
    with TestingSessionLocal() as db:
        consent = db.scalar(select(ConsentRecord).where(ConsentRecord.user_id == test_user.id))
        assert consent is not None
        assert consent.notice_version == "2026.1"
        assert consent.pseudo_id is None

    # Delete account
    res_delete = client.request(
        "DELETE",
        "/api/me/data",
        json={"password": "SuperSecurePassword123!", "confirmation": "DELETE"},
        headers=headers,
    )
    assert res_delete.status_code == 200

    # Verify ConsentRecord persists with pseudo_id, and user_id is NULL
    with TestingSessionLocal() as db:
        consent_after = db.scalar(select(ConsentRecord).where(ConsentRecord.pseudo_id == pseudo_id))
        assert consent_after is not None
        assert consent_after.user_id is None
        assert consent_after.notice_version == "2026.1"
        assert consent_after.consent_given_at is not None
