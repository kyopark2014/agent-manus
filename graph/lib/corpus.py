from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from lib.tasks_db import Turn


def _clip(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _yaml_escape(value: str) -> str:
    """Quote a scalar for YAML frontmatter if needed."""
    if value is None:
        return '""'
    s = str(value)
    if any(c in s for c in (":", "#", '"', "'", "\n", "{", "}", "[", "]")) or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def safe_slug(raw: str, *, max_len: int = 48) -> str:
    """Filesystem-safe slug for user ids / titles (e.g. email → underscores)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw or "user")[:max_len].strip("_")
    if cleaned:
        return cleaned
    digest = hashlib.sha1((raw or "user").encode("utf-8")).hexdigest()[:12]
    return f"user_{digest}"


# Back-compat alias
_safe_slug = safe_slug


def turn_filename(turn: Turn, index: int | None = None) -> str:
    """Stable corpus filename keyed by user message id (index kept for compat)."""
    user = safe_slug(turn.task.user_id)
    msg_id = safe_slug(turn.user.id, max_len=64)
    # Prefer stable names so delta export + content-hash cache survive re-runs.
    # Legacy indexed names are still accepted when reading existing corpora.
    if index is None:
        return f"turn-{user}-{msg_id}.md"
    title = safe_slug(turn.task.title or "task", max_len=40)
    return f"turn-{index:04d}-{user}-{title}-{turn.user.id[:8]}.md"


def stable_turn_filename(turn: Turn) -> str:
    return turn_filename(turn, index=None)


def turn_to_markdown(
    turn: Turn,
    *,
    prompt_max: int = 2000,
    reply_max: int = 3000,
) -> str:
    """Render one turn as a graphify-friendly markdown document."""
    task = turn.task
    captured = (
        (turn.assistant.created_at if turn.assistant else None)
        or turn.user.created_at
        or turn.task.updated_at
        or ""
    )
    skills = ", ".join(str(s) for s in task.skills) if task.skills else "(none)"
    mcps = ", ".join(str(m) for m in task.mcp_servers) if task.mcp_servers else "(none)"
    tools = ", ".join(turn.tool_names) if turn.tool_names else "(none)"
    user_msg = _clip(turn.user.content, prompt_max)
    reply = _clip(turn.assistant.content if turn.assistant else "", reply_max)

    lines = [
        "---",
        f"task_id: {_yaml_escape(task.id)}",
        f"user_id: {_yaml_escape(task.user_id)}",
        f"captured_at: {_yaml_escape(captured)}",
        f"source: tasks.db",
        "---",
        "",
        f"# {task.title or 'Untitled task'}",
        "",
        f"- model: {task.model_name or '(unknown)'}",
        f"- skills: {skills}",
        f"- mcp_servers: {mcps}",
        f"- tools_used: {tools}",
        f"- has_images: {bool(turn.user.images)}",
        "",
        "## User",
        "",
        user_msg or "(empty)",
        "",
        "## Assistant",
        "",
        reply or "(no assistant reply)",
        "",
    ]
    return "\n".join(lines)


def export_turns(
    turns: list[Turn],
    out_dir: Path,
    *,
    prompt_max: int = 2000,
    reply_max: int = 3000,
    clean: bool = True,
) -> list[Path]:
    """Write turn markdown files into out_dir. Returns written paths.

    Filenames are stable by message id so incremental export does not reshuffle
    paths (graphify cache keys include the resolved path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for old in out_dir.glob("turn-*.md"):
            old.unlink()

    written: list[Path] = []
    for turn in turns:
        path = out_dir / stable_turn_filename(turn)
        path.write_text(
            turn_to_markdown(turn, prompt_max=prompt_max, reply_max=reply_max),
            encoding="utf-8",
        )
        written.append(path)
    return written


def sync_corpus_turns(
    turns: list[Turn],
    out_dir: Path,
    *,
    prompt_max: int = 2000,
    reply_max: int = 3000,
    full: bool = False,
) -> tuple[list[Path], list[dict]]:
    """Write corpus turns; in delta mode only create/update changed files.

    Returns (all_corpus_paths_for_turns, changed_items) where changed_items are
    dicts ready for extract_queue.enqueue (message_id, task_id, corpus_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = {stable_turn_filename(t) for t in turns}
    # Always drop orphan/legacy turn files so corpus matches current turns.
    for old in out_dir.glob("turn-*.md"):
        if old.name not in keep:
            old.unlink()

    all_paths: list[Path] = []
    changed: list[dict] = []
    for turn in turns:
        path = out_dir / stable_turn_filename(turn)
        text = turn_to_markdown(turn, prompt_max=prompt_max, reply_max=reply_max)
        prev = path.read_text(encoding="utf-8") if path.is_file() else None
        if prev != text:
            path.write_text(text, encoding="utf-8")
            changed.append(
                {
                    "message_id": turn.user.id,
                    "task_id": turn.task.id,
                    "corpus_path": str(path.resolve()),
                }
            )
        all_paths.append(path)
    return all_paths, changed


def preview_turn(turn: Turn, *, max_chars: int = 1500) -> dict[str, Any]:
    """Compact dict for inspect_db samples."""
    return {
        "task_id": turn.task.id,
        "task_title": turn.task.title,
        "user_id": turn.task.user_id,
        "model_name": turn.task.model_name,
        "skills": turn.task.skills,
        "tools_used": turn.tool_names,
        "user_message": _clip(turn.user.content, max_chars),
        "assistant_reply": _clip(
            turn.assistant.content if turn.assistant else "", max_chars
        ),
    }
