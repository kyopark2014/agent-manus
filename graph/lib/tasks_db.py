from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class Task:
    id: str
    user_id: str
    title: str
    model_name: str
    skills: list[str]
    mcp_servers: list[str]
    created_at: str | None
    updated_at: str | None


@dataclass
class Message:
    id: str
    task_id: str
    role: str
    content: str
    images: list[Any]
    tool_events: list[Any]
    created_at: str | None


@dataclass
class Turn:
    """One user message paired with the following assistant reply (if any)."""

    task: Task
    user: Message
    assistant: Message | None = None
    tool_names: list[str] = field(default_factory=list)


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"tasks.db not found: {db_path}")
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def snapshot_db(db_path: Path) -> Iterator[Path]:
    """Yield a consistent SQLite backup path; cleans up when the block exits.

    Callers should read only the yielded snapshot so concurrent writers to the
    live tasks.db cannot observe a torn export.
    """
    db_path = db_path.expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"tasks.db not found: {db_path}")

    tmp = tempfile.NamedTemporaryFile(prefix="tasks_snapshot_", suffix=".db", delete=False)
    snap_path = Path(tmp.name)
    tmp.close()
    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        src = sqlite3.connect(str(db_path), timeout=5.0)
        src.execute("PRAGMA busy_timeout=5000")
        dst = sqlite3.connect(str(snap_path))
        src.backup(dst)
        dst.close()
        dst = None
        src.close()
        src = None
        yield snap_path
    finally:
        if dst is not None:
            try:
                dst.close()
            except Exception:
                pass
        if src is not None:
            try:
                src.close()
            except Exception:
                pass
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(snap_path) + suffix)
            try:
                if candidate.is_file():
                    candidate.unlink()
            except OSError:
                pass


def _parse_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def list_tasks(
    db_path: Path,
    *,
    user_id: str | None = None,
    limit: int | None = None,
) -> list[Task]:
    sql = "SELECT * FROM tasks"
    params: list[Any] = []
    if user_id:
        sql += " WHERE user_id = ?"
        params.append(user_id)
    sql += " ORDER BY updated_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    tasks: list[Task] = []
    for row in rows:
        tasks.append(
            Task(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"] or "New task",
                model_name=row["model_name"] or "",
                skills=_parse_json_list(row["skills_json"]),
                mcp_servers=_parse_json_list(row["mcp_servers_json"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    return tasks


def list_messages(db_path: Path, task_id: str) -> list[Message]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM messages
            WHERE task_id = ?
            ORDER BY created_at ASC
            """,
            (task_id,),
        ).fetchall()

    messages: list[Message] = []
    for row in rows:
        messages.append(
            Message(
                id=row["id"],
                task_id=row["task_id"],
                role=row["role"],
                content=row["content"] or "",
                images=_parse_json_list(row["images_json"]),
                tool_events=_parse_json_list(row["tool_events_json"]),
                created_at=row["created_at"],
            )
        )
    return messages


def extract_tool_names(tool_events: list[Any], *, max_names: int = 20) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def visit(obj: Any) -> None:
        if len(names) >= max_names:
            return
        if isinstance(obj, dict):
            for key in ("name", "tool", "tool_name", "toolName"):
                val = obj.get(key)
                if isinstance(val, str) and val and val not in seen:
                    seen.add(val)
                    names.append(val)
                    if len(names) >= max_names:
                        return
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(tool_events)
    return names


def build_turns(
    db_path: Path,
    *,
    user_id: str | None = None,
    task_limit: int | None = None,
    turn_limit: int | None = None,
) -> list[Turn]:
    """Build user→assistant turns from tasks.db for graphify corpus docs."""
    turns: list[Turn] = []
    tasks = list_tasks(db_path, user_id=user_id, limit=task_limit)

    for task in tasks:
        messages = list_messages(db_path, task.id)
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.role != "user":
                i += 1
                continue

            assistant: Message | None = None
            tool_names: list[str] = []
            if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                assistant = messages[i + 1]
                tool_names = extract_tool_names(assistant.tool_events)
                i += 2
            else:
                i += 1

            turns.append(
                Turn(
                    task=task,
                    user=msg,
                    assistant=assistant,
                    tool_names=tool_names,
                )
            )
            if turn_limit is not None and len(turns) >= turn_limit:
                return turns

    return turns


def db_stats(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        users = conn.execute(
            """
            SELECT user_id, COUNT(*) AS n
            FROM tasks
            GROUP BY user_id
            ORDER BY n DESC
            """
        ).fetchall()
    return {
        "path": str(db_path),
        "tasks": task_count,
        "messages": msg_count,
        "users": [{"user_id": r[0], "tasks": r[1]} for r in users],
    }
