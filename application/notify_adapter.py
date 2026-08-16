"""Thin Streamlit-compat containers over QueueNotificationSink (agent-skills API).

Prefer calling ``chat._notify_stream`` / ``_notify_tool`` / ``_notify_result``
directly when possible. This adapter only exists so legacy manus/agent code that
expects ``containers["status"].info(...)`` keeps working with the same sink.
"""

from __future__ import annotations

from typing import Any


def _coerce_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for block in message:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            else:
                text = getattr(block, "text", None)
                parts.append(str(text if text is not None else block))
        return "\n".join(parts)
    text = getattr(message, "content", None)
    if text is not None and text is not message:
        return _coerce_text(text)
    return str(message)


class _InfoSlot:
    """Maps Streamlit ``.info()`` to agent-skills notification_queue helpers."""

    def __init__(self, notification_queue: Any | None, *, kind: str = "stream"):
        self._q = notification_queue
        self._kind = kind

    def info(self, message: str) -> None:
        text = _coerce_text(message).strip()
        if not text or self._q is None:
            return
        # Match agent-skills: progress/status text → info notify
        if self._kind == "status":
            self._q.notify(text)
        else:
            # Same path as chat._notify_stream
            self._q.stream(text)

    def markdown(self, message: str) -> None:
        text = _coerce_text(message).strip()
        if text and self._q is not None:
            self._q.stream(text)


def make_containers(notification_queue: Any | None = None) -> dict:
    """Build status/tools/notification slots backed by QueueNotificationSink."""
    status = _InfoSlot(notification_queue, kind="status")
    body = _InfoSlot(notification_queue, kind="stream")
    return {
        "status": status,
        "tools": status,
        "notification": [body for _ in range(100)],
        # Explicit handle for agent-skills-style helpers
        "notification_queue": notification_queue,
    }
