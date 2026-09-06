"""Query chat run status without exposing checkpoint file I/O to the UI.

Resolution order:
1. In-process run registry (same process, refresh mid-run)
2. Messages DB (assistant already persisted)
3. LangGraph checkpoint (durable/working DB via SqliteSaver) — hydrate messages
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from application import chat
from application import run_registry
from application import task_store
from application.task_store_persistence import flush_persist

logger = logging.getLogger("run_state")


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    return chat._content_to_text(content)


def _ai_has_tool_calls(msg: AIMessage) -> bool:
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        return True
    additional = getattr(msg, "additional_kwargs", None) or {}
    return bool(additional.get("tool_calls"))


def _classify_checkpoint_messages(messages: list[Any]) -> dict[str, Any]:
    """Derive run status from LangGraph channel messages."""
    if not messages:
        return {
            "status": "pending",
            "content": "",
            "incomplete": True,
        }

    last = messages[-1]
    # Walk backwards for the latest final AI reply (no pending tool calls).
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not _ai_has_tool_calls(msg):
            text = _message_text(msg).strip()
            if text:
                return {
                    "status": "done",
                    "content": text,
                    "incomplete": False,
                }

    if isinstance(last, ToolMessage) or (
        isinstance(last, AIMessage) and _ai_has_tool_calls(last)
    ):
        return {
            "status": "pending",
            "content": "",
            "incomplete": True,
        }

    if isinstance(last, HumanMessage):
        return {
            "status": "pending",
            "content": "",
            "incomplete": True,
        }

    return {
        "status": "pending",
        "content": "",
        "incomplete": True,
    }


def _read_checkpoint_messages(session_id: str) -> list[Any] | None:
    """Load channel_values.messages for thread_id=session_id via SqliteSaver."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except Exception as exc:
        logger.warning("SqliteSaver unavailable: %s", exc)
        return None

    candidates: list[str] = []
    working = chat.get_checkpoint_db_path(session_id)
    durable = chat.get_persistent_checkpoint_db_path(session_id)
    # Prefer the newer non-empty DB.
    for path in (working, durable):
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            candidates.append(path)
    if not candidates:
        return None

    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    config = {"configurable": {"thread_id": session_id}}

    for path in candidates:
        try:
            with SqliteSaver.from_conn_string(path) as saver:
                tup = saver.get_tuple(config)
            if not tup or not tup.checkpoint:
                continue
            channel_values = tup.checkpoint.get("channel_values") or {}
            messages = channel_values.get("messages") or []
            if messages:
                return list(messages)
        except Exception as exc:
            logger.warning(
                "Checkpoint read failed for session=%s path=%s: %s",
                session_id,
                path,
                exc,
            )
            continue
    return None


def _hydrate_assistant_if_needed(
    *,
    task_id: str,
    user_id: str,
    content: str,
    images: list[str] | None = None,
) -> bool:
    """Persist assistant message when messages DB still ends on user."""
    content = (content or "").strip()
    if not content:
        return False
    messages = task_store.list_messages(task_id, user_id)
    if messages and messages[-1].get("role") == "assistant":
        return False
    task_store.add_message(
        task_id,
        "assistant",
        content,
        user_id=user_id,
        images=images or [],
        tool_events=[],
    )
    flush_persist(user_id)
    logger.info(
        "Hydrated assistant message from run query (%s chars) task=%s",
        len(content),
        task_id,
    )
    return True


def query_task_run(task_id: str, user_id: str) -> dict[str, Any]:
    """Return run status for a task (query API surface for UI / future runtime)."""
    task = task_store.get_task_refreshing(task_id, user_id)
    if not task:
        return {
            "task_id": task_id,
            "status": "missing",
            "content": "",
            "images": [],
            "error": "Task not found",
            "source": None,
            "hydrated": False,
        }

    session_id = task.get("runtime_session_id") or task_id
    messages = task_store.list_messages(task_id, user_id)
    last_role = messages[-1]["role"] if messages else None

    # 1) Messages already complete → idle
    if last_role == "assistant":
        last = messages[-1]
        return {
            "task_id": task_id,
            "status": "idle",
            "content": last.get("content") or "",
            "images": last.get("images") or [],
            "error": None,
            "source": "messages",
            "hydrated": False,
        }

    # 2) In-process registry (browser refresh while same process still runs)
    reg = run_registry.get(task_id)
    if reg and reg.get("status") == "running":
        return {
            "task_id": task_id,
            "status": "running",
            "content": "",
            "images": [],
            "error": None,
            "source": "registry",
            "hydrated": False,
        }

    if reg and reg.get("status") in ("done", "error"):
        content = (reg.get("content") or "").strip()
        error = reg.get("error")
        images = list(reg.get("images") or [])
        if error and not content:
            content = f"Error: {error}"
        hydrated = False
        if content and last_role == "user":
            hydrated = _hydrate_assistant_if_needed(
                task_id=task_id,
                user_id=user_id,
                content=content,
                images=images,
            )
        return {
            "task_id": task_id,
            "status": "error" if error and not (reg.get("content") or "").strip() else "done",
            "content": content,
            "images": images,
            "error": error,
            "source": "registry",
            "hydrated": hydrated,
        }

    # Empty conversation
    if not messages:
        return {
            "task_id": task_id,
            "status": "idle",
            "content": "",
            "images": [],
            "error": None,
            "source": "messages",
            "hydrated": False,
        }

    # 3) Checkpoint query (last message is user; recover finished answer)
    cp_messages = _read_checkpoint_messages(session_id)
    if cp_messages is not None:
        classified = _classify_checkpoint_messages(cp_messages)
        if classified["status"] == "done" and classified.get("content"):
            hydrated = _hydrate_assistant_if_needed(
                task_id=task_id,
                user_id=user_id,
                content=classified["content"],
            )
            return {
                "task_id": task_id,
                "status": "done",
                "content": classified["content"],
                "images": [],
                "error": None,
                "source": "checkpoint",
                "hydrated": hydrated,
            }
        return {
            "task_id": task_id,
            "status": "pending",
            "content": "",
            "images": [],
            "error": None,
            "source": "checkpoint",
            "hydrated": False,
        }

    # No registry, no checkpoint — waiting / abandoned
    return {
        "task_id": task_id,
        "status": "pending",
        "content": "",
        "images": [],
        "error": None,
        "source": None,
        "hydrated": False,
    }
