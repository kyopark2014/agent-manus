import logging
import sys
import mcp_memory

from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP 

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("memory")

try:
    mcp = FastMCP(
        name = "memory"
    )
    logger.info("MCP server initialized successfully")
except Exception as e:
        err_msg = f"Error: {str(e)}"
        logger.info(f"{err_msg}")

######################################
# memory
######################################
@mcp.tool()
def recall_memory(
    action: str,
    query: Optional[str] = None,
    memory_record_id: Optional[str] = None,
    max_results: Optional[int] = None,
    next_token: Optional[str] = None,
) -> Dict:
    """
    Look up the user's long-term memories and profile BEFORE answering personal questions.

    Call this tool whenever the answer depends on stored personal context, for example:
    home/office address, commute, preferred transport, schedule, diet, brands,
    or anything the user previously shared (Korean: 집, 회사, 통근, 선호, 주소, 프로필).

    Do NOT guess personal facts. Prefer retrieve first; use list if retrieve is empty.

    Actions:
    - retrieve: Semantic search (recommended default).
        Example: action="retrieve", query="집 주소 회사 위치 통근 교통"
    - list: Browse stored memory / profile records in the user namespace.
    - get: Fetch one record by memory_record_id.

    Args:
        action: One of "retrieve", "list", "get"
        query: Search text for retrieve (required for retrieve)
        memory_record_id: Required for get
        max_results: Optional result cap
        next_token: Optional pagination token

    Returns:
        Dict with matching memory content or operation status
    """
    logger.info(f"###### recall_memory ######")
    logger.info(f"action: {action}")

    return mcp_memory.recall_memory(action, query, memory_record_id, max_results, next_token)

if __name__ =="__main__":
    mcp.run(transport="stdio")
