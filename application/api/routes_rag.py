import logging

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from application.api.routes_auth import require_user_id
from application.services.rag_service import (
    RagServiceError,
    complete_rag_upload,
    create_rag_upload_presign,
    ingest_rag_upload,
    validate_rag_filename,
)

logger = logging.getLogger("routes_rag")

router = APIRouter(prefix="/api/rag", tags=["rag"])


class RagUploadPresignRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    size: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class RagUploadCompleteRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    s3_key: str = Field(..., min_length=1)
    size: int | None = Field(default=None, ge=0)
    sync: bool = True


@router.post("/upload/presign")
async def rag_upload_presign(request: Request, body: RagUploadPresignRequest):
    """Return a short-lived S3 PUT URL so the browser can upload past ECS body limits."""
    user_id = require_user_id(request)
    try:
        return create_rag_upload_presign(
            body.file_name,
            user_id=user_id,
            size=body.size,
        )
    except RagServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/upload/complete")
async def rag_upload_complete(request: Request, body: RagUploadCompleteRequest):
    """Confirm a presigned PUT, write KB metadata, and optionally start sync."""
    user_id = require_user_id(request)
    try:
        return complete_rag_upload(
            body.file_name,
            body.s3_key,
            user_id=user_id,
            size=body.size,
            sync=body.sync,
        )
    except RagServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/upload")
async def upload_to_rag(
    request: Request,
    file: UploadFile = File(...),
    sync: bool = Query(
        True,
        description="Start KB ingestion after upload. Use false for batch intermediates.",
    ),
):
    """Multipart upload (compat). Prefer ``/upload/presign`` for large files."""
    user_id = require_user_id(request)

    try:
        file_name = validate_rag_filename(file.filename or "")
    except RagServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        return ingest_rag_upload(
            file_bytes, file_name, user_id=user_id, sync=sync
        )
    except RagServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
