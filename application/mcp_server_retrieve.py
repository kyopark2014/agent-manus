import logging
import sys
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import mcp_retrieve

from mcp.server.fastmcp import FastMCP 

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("retrieve-server")

try:
    mcp = FastMCP(
        name = "mcp-retrieve",
        instructions=(
            "You are a helpful assistant. "
            "You search the user's knowledge base with RAG. "
            "Use this for information lookup alongside web/wiki search when relevant. "
            "Results are scoped to the current user's uploaded documents only."
        ),
    )
    logger.info("MCP server initialized successfully")
except Exception as e:
        err_msg = f"Error: {str(e)}"
        logger.info(f"{err_msg}")

######################################
# RAG
######################################
@mcp.tool()
def retrieve(keyword: str) -> str:
    """
    Search the user's knowledge base (RAG) for relevant documents.
    Use together with web/wiki search when looking up information the user may have stored.
    Only returns documents owned by the current user (metadata owner filter).
    keyword: the search query / keyword to look up
    return: matching document excerpts from the knowledge base
    """
    logger.info(f"search --> keyword: {keyword}")

    return mcp_retrieve.retrieve(keyword)

if __name__ =="__main__":
    mcp.run(transport="stdio")


