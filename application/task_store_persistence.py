"""Persist global + per-user task DBs via S3 Files mount or local session_storage.

Global ``tasks.db`` holds legacy tasks/messages (migrate source) and optional
login_events. Per-user ``{user}.db`` holds tasks/messages; durable copy lives
under ``SESSION_STORAGE_DIR/{user}/{user}.db``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
from typing import Iterable

logger = logging.getLogger("task_store_persistence")

_APPLICATION_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORKING_DIR = os.path.join(_APPLICATION_DIR, "data")
_DEFAULT_MOUNT = "/mnt/app-data"
_APP_DATABASE_SEGMENT = "application-database"
_PERSIST_DEBOUNCE_SECONDS = 20.0
SQLITE_CONNECT_TIMEOUT_SECONDS = 5

_persist_lock = threading.Lock()
_persist_timer: threading.Timer | None = None
_global_dirty = False
_dirty_users: set[str] = set()


def _load_project_name() -> str:
    env_name = os.environ.get("TASK_DB_PROJECT", "").strip()
    if env_name:
        return env_name

    config_json = os.environ.get("APP_CONFIG_JSON", "").strip()
    if config_json:
        try:
            project = json.loads(config_json).get("projectName")
            if isinstance(project, str) and project.strip():
                return project.strip()
        except json.JSONDecodeError:
            pass

    config_path = os.path.join(_APPLICATION_DIR, "config.json")
    try:
        with open(config_path, encoding="utf-8") as handle:
            project = json.load(handle).get("projectName")
            if isinstance(project, str) and project.strip():
                return project.strip()
    except (OSError, json.JSONDecodeError):
        pass

    return "agent-skills"


def mount_dir() -> str:
    return os.environ.get("TASK_DB_MOUNT", _DEFAULT_MOUNT).strip() or _DEFAULT_MOUNT


def persistence_enabled() -> bool:
    """True when the S3 Files mount is writable (global DB durable path)."""
    path = mount_dir()
    return os.path.isdir(path) and os.access(path, os.W_OK)


def working_db_path() -> str:
    """Global/legacy working DB path."""
    custom = os.environ.get("TASK_DB_WORKING_PATH", "").strip()
    if custom:
        return custom
    return os.path.join(_DEFAULT_WORKING_DIR, "tasks.db")


def persistent_db_path() -> str:
    """Mount path for the global/legacy tasks.db."""
    project_name = _load_project_name()
    return os.path.join(
        mount_dir(),
        _APP_DATABASE_SEGMENT,
        project_name,
        "tasks.db",
    )


def _user_segment(user_id: str) -> str:
    from application.utils import sanitize_user_path_segment

    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(f"Invalid user_id for DB path: {user_id!r}")
    return segment


def working_user_db_path(user_id: str) -> str:
    """Per-user tasks/messages working DB under data/users/{segment}.db."""
    segment = _user_segment(user_id)
    return os.path.join(_DEFAULT_WORKING_DIR, "users", f"{segment}.db")


def durable_user_db_path(user_id: str) -> str:
    """Canonical durable path under SESSION_STORAGE_DIR/{user}/{user}.db."""
    from application.utils import get_user_db_path

    return get_user_db_path(user_id)


def persistent_user_db_path(user_id: str) -> str:
    """Log-friendly durable location (same as durable session_storage path)."""
    return durable_user_db_path(user_id)


def _db_ready(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _copy_db_files(source: str, destination: str) -> None:
    """Copy DB bytes only (no metadata/xattrs).

    S3 Files / NFS rejects os.setxattr with Errno 524 (EREMOTEIO). shutil.copy2
    calls copystat → setxattr after a successful content copy, so persist always
    failed even though the file body was written. Use shutil.copy instead.
    """
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy(source, destination)
    for suffix in ("-wal", "-shm"):
        src = source + suffix
        dst = destination + suffix
        if os.path.isfile(src):
            shutil.copy(src, dst)
        elif os.path.isfile(dst):
            os.remove(dst)


def _checkpoint_sqlite(db_path: str) -> None:
    if not os.path.isfile(db_path):
        return
    try:
        conn = sqlite3.connect(db_path, timeout=SQLITE_CONNECT_TIMEOUT_SECONDS)
    except sqlite3.Error as exc:
        logger.warning("Failed to open task DB for checkpoint %s: %s", db_path, exc)
        return
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


def _remove_db_files(path: str) -> None:
    for candidate in (path, path + "-wal", path + "-shm"):
        try:
            if os.path.isfile(candidate):
                os.remove(candidate)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", candidate, exc)


def restore_tasks_db() -> None:
    """Prepare working global tasks.db from S3 Files when persistence is enabled."""
    working = working_db_path()
    persistent = persistent_db_path()
    if not persistence_enabled():
        logger.info("Task DB persistence disabled (no writable mount at %s)", mount_dir())
        return

    os.makedirs(os.path.dirname(working), exist_ok=True)

    if _db_ready(persistent):
        _remove_db_files(working)
        _copy_db_files(persistent, working)
        logger.info("Restored task DB from S3 Files: %s -> %s", persistent, working)
        return

    if os.path.isfile(persistent):
        logger.warning(
            "Persistent task DB empty, starting fresh: %s (size=%s)",
            persistent,
            os.path.getsize(persistent),
        )
    else:
        logger.info("No persistent task DB yet at %s; creating fresh working DB", persistent)

    if any(os.path.isfile(working + suffix) for suffix in ("", "-wal", "-shm")):
        logger.info(
            "Removing pre-existing working task DB (e.g. image-baked test data): %s",
            working,
        )
        _remove_db_files(working)


def restore_user_db(user_id: str) -> bool:
    """Copy durable per-user DB into the working path if available. Returns True if restored."""
    working = working_user_db_path(user_id)
    durable = durable_user_db_path(user_id)
    if not _db_ready(durable):
        return False
    os.makedirs(os.path.dirname(working), exist_ok=True)
    _remove_db_files(working)
    _copy_db_files(durable, working)
    logger.info("Restored user DB from durable path: %s -> %s", durable, working)
    return True


def _persist_to_path(working: str, persistent: str) -> None:
    _checkpoint_sqlite(working)
    _copy_db_files(working, persistent)
    logger.info("Persisted task DB to durable path: %s -> %s", working, persistent)


def _persist_global(*, force: bool = False) -> None:
    global _global_dirty

    if not persistence_enabled():
        _global_dirty = False
        return

    working = working_db_path()
    if not force and not _global_dirty:
        return
    if not _db_ready(working):
        logger.warning("Working global task DB missing, skip persist: %s", working)
        _global_dirty = False
        return

    try:
        _persist_to_path(working, persistent_db_path())
        _global_dirty = False
    except Exception:
        logger.exception("Failed to persist global task DB")


def _persist_user(user_id: str) -> None:
    working = working_user_db_path(user_id)
    if not _db_ready(working):
        logger.warning("Working user DB missing, skip persist: %s", working)
        return
    try:
        _persist_to_path(working, durable_user_db_path(user_id))
    except Exception:
        logger.exception("Failed to persist user DB for %s", user_id)


def persist_tasks_db(*, force: bool = False, user_id: str | None = None) -> None:
    """Flush working SQLite DB(s) to durable storage.

    - ``user_id`` set: persist that user DB only.
    - ``user_id`` None and force: persist global + all dirty users.
    """
    with _persist_lock:
        users: Iterable[str]
        if user_id is not None:
            users = (user_id,)
            do_global = False
        else:
            users = list(_dirty_users)
            do_global = force or _global_dirty

        if do_global:
            _persist_global(force=True)

        for uid in users:
            _persist_user(uid)
            _dirty_users.discard(uid)


def _start_persist_timer_locked() -> None:
    """Caller must hold ``_persist_lock``."""
    global _persist_timer

    def _run() -> None:
        persist_tasks_db(force=True)

    if _persist_timer is not None:
        _persist_timer.cancel()
    _persist_timer = threading.Timer(_PERSIST_DEBOUNCE_SECONDS, _run)
    _persist_timer.daemon = True
    _persist_timer.start()


def schedule_persist(user_id: str | None = None) -> None:
    """Debounced persist after mutations. ``user_id=None`` marks global DB dirty."""
    global _global_dirty

    with _persist_lock:
        if user_id is None:
            if persistence_enabled():
                _global_dirty = True
            elif not _dirty_users:
                return
        else:
            _dirty_users.add(user_id)

        if not _global_dirty and not _dirty_users:
            return
        _start_persist_timer_locked()


def flush_persist(user_id: str | None = None) -> None:
    """Cancel pending debounce and persist immediately.

    - ``user_id`` set: flush that user immediately; reschedule if others remain dirty.
    - ``user_id`` None: flush global and all dirty users.
    """
    global _persist_timer

    with _persist_lock:
        if _persist_timer is not None:
            _persist_timer.cancel()
            _persist_timer = None

    if user_id is not None:
        persist_tasks_db(force=True, user_id=user_id)
        with _persist_lock:
            if _global_dirty or _dirty_users:
                _start_persist_timer_locked()
        return

    persist_tasks_db(force=True)
