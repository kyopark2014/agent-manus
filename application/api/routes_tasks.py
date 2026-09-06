from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from application.api.routes_auth import require_user_id, _llm_gateway_ready
from application import task_store
from application import utils
from application.run_state import query_task_run

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_LLM_GATEWAY_NOT_CONFIGURED = (
    "LLM Gateway가 설정되어 있지 않아 활성화할 수 없습니다."
)


class TaskCreate(BaseModel):
    model_name: str | None = None
    skills: list[str] | None = None
    mcp_servers: list[str] | None = None
    guardrail_enabled: bool = False
    llm_gateway_enabled: bool = False
    memory_enabled: bool = True
    title: str = "New task"


class TaskPatch(BaseModel):
    title: str | None = None
    model_name: str | None = None
    skills: list[str] | None = None
    mcp_servers: list[str] | None = None
    guardrail_enabled: bool | None = None
    llm_gateway_enabled: bool | None = None
    memory_enabled: bool | None = None
    pinned: bool | None = None


def _require_gateway_if_enabling(enabled: bool | None) -> None:
    if enabled and not _llm_gateway_ready():
        raise HTTPException(status_code=400, detail=_LLM_GATEWAY_NOT_CONFIGURED)


@router.get("")
def list_tasks(request: Request, limit: int = 100):
    user_id = require_user_id(request)
    return {"tasks": task_store.list_tasks(user_id, limit=limit)}


@router.post("")
def create_task(body: TaskCreate, request: Request):
    user_id = require_user_id(request)
    _require_gateway_if_enabling(body.llm_gateway_enabled)
    skills, mcp_servers = _resolve_tool_defaults(
        user_id, body.skills, body.mcp_servers
    )
    # Remember the user's last selection for subsequent new tasks.
    utils.save_user_tool_defaults(
        user_id, skills=skills, mcp_servers=mcp_servers
    )
    task = task_store.create_task(
        user_id,
        model_name=body.model_name,
        skills=skills,
        mcp_servers=mcp_servers,
        guardrail_enabled=body.guardrail_enabled,
        llm_gateway_enabled=body.llm_gateway_enabled,
        memory_enabled=body.memory_enabled,
        title=body.title,
    )
    return task


@router.get("/{task_id}")
def get_task(task_id: str, request: Request):
    user_id = require_user_id(request)
    task = task_store.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
def patch_task(task_id: str, body: TaskPatch, request: Request):
    user_id = require_user_id(request)
    task = task_store.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    patch = body.model_dump(exclude_unset=True)
    _require_gateway_if_enabling(patch.get("llm_gateway_enabled"))
    updated = task_store.update_task(
        task_id,
        user_id,
        **patch,
    )
    if updated and ("skills" in patch or "mcp_servers" in patch):
        utils.save_user_tool_defaults(
            user_id,
            skills=patch.get("skills"),
            mcp_servers=patch.get("mcp_servers"),
        )
    return updated


@router.delete("/{task_id}")
def remove_task(task_id: str, request: Request):
    user_id = require_user_id(request)
    if not task_store.delete_task(task_id, user_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}



def _resolve_tool_defaults(
    user_id: str,
    skills: list[str] | None,
    mcp_servers: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Fill missing skill/MCP from settings.json (else favorite_tools)."""
    default_skills, default_mcp = utils.get_user_tool_defaults(user_id)
    resolved_skills = list(skills) if skills is not None else list(default_skills)
    resolved_mcp = (
        list(mcp_servers) if mcp_servers is not None else list(default_mcp)
    )
    return resolved_skills, resolved_mcp

@router.get("/{task_id}/messages")
def get_messages(task_id: str, request: Request):
    user_id = require_user_id(request)
    task = task_store.get_task_refreshing(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"messages": task_store.list_messages(task_id, user_id)}


@router.get("/{task_id}/run")
def get_task_run(task_id: str, request: Request):
    """Query agent run status for refresh recovery (no direct checkpoint I/O for clients).

    Status values: idle | running | pending | done | error | missing
    source: messages | registry | checkpoint | null
    When status is done and messages still end on user, hydrates the assistant row.
    """
    user_id = require_user_id(request)
    result = query_task_run(task_id, user_id)
    if result.get("status") == "missing":
        raise HTTPException(status_code=404, detail="Task not found")
    return result
