"""Agent Skills application package (Web UI + co-located LangGraph agent)."""

import os
import sys

# Agent modules (chat, langgraph_agent, mcp_*, …) use bare imports when run as
# AgentCore entrypoint from this directory. Ensure the same resolution when the
# package is loaded as `application.*` from the repo root.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
