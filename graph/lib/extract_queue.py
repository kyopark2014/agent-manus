"""Persistent extract queue for incremental graph LLM work.

Stored at ``{artifact_dir}/.extract_queue.json`` (session ``out/``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUEUE_NAME = ".extract_queue.json"


def queue_path(artifact_dir: Path) -> Path:
    return Path(artifact_dir).resolve() / QUEUE_NAME


def empty_queue() -> dict[str, Any]:
    return {"pending": [], "inflight": [], "failed": []}


def load_queue(artifact_dir: Path) -> dict[str, Any]:
    path = queue_path(artifact_dir)
    if not path.is_file():
        return empty_queue()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_queue()
    if not isinstance(data, dict):
        return empty_queue()
    for key in ("pending", "inflight", "failed"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data


def save_queue(artifact_dir: Path, queue: dict[str, Any]) -> None:
    path = queue_path(artifact_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def has_work(artifact_dir: Path) -> bool:
    q = load_queue(artifact_dir)
    return bool(q["pending"] or q["inflight"])


def _item_key(item: dict[str, Any]) -> str:
    mid = (item.get("message_id") or "").strip()
    if mid:
        return f"msg:{mid}"
    return f"path:{(item.get('corpus_path') or '').strip()}"


def enqueue(
    artifact_dir: Path,
    items: list[dict[str, Any]],
) -> int:
    """Add items to pending (dedupe by message_id / path). Returns newly added count."""
    if not items:
        return 0
    q = load_queue(artifact_dir)
    seen = {
        _item_key(x)
        for bucket in ("pending", "inflight", "failed")
        for x in q[bucket]
        if _item_key(x)
    }
    added = 0
    for raw in items:
        item = {
            "message_id": (raw.get("message_id") or "").strip(),
            "task_id": (raw.get("task_id") or "").strip(),
            "content_hash": (raw.get("content_hash") or "").strip(),
            "corpus_path": (raw.get("corpus_path") or "").strip(),
        }
        key = _item_key(item)
        if not key or key in seen:
            continue
        if not item["corpus_path"]:
            continue
        seen.add(key)
        q["pending"].append(item)
        added += 1
    if added:
        save_queue(artifact_dir, q)
    return added


def claim_pending(artifact_dir: Path) -> list[dict[str, Any]]:
    """Move all pending → inflight and return the claimed items."""
    q = load_queue(artifact_dir)
    # Re-queue any leftover inflight from a crashed worker.
    claimed = list(q["inflight"]) + list(q["pending"])
    q["pending"] = []
    q["inflight"] = list(claimed)
    save_queue(artifact_dir, q)
    return claimed


def complete_items(
    artifact_dir: Path,
    *,
    message_ids: set[str] | None = None,
    corpus_paths: set[str] | None = None,
) -> None:
    """Remove completed items from inflight (and pending/failed duplicates)."""
    message_ids = message_ids or set()
    corpus_paths = {str(Path(p).resolve()) for p in (corpus_paths or set())}
    q = load_queue(artifact_dir)

    def keep(item: dict[str, Any]) -> bool:
        mid = (item.get("message_id") or "").strip()
        if mid and mid in message_ids:
            return False
        path = (item.get("corpus_path") or "").strip()
        if path and str(Path(path).resolve()) in corpus_paths:
            return False
        return True

    for bucket in ("pending", "inflight", "failed"):
        q[bucket] = [x for x in q[bucket] if keep(x)]
    save_queue(artifact_dir, q)


def fail_items(
    artifact_dir: Path,
    items: list[dict[str, Any]],
    *,
    error: str,
) -> None:
    """Move items from inflight to failed."""
    q = load_queue(artifact_dir)
    keys = {_item_key(x) for x in items}
    still_inflight: list[dict[str, Any]] = []
    for item in q["inflight"]:
        if _item_key(item) in keys:
            failed = dict(item)
            failed["error"] = (error or "")[:500]
            q["failed"].append(failed)
        else:
            still_inflight.append(item)
    q["inflight"] = still_inflight
    save_queue(artifact_dir, q)


def clear_queue(artifact_dir: Path) -> None:
    save_queue(artifact_dir, empty_queue())
