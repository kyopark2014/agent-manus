"""
Knowledge Graph memory tool for MCP.

Wraps application.graph_query.query_user_graph — the same BFS/DFS + excerpt
path used by POST /api/graph/query (graph UI document search) — so the agent
can recall past conversation history stored in the user's knowledge graph.

Return shape mirrors mcp_memory.recall_memory(retrieve):
  success → {"text": [<content items LLM can cite>]}
  error   → {"status": "error", "content": [{"text": "..."}]}
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("graph-memory")

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

_MAX_EXCERPTS = 12


def _current_user_id() -> str:
    """User id injected into the MCP process env by chat.create_agent()."""
    return (os.environ.get("AGENTCORE_USER_ID") or "").strip()


def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "content": [{"text": message}]}


def _extract_contents(result: dict[str, Any]) -> List[Any]:
    """
    Flatten graph query output into LLM-ready excerpt items.

    Topic labels and relations are omitted: they add tokens without
    citable source text. Related entity names stay on each excerpt as
    ``related_topics``.
    """
    contents: List[Any] = []

    if result.get("message") and not result.get("nodes") and not result.get("sources"):
        # No matches — keep empty list like memory retrieve with no hits
        logger.info("graph memory empty: %s", result.get("message"))
        return contents

    excerpt_count = 0
    for source in result.get("sources") or []:
        if not source.get("readable", True):
            continue
        name = source.get("name") or Path(str(source.get("path") or "")).name or "unknown"
        labels = [str(lb) for lb in (source.get("matched_labels") or []) if lb][:8]
        for excerpt in source.get("excerpts") or []:
            text = str(excerpt).strip()
            if not text:
                continue
            item: Dict[str, Any] = {
                "type": "excerpt",
                "source": name,
                "text": text,
            }
            if labels:
                item["related_topics"] = labels
            contents.append(item)
            excerpt_count += 1
            if excerpt_count >= _MAX_EXCERPTS:
                break
        if excerpt_count >= _MAX_EXCERPTS:
            break

    logger.info("extracted contents: excerpts=%s", excerpt_count)
    return contents


def recall_graph_memory(
    question: str,
    mode: Optional[Literal["bfs", "dfs"]] = "bfs",
    budget: Optional[int] = 2000,
) -> Dict[str, Any]:
    """
    Search the current user's knowledge graph for past history related to ``question``.

    Same semantics as the graph UI document search (POST /api/graph/query).
    On success returns ``{"text": [...]}`` like memory retrieve.
    """
    try:
        import utils
        from graph_query import query_user_graph
    except ImportError as e:
        logger.error(f"Failed to import graph modules: {e}")
        return _error(f"Graph memory unavailable: {e}")

    user_id = _current_user_id()
    if not user_id:
        user_id = "default"
        logger.info("AGENTCORE_USER_ID was empty, using default: %s", user_id)

    logger.info(
        "###### recall_graph_memory ###### user_id=%s question=%r mode=%s budget=%s",
        user_id,
        question,
        mode,
        budget,
    )

    if not utils.is_knowledge_graph_enabled(user_id):
        return _error(
            "Knowledge Graph is disabled in Settings. "
            "Enable it to search past conversation history."
        )

    question = (question or "").strip()
    if not question:
        return _error("question is required")

    graph_root = Path(utils.get_user_graph_dir(user_id))
    graph_json = graph_root / "out" / "graph.json"
    if not graph_json.is_file():
        return _error(
            "그래프가 아직 없습니다. Knowledge Graph를 생성한 뒤 다시 검색하세요."
        )

    try:
        result = query_user_graph(
            graph_json,
            question,
            mode=mode or "bfs",
            budget=int(budget or 2000),
            allowed_roots=[graph_root, graph_root / "corpus", graph_root / "out"],
            use_embeddings=utils.is_hybrid_graph_search_enabled(),
        )
    except ValueError as e:
        return _error(str(e))
    except FileNotFoundError as e:
        return _error(str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("graph memory failed")
        return _error(f"query failed: {e}")

    contents = _extract_contents(result)
    # Match mcp_memory.recall_memory(retrieve) success shape
    return {"text": contents}
