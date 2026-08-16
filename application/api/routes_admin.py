"""Admin dashboard API — basic registrant metrics from the task store."""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

try:
    from application.api.routes_auth import require_user_id
    from application import task_store, utils
except ImportError:
    from routes_auth import require_user_id  # type: ignore
    import task_store  # type: ignore
    import utils  # type: ignore

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_admin_emails() -> set[str]:
    cfg = utils.load_config()
    emails: list[str] = []
    raw = cfg.get("admin_emails")
    if isinstance(raw, list):
        emails.extend(str(item).strip() for item in raw if str(item).strip())
    elif isinstance(raw, str) and raw.strip():
        emails.extend(part.strip() for part in raw.split(",") if part.strip())

    env = os.environ.get("ADMIN_EMAILS", "").strip()
    if env:
        emails.extend(part.strip() for part in env.split(",") if part.strip())

    return {email.lower() for email in emails}


def is_admin_user(user_id: str) -> bool:
    """Admin when listed in admin_emails, or when no admins are configured."""
    admins = get_admin_emails()
    if not admins:
        return True
    return user_id.strip().lower() in admins


def require_admin(request: Request) -> str:
    user_id = require_user_id(request)
    if not is_admin_user(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def _empty_dashboard() -> dict:
    return {
        "summary": {
            "total_users": 0,
            "google_users": 0,
            "legacy_users": 0,
            "total_tasks": 0,
            "total_messages": 0,
            "total_logins": 0,
            "logins_today": 0,
            "active_users_today": 0,
            "logins_7d": 0,
            "active_users_7d": 0,
        },
        "users": [],
        "recent_logins": [],
        "daily_logins": [],
    }


def _dashboard_from_tasks() -> dict:
    """Build lightweight dashboard stats from the local SQLite task store."""
    try:
        conn = task_store._connect()
    except Exception:
        return _empty_dashboard()

    try:
        tasks = conn.execute(
            "SELECT user_id, id, created_at, updated_at FROM tasks"
        ).fetchall()
        messages = conn.execute(
            "SELECT task_id, created_at FROM messages"
        ).fetchall()
    except sqlite3.Error:
        return _empty_dashboard()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    user_tasks: dict[str, list] = defaultdict(list)
    for row in tasks:
        user_tasks[str(row["user_id"])].append(row)

    task_msg_counts: dict[str, int] = defaultdict(int)
    msg_times: list[str] = []
    for row in messages:
        task_msg_counts[str(row["task_id"])] += 1
        if row["created_at"]:
            msg_times.append(str(row["created_at"]))

    users = []
    for user_id, rows in sorted(user_tasks.items()):
        msg_count = sum(task_msg_counts.get(str(r["id"]), 0) for r in rows)
        first_seen = min((r["created_at"] for r in rows if r["created_at"]), default=None)
        last_active = max(
            (r["updated_at"] or r["created_at"] for r in rows if r["created_at"] or r["updated_at"]),
            default=None,
        )
        is_google = "@" in user_id
        users.append(
            {
                "user_id": user_id,
                "task_count": len(rows),
                "message_count": msg_count,
                "login_count": 0,
                "first_seen": first_seen,
                "last_active": last_active,
                "last_login": last_active,
                "auth_methods": ["google" if is_google else "local"],
                "is_google": is_google,
            }
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    active_today = {
        u["user_id"]
        for u in users
        if (u.get("last_active") or "").startswith(today)
    }

    return {
        "summary": {
            "total_users": len(users),
            "google_users": sum(1 for u in users if u["is_google"]),
            "legacy_users": sum(1 for u in users if not u["is_google"]),
            "total_tasks": len(tasks),
            "total_messages": len(messages),
            "total_logins": 0,
            "logins_today": 0,
            "active_users_today": len(active_today),
            "logins_7d": 0,
            "active_users_7d": len(users),
        },
        "users": users,
        "recent_logins": [],
        "daily_logins": [],
    }


@router.get("/dashboard")
def get_dashboard(_admin: str = Depends(require_admin)) -> dict:
    return _dashboard_from_tasks()
