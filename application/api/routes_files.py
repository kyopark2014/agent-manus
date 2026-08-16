import logging
import os
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from application.api.routes_auth import require_user_id
from application import utils

logger = logging.getLogger("routes_files")

router = APIRouter(prefix="/api/files", tags=["files"])

IMAGE_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _validate_image_filename(filename: str) -> str:
    name = os.path.basename(filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="File name is required")
    ext = os.path.splitext(name)[1].lower()
    if ext not in IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {ext or '(none)'}",
        )
    # Avoid collisions when multiple pastes share a generic name
    stem = os.path.splitext(name)[0] or "pasted"
    unique = uuid.uuid4().hex[:10]
    return f"{stem}_{unique}{ext}"


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload an image to S3 (images/{user_id}/) for chat attachment. No Knowledge Base sync."""
    user_id = require_user_id(request)

    file_name = _validate_image_filename(file.filename or "pasted.png")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    upload_result = utils.upload_to_s3(file_bytes, file_name, user_id=user_id)
    if not upload_result:
        raise HTTPException(status_code=500, detail="Failed to upload file to S3")
    if not upload_result.get("url"):
        raise HTTPException(
            status_code=500,
            detail="File uploaded but sharing URL is not configured",
        )

    logger.info(
        "File upload complete: user=%s file=%s s3_key=%s url=%s",
        user_id,
        file_name,
        upload_result.get("s3_key"),
        upload_result.get("url"),
    )

    return {
        "ok": True,
        "file_name": upload_result["file_name"],
        "s3_key": upload_result["s3_key"],
        "url": upload_result["url"],
        "content_type": upload_result.get("content_type"),
    }
