"""Document upload handling with sandbox process isolation, storage quota, and consent records."""

import contextlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.api.security import verify_csrf
from alphalens.config import get_settings
from alphalens.data.pdf_parser import parse_pdf_safe
from alphalens.db.models import ConsentRecord, UploadRecord, User
from alphalens.db.session import get_db

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
limiter = Limiter(key_func=get_remote_address)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
USER_STORAGE_QUOTA_BYTES = 200 * 1024 * 1024  # 200 MB
CURRENT_NOTICE_VERSION = "2026.1"


class UploadResponse(BaseModel):
    """Metadata response for an uploaded research document."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    page_count: int
    created_at: datetime


@router.post("", response_model=UploadResponse, dependencies=[Depends(verify_csrf)])
@limiter.limit("10/day")
async def upload_document(
    request: Request,
    file: UploadFile = File(description="Research document (PDF only)"),
    consent: bool = Form(
        description="Required consent that document will be processed for analysis"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload and verify research PDF document.

    Enforces 20 MB file ceiling, 200 MB user storage quota, PDF magic bytes check,
    10s isolated subprocess parsing, and audits privacy consent version.
    """
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to upload and process research documents",
        )

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 20 MB maximum limit",
        )

    # Magic bytes check: must begin with %PDF-
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format: Document must be a valid PDF (magic bytes check failed)",
        )

    # Storage Quota Check: 200 MB per user
    current_storage = (
        db.scalar(
            select(func.coalesce(func.sum(UploadRecord.file_size_bytes), 0)).where(
                UploadRecord.user_id == current_user.id
            )
        )
        or 0
    )

    if current_storage + file_size > USER_STORAGE_QUOTA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Storage quota exceeded: 200 MB limit per user.",
        )

    # Parse in a dedicated worker process with 10 s timeout and memory limits
    page_count = parse_pdf_safe(content, max_pages=100, timeout_seconds=10.0)

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    random_filename = f"{uuid.uuid4()}.pdf"
    stored_path = upload_dir / random_filename
    stored_path.write_bytes(content)

    clean_filename = file.filename or "document.pdf"
    record = UploadRecord(
        user_id=current_user.id,
        original_filename=clean_filename,
        stored_filename=random_filename,
        file_size_bytes=file_size,
        page_count=page_count,
    )
    db.add(record)

    # Record structured consent audit
    consent_record = ConsentRecord(
        user_id=current_user.id,
        notice_version=CURRENT_NOTICE_VERSION,
        consent_given_at=datetime.now(UTC),
    )
    db.add(consent_record)

    db.commit()
    db.refresh(record)

    return UploadResponse(
        id=record.id,
        original_filename=record.original_filename,
        file_size_bytes=record.file_size_bytes,
        page_count=record.page_count,
        created_at=record.created_at,
    )


@router.get("", response_model=list[UploadResponse])
async def list_user_uploads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UploadResponse]:
    """List all research documents uploaded by the authenticated user."""
    records = db.scalars(
        select(UploadRecord)
        .where(UploadRecord.user_id == current_user.id)
        .order_by(UploadRecord.created_at.desc())
    ).all()

    return [
        UploadResponse(
            id=r.id,
            original_filename=r.original_filename,
            file_size_bytes=r.file_size_bytes,
            page_count=r.page_count,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.delete("/{upload_id}", response_model=dict[str, str], dependencies=[Depends(verify_csrf)])
async def delete_user_upload(
    upload_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete an upload record and stored file. Returns 404 if not found or unauthorized."""
    record = db.scalar(
        select(UploadRecord).where(
            UploadRecord.id == upload_id,
            UploadRecord.user_id == current_user.id,
        )
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    settings = get_settings()
    stored_path = Path(settings.upload_dir) / record.stored_filename
    if stored_path.is_file():
        with contextlib.suppress(Exception):
            stored_path.unlink()

    db.delete(record)
    db.commit()

    return {"status": "deleted"}
