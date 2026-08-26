"""RAG upload orchestration: S3 ingest + Knowledge Base sync."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Sequence

from application import utils

logger = logging.getLogger("rag_service")

DEFAULT_TEAM = "mycompany"
DEFAULT_IS_CONFIDENTIAL = False

# Single PUT max object size on S3 is 5 GiB; keep a hard cap for safety.
MAX_RAG_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024

RAG_ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".html",
    ".htm",
    ".json",
    ".py",
    ".js",
}


class RagServiceError(Exception):
    """Business failure while uploading or syncing a RAG document."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def validate_rag_filename(filename: str) -> str:
    """Validate extension and return a safe basename."""
    name = os.path.basename(filename or "").strip()
    if not name:
        raise RagServiceError(400, "File name is required")
    ext = os.path.splitext(name)[1].lower()
    if ext not in RAG_ALLOWED_EXTENSIONS:
        raise RagServiceError(
            400,
            f"Unsupported file type: {ext or '(none)'}",
        )
    return name


def _assert_rag_upload_size(size: int | None) -> None:
    if size is None:
        return
    if size < 0:
        raise RagServiceError(400, "Invalid file size")
    if size == 0:
        raise RagServiceError(400, "Empty file")
    if size > MAX_RAG_UPLOAD_BYTES:
        raise RagServiceError(400, "File exceeds the 5 GiB upload limit")


def _ensure_no_active_ingestion() -> None:
    try:
        active_job = utils.get_active_ingestion_job()
    except Exception:
        raise RagServiceError(
            503,
            "Unable to check Knowledge Base sync status. Please try again later.",
        ) from None
    if active_job:
        raise RagServiceError(
            409,
            "현재 이전에 업로드된 파일을 처리하고 있습니다. 조금후 다시 시도해주세요.",
        )


def _metadata_attr(
    attr_type: str,
    *,
    string_value: str | None = None,
    number_value: float | int | None = None,
    boolean_value: bool | None = None,
    string_list_value: Sequence[str] | None = None,
    include_for_embedding: bool = False,
) -> dict[str, Any]:
    """Build one Bedrock KB sidecar metadata attribute.

    See: https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html
    """
    value: dict[str, Any] = {"type": attr_type}
    if attr_type == "STRING":
        value["stringValue"] = string_value or ""
    elif attr_type == "NUMBER":
        value["numberValue"] = number_value if number_value is not None else 0
    elif attr_type == "BOOLEAN":
        value["booleanValue"] = bool(boolean_value)
    elif attr_type == "STRING_LIST":
        value["stringListValue"] = list(string_list_value or [])
    else:
        raise ValueError(f"Unsupported metadata type: {attr_type}")

    return {
        "value": value,
        "includeForEmbedding": include_for_embedding,
    }


def build_kb_metadata_document(
    *,
    owners: Sequence[str],
    team: str = DEFAULT_TEAM,
    is_confidential: bool = DEFAULT_IS_CONFIDENTIAL,
    created_time: int | float | None = None,
) -> dict[str, Any]:
    """Return Bedrock Knowledge Base ``.metadata.json`` body for filtering.

    ``owner`` uses STRING_LIST so multiple owners can be registered.
    All attributes set ``includeForEmbedding`` to false (filter-only).
    ``created_time`` is a Unix epoch in seconds (NUMBER) so Retrieve can use
    greaterThan / lessThan range filters. Requires a fresh OpenSearch index
    so the field is mapped as numeric (not ``date``).
    """
    owner_list = [o.strip() for o in owners if o and str(o).strip()]
    if not owner_list:
        raise ValueError("At least one owner is required")

    if created_time is None:
        created_time = int(datetime.now(timezone.utc).timestamp())
    else:
        created_time = int(created_time)

    return {
        "metadataAttributes": {
            "owner": _metadata_attr(
                "STRING_LIST",
                string_list_value=owner_list,
                include_for_embedding=False,
            ),
            "team": _metadata_attr(
                "STRING",
                string_value=team,
                include_for_embedding=False,
            ),
            "created_time": _metadata_attr(
                "NUMBER",
                number_value=created_time,
                include_for_embedding=False,
            ),
            "is_confidential": _metadata_attr(
                "BOOLEAN",
                boolean_value=is_confidential,
                include_for_embedding=False,
            ),
        }
    }


