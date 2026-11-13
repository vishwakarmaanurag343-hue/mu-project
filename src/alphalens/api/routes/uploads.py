"""Document upload handling with magic bytes verification and consent auditing."""

import contextlib
import io
import uuid
from datetime import UTC, datetime

import pypdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from alphalens.api.deps import get_current_user
from alphalens.api.security import verify_csrf
from alphalens.config import get_settings
from alphalens.db.models import UploadRecord, User
from alphalens.db.session import get_db

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PAGE_LIMIT = 100


class UploadResponse(BaseModel):
    """Metadata response for an uploaded research document."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    page_count: int
    created_at: datetime


@router.post("", response_model=UploadResponse, dependencies=[Depends(verify_csrf)])
async def upload_document(
    file: UploadFile = File(description="Research document (PDF only)"),
    consent: bool = Form(
        description="Required consent that document will be processed for analysis"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload and verify research PDF document.

    Enforces 20 MB size limit, PDF magic bytes check, page limit, and random UUID storage.
    """
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to upload and process research documents",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
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

    # Parse in-memory with pypdf and enforce page limit
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        if page_count > MAX_PAGE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Document exceeds maximum page limit of {MAX_PAGE_LIMIT} pages "
                    f"(found {page_count})"
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or unreadable PDF document",
        ) from exc

    settings = get_settings()
    upload_dir = settings.cache_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    random_filename = f"{uuid.uuid4()}.pdf"
    stored_path = upload_dir / random_filename
    stored_path.write_bytes(content)

    clean_filename = file.filename or "document.pdf"
    record = UploadRecord(
        user_id=current_user.id,
        original_filename=clean_filename,
        stored_filename=random_filename,
        file_size_bytes=len(content),
        page_count=page_count,
        consent_given_at=datetime.now(UTC),
    )
    db.add(record)
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
    stored_path = settings.cache_dir / "uploads" / record.stored_filename
    if stored_path.is_file():
        with contextlib.suppress(Exception):
            stored_path.unlink()

    db.delete(record)
    db.commit()

    return {"status": "deleted"}
