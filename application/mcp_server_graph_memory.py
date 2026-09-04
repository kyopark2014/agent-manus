import logging
import sys
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import mcp_graph_memory

from typing import Dict, Literal, Optional
from mcp.server.mcpserver import MCPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("graph-memory")

try:
    mcp = MCPServer(
        name="graph memory",
        instructions=(
            "Search the user's Knowledge Graph (past conversation history) "
            "with the same document-search path as the graph UI. "
            "Use when the answer depends on topics, entities, or events "
            "from earlier chats stored in the graph."
        ),
    )
    logger.info("MCP server initialized successfully")
except Exception as e:
    err_msg = f"Error: {str(e)}"
    logger.info(f"{err_msg}")


######################################
# knowledge graph memory
######################################
@mcp.tool()
def recall_graph_memory(
    question: str,
    mode: Optional[Literal["bfs", "dfs"]] = "bfs",
    budget: Optional[int] = 2000,
) -> Dict:
    """
    Search the user's Knowledge Graph for past conversation history related to the question.

    Same behavior as the graph screen document search (POST /api/graph/query):
    finds matching nodes (label / source text / optional embedding hybrid),
    traverses neighbors (BFS or DFS), and returns source-text excerpts from
    prior chats (topic/relation metadata is omitted).

    Call this when the user asks about something they discussed before, or when
    personal/historical context may live in the knowledge graph rather than
    AgentCore Memory alone (Korean: 과거 대화, 히스토리, 예전에 말한, 그래프).

    Args:
        question: Natural-language search query (required), e.g. "제주도 여행", "회사 주소"
        mode: Traversal mode — "bfs" (default) or "dfs"
        budget: Soft size budget for node/edge listing (200–8000, default 2000)

    Returns:
        On success (same shape as memory retrieve):
            {"text": [
                {"type": "excerpt", "source": "...", "related_topics": [...], "text": "..."},
                ...
            ]}
        On error:
            {"status": "error", "content": [{"text": "..."}]}
    """
    logger.info("###### recall_graph_memory ######")
    logger.info(f"question: {question}, mode: {mode}, budget: {budget}")

    return mcp_graph_memory.recall_graph_memory(question, mode=mode, budget=budget)


if __name__ == "__main__":
    mcp.run(transport="stdio")
