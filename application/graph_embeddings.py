"""Application-facing wrappers for graph node embeddings (hybrid document search).

Canonical implementation lives in ``graph/lib/embeddings.py`` so the publish
pipeline and the FastAPI query path share one code path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"


def _ensure_graph_lib() -> None:
    root = str(_GRAPH_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)


def _emb():
    _ensure_graph_lib()
    from lib import embeddings as emb  # type: ignore

    return emb


def embeddings_path_for(graph_json: Path) -> Path:
    return _emb().embeddings_path_for(graph_json)


def build_node_embeddings(
    graph_json: Path,
    out_path: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    return _emb().build_node_embeddings(graph_json, out_path, force=force)


def ensure_node_embeddings(graph_json: Path) -> dict[str, Any] | None:
    return _emb().ensure_node_embeddings(graph_json)


def maybe_build_node_embeddings(graph_json: Path) -> Path | None:
    return _emb().maybe_build_node_embeddings(graph_json)


def find_start_nodes_by_embedding(
    question: str,
    graph_json: Path,
    *,
    k: int = 5,
    min_score: float = 0.35,
) -> list[tuple[float, str]]:
    return _emb().find_start_nodes_by_embedding(
        question, graph_json, k=k, min_score=min_score
    )


def cosine_top_k(
    query_vec: list[float],
    index: dict[str, Any],
    *,
    k: int = 5,
    min_score: float = 0.35,
) -> list[tuple[float, str]]:
    return _emb().cosine_top_k(query_vec, index, k=k, min_score=min_score)


def embed_texts(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    return _emb().embed_texts(texts, model=model)
