"""Resolve and dispatch Knowledge Graph HTML patterns (pattern1|2|3)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import networkx as nx

GRAPH_PATTERNS = ("pattern1", "pattern2", "pattern3")
DEFAULT_GRAPH_PATTERN = "pattern1"


def normalize_graph_pattern(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "").replace("_", "")
    aliases = {
        "pattern1": "pattern1",
        "p1": "pattern1",
        "1": "pattern1",
        "forceatlas": "pattern1",
        "pattern2": "pattern2",
        "p2": "pattern2",
        "2": "pattern2",
        "neo4j": "pattern2",
        "neo4jexplore": "pattern2",
        "pattern3": "pattern3",
        "p3": "pattern3",
        "3": "pattern3",
        "holistic": "pattern3",
        "holisticview": "pattern3",
    }
    return aliases.get(raw, DEFAULT_GRAPH_PATTERN)


def _sanitize_user_segment(user_id: str) -> str:
    raw = (user_id or "").strip()
    if not raw or (raw.startswith("v1.") and raw.count(".") >= 2) or len(raw) > 128:
        return "default"
    segment = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return segment or "default"


def resolve_graph_pattern(*, user_id: str | None = None) -> str:
    """Resolve pattern: GRAPH_PATTERN env → user settings.json → default."""
    env_raw = os.getenv("GRAPH_PATTERN", "").strip()
    if env_raw:
        return normalize_graph_pattern(env_raw)

    if user_id:
        try:
            from lib.config import session_storage_dir

            path = (
                session_storage_dir()
                / _sanitize_user_segment(user_id)
                / "settings.json"
            )
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and "graph_pattern" in raw:
                    return normalize_graph_pattern(raw.get("graph_pattern"))
        except (OSError, json.JSONDecodeError, ImportError):
            pass

    return DEFAULT_GRAPH_PATTERN


def write_pattern_html(
    pattern: str,
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str | Path,
    *,
    title: str,
    subtitle: str | None = None,
    community_labels: dict[int, str] | None = None,
) -> str:
    """Write graph HTML using the selected pattern. Returns normalized pattern id."""
    pid = normalize_graph_pattern(pattern)
    kwargs = dict(
        title=title,
        subtitle=subtitle,
        community_labels=community_labels,
    )
    if pid == "pattern2":
        from lib.pattern2_html import to_pattern2_html

        to_pattern2_html(G, communities, output_path, **kwargs)
    elif pid == "pattern3":
        from lib.pattern3_html import to_pattern3_html

        to_pattern3_html(G, communities, output_path, **kwargs)
    else:
        from lib.pattern1_html import to_pattern1_html

        to_pattern1_html(G, communities, output_path, **kwargs)
    return pid
