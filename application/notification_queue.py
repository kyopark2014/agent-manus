import logging
import queue
from typing import Any

logger = logging.getLogger("notification_queue")


class QueueNotificationSink:
    """Forwards agent output to a queue for SSE streaming."""

    def __init__(self, message_queue: queue.Queue):
        self._q = message_queue
        self._streaming_slot = None
        self._tool_slots: dict[str, object] = {}
        self._tool_names: dict[str, str] = {}

    def reset(self):
        self._streaming_slot = None
        self._tool_slots = {}
        self._tool_names = {}

    def notify(self, message: str):
        self._streaming_slot = None
        self._q.put({"type": "info", "data": message})

    def status(self, message: str):
        """Emit pipeline status as a normal Info notification (not a sticky bar)."""
        stripped = (message or "").strip()
        if not stripped:
            return
        if stripped.startswith("[status]"):
            stripped = stripped[len("[status]") :].lstrip("\n").strip()
        self._streaming_slot = None
        self._q.put({"type": "info", "data": stripped})

    def respond(self, message: str):
        self._streaming_slot = None
        self._q.put({"type": "markdown", "data": message})

    def stream(self, message: str):
        if self._streaming_slot is None:
            self._streaming_slot = object()
        self._q.put({"type": "markdown", "data": message})

    def commit_text_segment(self, message: str):
        """Persist a completed assistant text segment before tool events."""
        stripped = message.strip()
        if not stripped:
            return
        self._streaming_slot = None
        self._q.put({"type": "text_segment", "data": stripped})

    def result(self, message: str):
        was_streaming = self._streaming_slot is not None
        self._streaming_slot = None
        if not was_streaming:
            self._q.put({"type": "markdown", "data": message})

    def tool_update(self, tool_use_id: str, message: str):
        self._streaming_slot = None
        if tool_use_id not in self._tool_slots:
            self._tool_slots[tool_use_id] = object()
        self._q.put(
            {
                "type": "info",
                "data": message,
                "toolUseId": tool_use_id,
                "toolName": self._tool_names.get(tool_use_id, ""),
            }
        )

    def plan(self, message: str):
        """Emit a Manus planner plan as a dedicated timeline event."""
        stripped = (message or "").strip()
        if not stripped:
            return
        self._streaming_slot = None
        self._q.put({"type": "plan", "data": stripped})

    def register_tool(self, tool_use_id: str, name: str):
        self._tool_names[tool_use_id] = name

    def get_tool_name(self, tool_use_id: str) -> str:
        return self._tool_names.get(tool_use_id, "")