def _upload_kb_metadata(
    file_name: str,
    user_id: str,
    *,
    owners: Sequence[str] | None = None,
    team: str = DEFAULT_TEAM,
    is_confidential: bool = DEFAULT_IS_CONFIDENTIAL,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Upload ``{file}.metadata.json`` sidecar; return (metadata_doc, upload_result)."""
    owner_list = list(owners) if owners else [user_id]
    try:
        metadata_doc = build_kb_metadata_document(
            owners=owner_list,
            team=team,
            is_confidential=is_confidential,
        )
    except ValueError as exc:
        raise RagServiceError(400, str(exc)) from exc

    metadata_file_name = f"{file_name}.metadata.json"
    metadata_bytes = json.dumps(metadata_doc, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    try:
        metadata_result = utils.upload_to_s3(
            metadata_bytes,
            metadata_file_name,
            user_id=user_id,
        )
    except Exception:
        logger.exception(
            "S3 metadata upload failed for file=%s user=%s",
            metadata_file_name,
            user_id,
        )
        raise RagServiceError(
            500,
            "Failed to upload Knowledge Base metadata file to S3",
        ) from None
    if not metadata_result:
        raise RagServiceError(
            500,
            "Failed to upload Knowledge Base metadata file to S3",
        )
    return metadata_doc, metadata_result


def _maybe_sync_kb(file_name: str, *, sync: bool) -> tuple[dict[str, Any] | None, str]:
    sync_result: dict[str, Any] | None = None
    if sync:
        try:
            sync_result = utils.sync_data_source()
        except Exception:
            logger.exception("Knowledge Base sync failed for file=%s", file_name)
            raise RagServiceError(
                500,
                "File uploaded but Knowledge Base sync failed",
            ) from None
        if not sync_result:
            raise RagServiceError(
                500,
                "File uploaded but Knowledge Base sync failed",
            )
        message = (
            f'"{file_name}"가 S3에 업로드 되었고 Knowledge Base와 동기화를 시작합니다.'
        )
    else:
        message = (
            f'"{file_name}"가 S3에 업로드 되었습니다. Knowledge Base 동기화는 대기 중입니다.'
        )
    return sync_result, message


def create_rag_upload_presign(
    file_name: str,
    user_id: str,
    *,
    size: int | None = None,
) -> dict[str, Any]:
    """Issue a short-lived S3 PUT URL for RAG document upload."""
    safe_name = validate_rag_filename(file_name)
    _assert_rag_upload_size(size)

    try:
        presign = utils.generate_rag_upload_presigned_put(safe_name, user_id=user_id)
    except Exception:
        logger.exception("RAG presign failed for file=%s user=%s", safe_name, user_id)
        raise RagServiceError(500, "Failed to create upload URL") from None
    if not presign or not presign.get("upload_url"):
        raise RagServiceError(500, "Failed to create upload URL")

    logger.info(
        "RAG upload presign: user=%s file=%s s3_key=%s size=%s",
        user_id,
        safe_name,
        presign.get("s3_key"),
        size,
    )
    return {
        "ok": True,
        "file_name": safe_name,
        "s3_key": presign["s3_key"],
        "content_type": presign.get("content_type"),
        "upload_url": presign["upload_url"],
        "headers": presign.get("headers") or {},
        "expires_in": presign.get("expires_in"),
        "url": presign.get("url"),
    }


def complete_rag_upload(
    file_name: str,
    s3_key: str,
    user_id: str,
    *,
    size: int | None = None,
    owners: Sequence[str] | None = None,
    team: str = DEFAULT_TEAM,
    is_confidential: bool = DEFAULT_IS_CONFIDENTIAL,
    sync: bool = True,
) -> dict[str, Any]:
    """Verify a browser PUT to docs/{projectName}/, write KB metadata, optionally start sync."""
    safe_name = validate_rag_filename(file_name)
    _assert_rag_upload_size(size)
    _ensure_no_active_ingestion()

    expected_key = utils.rag_docs_s3_key(safe_name, user_id=user_id)
    key = (s3_key or "").strip()
    if key != expected_key:
        raise RagServiceError(400, "Invalid upload target")

    head = utils.head_session_upload_object(key)
    if not head:
        raise RagServiceError(404, "Uploaded object not found")
    content_length = int(head.get("content_length") or 0)
    if content_length <= 0:
        raise RagServiceError(400, "Empty file")
    if size is not None and content_length != size:
        raise RagServiceError(
            400,
            f"Uploaded size mismatch (expected {size}, got {content_length})",
        )

    metadata_doc, metadata_result = _upload_kb_metadata(
        safe_name,
        user_id,
        owners=owners,
        team=team,
        is_confidential=is_confidential,
    )
    sync_result, message = _maybe_sync_kb(safe_name, sync=sync)

    logger.info(
        "RAG upload complete: user=%s file=%s s3_key=%s metadata_key=%s sync=%s job=%s",
        user_id,
        safe_name,
        key,
        metadata_result.get("s3_key"),
        sync,
        (sync_result or {}).get("ingestion_job_id"),
    )

    return {
        "ok": True,
        "file_name": safe_name,
        "s3_key": key,
        "metadata_file_name": metadata_result["file_name"],
        "metadata_s3_key": metadata_result["s3_key"],
        "metadata": metadata_doc,
        "user_id": user_id,
        "url": utils.rag_docs_public_url(safe_name, user_id=user_id),
        "content_type": head.get("content_type"),
        "sync": sync_result,
        "message": message,
    }


def ingest_rag_upload(
    file_bytes: bytes,
    file_name: str,
    user_id: str,
    *,
    owners: Sequence[str] | None = None,
    team: str = DEFAULT_TEAM,
    is_confidential: bool = DEFAULT_IS_CONFIDENTIAL,
    sync: bool = True,
) -> dict[str, Any]:
    """Upload ``file_bytes`` to S3 under the user's folder and optionally KB-sync.

    Objects are stored at ``docs/{projectName}/{user_id}/{file_name}`` with a
    sidecar ``{file_name}.metadata.json`` for Knowledge Base metadata filtering.

    Set ``sync=False`` for intermediate files in a multi-upload batch so only
    the last file starts ingestion (avoids 409 while a job is already running).

    Prefer :func:`create_rag_upload_presign` + browser PUT for large files so the
    request body does not traverse ECS/ALB.

    Raises:
        RagServiceError: when sync status cannot be checked, an ingest is
            already running, S3 upload fails, or KB sync fails.
    """
    safe_name = validate_rag_filename(file_name)
    if not file_bytes:
        raise RagServiceError(400, "Empty file")
    _assert_rag_upload_size(len(file_bytes))
    _ensure_no_active_ingestion()

    try:
        upload_result = utils.upload_to_s3(file_bytes, safe_name, user_id=user_id)
    except Exception:
        logger.exception("S3 upload failed for file=%s user=%s", safe_name, user_id)
        raise RagServiceError(
            500,
            "Failed to upload file to S3",
        ) from None
    if not upload_result:
        raise RagServiceError(500, "Failed to upload file to S3")

    metadata_doc, metadata_result = _upload_kb_metadata(
        safe_name,
        user_id,
        owners=owners,
        team=team,
        is_confidential=is_confidential,
    )
    sync_result, message = _maybe_sync_kb(safe_name, sync=sync)

    logger.info(
        "RAG upload complete: user=%s file=%s s3_key=%s metadata_key=%s sync=%s job=%s",
        user_id,
        safe_name,
        upload_result.get("s3_key"),
        metadata_result.get("s3_key"),
        sync,
        (sync_result or {}).get("ingestion_job_id"),
    )

    return {
        "ok": True,
        "file_name": upload_result["file_name"],
        "s3_key": upload_result["s3_key"],
        "metadata_file_name": metadata_result["file_name"],
        "metadata_s3_key": metadata_result["s3_key"],
        "metadata": metadata_doc,
        "user_id": user_id,
        "url": upload_result.get("url"),
        "sync": sync_result,
        "message": message,
    }
