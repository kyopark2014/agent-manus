"""Background knowledge-graph pipeline jobs triggered after chat / login / rebuild."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("graph_jobs")

_APPLICATION_DIR = Path(__file__).resolve().parent
_GRAPH_DIR = _APPLICATION_DIR.parent / "graph"
_DEFAULT_COOLDOWN = 600
_FINGERPRINT_NAME = ".graph_source_fingerprint.json"

_lock = threading.Lock()
_pipeline_lock = threading.Lock()
_running_users: set[str] = set()
_states: dict[str, "GraphJobState"] = {}


def _cooldown_seconds() -> int:
    raw = os.environ.get("GRAPH_JOB_COOLDOWN_SECONDS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return _DEFAULT_COOLDOWN


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GraphJobState:
    user_id: str
    status: str = "idle"  # idle|queued|running|ready|error|skipped_cooldown|skipped_unchanged
    error: str | None = None
    last_success_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        cooldown = _cooldown_seconds()
        next_eligible: str | None = None
        if self.last_success_at is not None and cooldown > 0:
            next_eligible = (
                self.last_success_at + timedelta(seconds=cooldown)
            ).isoformat()
        return {
            "user_id": self.user_id,
            "status": self.status,
            "error": self.error,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "cooldown_seconds": cooldown,
            "next_eligible_at": next_eligible,
        }


def _get_or_create(user_id: str) -> GraphJobState:
    state = _states.get(user_id)
    if state is None:
        state = GraphJobState(user_id=user_id)
        _states[user_id] = state
    return state


def get_job_status(user_id: str) -> dict[str, Any]:
    with _lock:
        return _get_or_create(user_id).to_dict()


def _in_cooldown(state: GraphJobState) -> bool:
    cooldown = _cooldown_seconds()
    if cooldown <= 0 or state.last_success_at is None:
        return False
    return (_now() - state.last_success_at) < timedelta(seconds=cooldown)


def _fingerprint_path(user_id: str) -> Path:
    from application import utils

    return Path(utils.get_user_graph_dir(user_id)) / "out" / _FINGERPRINT_NAME


def _compute_source_fingerprint(user_id: str) -> dict[str, Any]:
    """Return {message_count, max_created_at} for the user's tasks.db messages."""
    from application import task_store
    from application.task_store_persistence import working_user_db_path

    db_path = working_user_db_path(user_id)
    message_count = 0
    max_created_at: str | None = None
    try:
        # Ensure per-user DB exists (lazy migrate) before fingerprinting.
        task_store.ensure_user_db(user_id)
        db_path = working_user_db_path(user_id)
    except Exception:
        logger.exception("Failed to ensure user DB for fingerprint %s", user_id)

    if os.path.isfile(db_path):
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(m.id), MAX(m.created_at)
                    FROM messages m
                    JOIN tasks t ON t.id = m.task_id
                    WHERE t.user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
            if row:
                message_count = int(row[0] or 0)
                max_created_at = row[1]
        except sqlite3.Error:
            logger.exception("Failed to compute graph source fingerprint for %s", user_id)
    return {
        "user_id": user_id,
        "message_count": message_count,
        "max_created_at": max_created_at,
    }


