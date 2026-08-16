"""Serve per-user knowledge graph HTML from session storage."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from application.api.routes_auth import require_user_id
from application.graph_jobs import ensure_graph_job, get_job_status, republish_graph_html
from application.graph_query import query_user_graph
from application import utils

router = APIRouter(prefix="/api/graph", tags=["graph"])



# Marker present in current pattern HTML templates (top-left document search).
_GRAPH_HTML_CURRENT_MARKER = 'data-doc-search="1"'


def user_graph_html_path(user_id: str) -> Path:
    """Session storage only: …/{user}/graph/out/graph.html"""
    return Path(utils.user_graph_html_path(user_id))


def user_graph_json_path(user_id: str) -> Path:
    return Path(utils.get_user_graph_dir(user_id)) / "out" / "graph.json"


def _ensure_graph_html_current(user_id: str, path: Path) -> Path:
    """Re-render graph.html when an older publish lacks the document-search UI."""
    if not path.is_file():
        return path
    try:
        sample = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return path
    if _GRAPH_HTML_CURRENT_MARKER in sample:
        return path
    graph_json = user_graph_json_path(user_id)
    if not graph_json.is_file():
        return path
    try:
        republish_graph_html(user_id)
    except Exception:
        return path
    return path


class GraphQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    mode: Literal["bfs", "dfs"] = "bfs"
    budget: int = Field(2000, ge=200, le=8000)


@router.get("/status")
def graph_status(request: Request) -> dict:
    user_id = require_user_id(request)
    enabled = utils.is_knowledge_graph_enabled(user_id)
    path = user_graph_html_path(user_id)
    job = get_job_status(user_id)
    exists = path.is_file()
    status = job.get("status") or "idle"
    if not enabled:
        status = "disabled"
    elif status in ("idle", "skipped_cooldown", "skipped_unchanged") and exists:
        status = "ready" if status in ("idle", "skipped_unchanged") else status
    return {
        "user_id": user_id,
        "exists": exists,
        "path": path.name if exists else None,
        "storage": str(path.parent),
        "status": status,
        "enabled": enabled,
        "error": job.get("error"),
        "last_success_at": job.get("last_success_at"),
        "cooldown_seconds": job.get("cooldown_seconds"),
        "next_eligible_at": job.get("next_eligible_at"),
    }


@router.post("/rebuild")
def rebuild_graph(request: Request, force: bool = Query(False)) -> dict:
    """Enqueue a background pipeline (respects cooldown unless force=true)."""
    user_id = require_user_id(request)
    if not utils.is_knowledge_graph_enabled(user_id):
        raise HTTPException(
            status_code=403,
            detail="Knowledge Graph is disabled in Settings",
        )
    job = ensure_graph_job(user_id, force=force)
    path = user_graph_html_path(user_id)
    return {
        "user_id": user_id,
        "exists": path.is_file(),
        "path": path.name if path.is_file() else None,
        "storage": str(path.parent),
        "enabled": True,
        **job,
    }


@router.get("")
def get_user_graph(request: Request):
    """Open the logged-in user's knowledge graph from session storage."""
    user_id = require_user_id(request)
    path = user_graph_html_path(user_id)
    if path.is_file():
        path = _ensure_graph_html_current(user_id, path)
    if not path.is_file():
        job = get_job_status(user_id)
        status = job.get("status") or "idle"
        if status in ("queued", "running"):
            detail = "지식 그래프를 백그라운드에서 생성 중입니다. 잠시 후 다시 열어 주세요."
        elif status == "error":
            detail = f"그래프 생성에 실패했습니다: {job.get('error') or 'unknown error'}"
        else:
            detail = (
                f"사용자 <b>{user_id}</b> 용 그래프 파일이 아직 없습니다. "
                "로그인 후 자동 생성을 기다리거나 "
                f"<code>cd graph && python run_pipeline.py --user {user_id}</code> "
                "로 생성해 주세요."
            )
        return HTMLResponse(
            "<!doctype html><html lang='ko'><head><meta charset='UTF-8' />"
            f"<title>Knowledge Graph — {user_id}</title></head><body style='"
            "font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
            "padding:48px;max-width:640px;margin:0 auto;'>"
            f"<h1>Knowledge Graph 없음</h1>"
            f"<p>{detail}</p>"
            "</body></html>",
            status_code=404,
        )
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )


@router.post("/query")
def query_graph(body: GraphQueryRequest, request: Request) -> dict:
    """BFS/DFS traversal over the user's graph.json with source-text excerpts."""
    user_id = require_user_id(request)
    if not utils.is_knowledge_graph_enabled(user_id):
        raise HTTPException(
            status_code=403,
            detail="Knowledge Graph is disabled in Settings",
        )
    graph_json = user_graph_json_path(user_id)
    if not graph_json.is_file():
        raise HTTPException(
            status_code=404,
            detail="그래프가 아직 없습니다. 먼저 지식 그래프를 생성하세요.",
        )
    graph_root = Path(utils.get_user_graph_dir(user_id))
    try:
        return query_user_graph(
            graph_json,
            body.question,
            mode=body.mode,
            budget=body.budget,
            allowed_roots=[graph_root, graph_root / "corpus", graph_root / "out"],
            use_embeddings=utils.is_hybrid_graph_search_enabled(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"query failed: {exc}",
        ) from exc
