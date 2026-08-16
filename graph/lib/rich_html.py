"""Backward-compatible wrapper — Pattern 1 HTML generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from lib.pattern1_html import GROUP_COLORS, to_pattern1_html  # noqa: F401


def to_rich_html(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str | Path,
    *,
    title: str,
    subtitle: str | None = None,
    community_labels: dict[int, str] | None = None,
) -> None:
    """Alias for Pattern 1 (to_pattern1_html)."""
    to_pattern1_html(
        G,
        communities,
        output_path,
        title=title,
        subtitle=subtitle,
        community_labels=community_labels,
    )