def _load_fingerprint(user_id: str) -> dict[str, Any] | None:
    path = _fingerprint_path(user_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Invalid graph fingerprint at %s", path)
        return None
    return data if isinstance(data, dict) else None


def _save_fingerprint(user_id: str, fingerprint: dict[str, Any]) -> None:
    path = _fingerprint_path(user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(fingerprint, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        logger.exception("Failed to save graph fingerprint for %s", user_id)


def _queue_has_work(user_id: str) -> bool:
    """True when out/.extract_queue.json still has pending/inflight items."""
    from application import utils

    artifact = Path(utils.get_user_graph_dir(user_id)) / "out"
    graph_dir = str(_GRAPH_DIR)
    inserted = False
    if graph_dir not in sys.path:
        sys.path.insert(0, graph_dir)
        inserted = True
    try:
        from lib.extract_queue import has_work  # type: ignore

        return bool(has_work(artifact))
    except Exception:
        logger.exception("Failed to read extract queue for %s", user_id)
        return False
    finally:
        if inserted:
            try:
                sys.path.remove(graph_dir)
            except ValueError:
                pass


def _source_unchanged(user_id: str) -> bool:
    """True when graph.html exists and tasks.db fingerprint matches last extract."""
    from application import utils

    html = Path(utils.user_graph_html_path(user_id))
    if not html.is_file():
        return False
    stored = _load_fingerprint(user_id)
    if stored is None:
        return False
    current = _compute_source_fingerprint(user_id)
    return (
        stored.get("message_count") == current.get("message_count")
        and stored.get("max_created_at") == current.get("max_created_at")
    )


def ensure_graph_job(user_id: str, *, force: bool = False) -> dict[str, Any]:
    """Start a background pipeline for user_id unless running, unchanged, or in cooldown.

    Returns the current job status dict. Never blocks on the pipeline itself.
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return {"status": "idle", "error": "missing user_id"}

    try:
        from application import utils

        if not utils.is_knowledge_graph_enabled(user_id):
            logger.info("Knowledge Graph disabled for %s — skip ensure_graph_job", user_id)
            return {
                "status": "disabled",
                "error": None,
                "enabled": False,
            }
    except Exception:
        logger.exception("Failed to read Knowledge Graph setting for %s", user_id)

    with _lock:
        state = _get_or_create(user_id)
        if user_id in _running_users or state.status in ("running", "queued"):
            logger.info("Graph job already running for %s — skip", user_id)
            return state.to_dict()

        if not force and _source_unchanged(user_id) and not _queue_has_work(user_id):
            state.status = "skipped_unchanged"
            state.error = None
            state.updated_at = _now()
            logger.info(
                "Graph source unchanged for %s — skip pipeline",
                user_id,
            )
            return state.to_dict()

        if not force and _in_cooldown(state):
            state.status = "skipped_cooldown"
            state.updated_at = _now()
            logger.info(
                "Graph job cooldown active for %s (last_success=%s, cooldown=%ss) — skip",
                user_id,
                state.last_success_at.isoformat() if state.last_success_at else None,
                _cooldown_seconds(),
            )
            return state.to_dict()

        state.status = "queued"
        state.error = None
        state.started_at = _now()
        state.finished_at = None
        state.updated_at = state.started_at
        _running_users.add(user_id)

    thread = threading.Thread(
        target=_run_pipeline,
        args=(user_id, force),
        name=f"graph-job-{user_id[:32]}",
        daemon=True,
    )
    thread.start()
    return get_job_status(user_id)


def _run_pipeline(user_id: str, force: bool = False) -> None:
    with _lock:
        state = _get_or_create(user_id)
        state.status = "running"
        state.updated_at = _now()

    logger.info("Graph pipeline starting for user=%s force=%s", user_id, force)
    try:
        # Ensure session-storage workspace exists before the CLI configures env dirs.
        try:
            from application import utils

            utils.ensure_user_graph_dir(user_id)
        except Exception:
            logger.exception("Could not ensure user graph dir for %s", user_id)

        with _pipeline_lock:
            cmd = [
                sys.executable,
                "run_pipeline.py",
                "--user",
                user_id,
            ]
            if force:
                cmd.append("--full")
            env = os.environ.copy()
            try:
                from application import task_store
                from application.task_store_persistence import working_user_db_path

                task_store.ensure_user_db(user_id)
                env["TASKS_DB_PATH"] = working_user_db_path(user_id)
            except Exception:
                logger.exception(
                    "Could not resolve per-user tasks DB for graph pipeline %s",
                    user_id,
                )
            logger.info("+ %s (cwd=%s)", " ".join(cmd), _GRAPH_DIR)
            subprocess.check_call(cmd, cwd=str(_GRAPH_DIR), env=env)
        fingerprint = _compute_source_fingerprint(user_id)
        _save_fingerprint(user_id, fingerprint)
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "ready"
            state.error = None
            state.last_success_at = now
            state.finished_at = now
            state.updated_at = now
            _running_users.discard(user_id)
        logger.info("Graph pipeline ready for user=%s", user_id)
    except Exception as exc:
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "error"
            state.error = str(exc)[:500]
            state.finished_at = now
            state.updated_at = now
            # Failures do not set last_success_at — retries allowed immediately.
            _running_users.discard(user_id)
        logger.exception("Graph pipeline failed for user=%s", user_id)


def republish_graph_html(
    user_id: str,
    *,
    pattern: str | None = None,
    sync_runtime: bool = False,  # reserved; no graph→runtime mirror in this app
) -> bool:
    """Re-render out/graph.html from existing graph.json using the given pattern.

    Pattern switches only change the view HTML; full runtime mirroring is skipped
    by default. Pass ``sync_runtime=True`` only when callers need AgentCore storage
    updated (pipeline success paths already mirror when configured).
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return False

    from application import utils

    out_dir = Path(utils.get_user_graph_dir(user_id)) / "out"
    graph_root = str(_GRAPH_DIR)
    if graph_root not in sys.path:
        sys.path.insert(0, graph_root)

    from lib.out_graphs import republish_html_from_json

    pid = pattern or utils.get_graph_pattern(user_id)
    os.environ.setdefault("SESSION_STORAGE_DIR", utils.SESSION_STORAGE_DIR)
    written = republish_html_from_json(out_dir, user_id=user_id, pattern=pid)
    if written is None:
        logger.info("No graph.json to republish for %s (pattern=%s)", user_id, pid)
        return False
    logger.info("Republished graph HTML for %s pattern=%s → %s", user_id, pid, written)
    if sync_runtime:
        logger.debug("sync_runtime requested but no graph→runtime mirror in this app")
    return True
