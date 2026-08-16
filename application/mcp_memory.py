"""
AgentCore Memory Tool 
modified from strands_tools.agent_core_memory: https://github.com/strands-agents/tools/blob/main/src/strands_tools/agent_core_memory.py

Memory Record Operations:
   • retrieve_memory_records: Semantic search for extracted memories and user profile
   • list_memory_records: List all memory records
   • get_memory_record: Get specific memory record
"""

import json
import logging
import boto3
import os
import sys
import agentcore_memory

from typing import Dict, List, Optional, Set

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("memory")

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config

config = load_config()

bedrock_region = config['region']
projectName = config['projectName']

bedrock_agent_core_client = boto3.client(
    "bedrock-agentcore",
    region_name=bedrock_region
)

def _format_namespace_for_search(
    namespace_template: str,
    actor_id: str,
    strategy_id: str = "",
) -> str:
    """
    Format a strategy namespace template for retrieve/list.

    AgentCore Memory matches namespace as a prefix. Summary strategies store records
    under /users/{actorId}/sessions/{sessionId}, but recall must not pin a single
    (often ephemeral) sessionId — search /users/{actorId}/sessions so all sessions
    for this actor are included.
    """
    template = (namespace_template or "").strip()
    if not template:
        return ""

    # Session-scoped templates → actor-level sessions prefix (prefix match).
    if "{sessionId}" in template:
        return f"/users/{actor_id}/sessions"

    try:
        return template.format(
            actorId=actor_id,
            memoryStrategyId=strategy_id,
        )
    except (KeyError, ValueError, IndexError):
        return template

def _namespace_belongs_to_actor(namespace: str, actor_id: str) -> bool:
    """
    Return True only if the namespace is scoped to the current actor.
    Prevents cross-user leakage when strategies store literal /users/<other> paths.
    """
    if not namespace or not actor_id:
        return False
    if namespace == f"/users/{actor_id}/preferences":
        return True
    if namespace == f"/users/{actor_id}/facts":
        return True
    if namespace == f"/users/{actor_id}/sessions":
        return True
    if namespace.startswith(f"/users/{actor_id}/sessions/"):
        return True
    if namespace == f"/users/{actor_id}":
        return True
    # Allow nested paths that include this actor as a path segment
    # e.g. /users/{actorId}/preferences|/facts|/sessions/... after formatting
    parts = [p for p in namespace.split("/") if p]
    return actor_id in parts

def get_search_namespaces(
    memory_id: str,
    actor_id: str,
    session_id: str,
    default_namespace: str,
) -> List[str]:
    """
    Build namespaces to search for the current actor only.
    Always includes the user preference namespace; strategy namespaces are included
    only when they resolve to this actor (literal /users/<other> are skipped).

    Summary uses /users/{actorId}/sessions (actor prefix), not a single sessionId.
    session_id is unused for search (kept for call-site compatibility).
    """
    _ = session_id  # intentionally ignored: do not bind Summary search to an ephemeral session
    namespaces: Set[str] = set()

    if default_namespace and _namespace_belongs_to_actor(default_namespace, actor_id):
        namespaces.add(default_namespace)
    elif default_namespace:
        logger.warning(
            f"Ignoring default_namespace not owned by actor {actor_id}: {default_namespace}"
        )

    # Leaf preference path — do NOT use bare /users/{actorId} (prefixes /facts and /sessions)
    user_profile_namespace = f"/users/{actor_id}/preferences"
    namespaces.add(user_profile_namespace)
    # Summary prefix — all sessions for this actor (AgentCore namespace prefix match)
    namespaces.add(f"/users/{actor_id}/sessions")

    try:
        strategies = agentcore_memory.load_memory_strategy(memory_id)
        for strategy in strategies or []:
            strategy_id = strategy.get("strategyId") or strategy.get("id") or ""
            for ns_template in strategy.get("namespaces") or []:
                formatted = _format_namespace_for_search(ns_template, actor_id, strategy_id)
                if not formatted:
                    continue
                if not _namespace_belongs_to_actor(formatted, actor_id):
                    logger.info(
                        f"Skipping strategy namespace not owned by actor {actor_id}: {formatted}"
                    )
                    continue
                namespaces.add(formatted)
    except Exception as e:
        logger.warning(f"Failed to load strategy namespaces, using defaults only: {e}")

    namespace_list = sorted(namespaces)
    logger.info(f"search namespaces for actor {actor_id}: {namespace_list}")
    return namespace_list

def retrieve_memory_records(
    memory_id: str,
    namespace: str,
    search_query: str,
    max_results: Optional[int] = 20, 
    next_token: Optional[str] = None,
) -> Dict:
    """
    Retrieve memory records using semantic search.

    Performs a semantic search across memory records in the specified namespace,
    returning records that semantically match the search query. Results are ranked
    by relevance to the query.

    Args:
        memory_id: ID of the memory store to search in
        namespace: Namespace to search within (e.g., "/users/{actorId}")
        search_query: Natural language query to search for
        max_results: Maximum return in a single call (default: 20, max: 100)
        next_token: Pagination token for retrieving additional results

    Returns:
        Dict: Response containing matching memory records and optional next_token
    """
    logger.info(f"###### retrieve_memory_records ######")
    logger.info(f"memory_id: {memory_id}, namespace: {namespace}, search_query: {search_query}, max_results: {max_results}, next_token: {next_token}")

    # Prepare request parameters
    topK = 20 # Maximum number of top-scoring memory records to return
    params = {"memoryId": memory_id, "namespace": namespace, "searchCriteria": {"topK":topK, "searchQuery": search_query}}
    if max_results is not None:
        params["maxResults"] = max_results
    if next_token is not None:
        params["nextToken"] = next_token

    return bedrock_agent_core_client.retrieve_memory_records(**params)

def get_memory_record(
    memory_id: str,
    memory_record_id: str,
) -> Dict:
    """Get a specific memory record."""
    return bedrock_agent_core_client.get_memory_record(
        memoryId=memory_id,
        memoryRecordId=memory_record_id,
    )

def list_memory_records(
    memory_id: str,
    namespace: str,
    max_results: Optional[int] = None,
    next_token: Optional[str] = None,
) -> Dict:
    """List memory records."""

    logger.info(f"###### list_memory_records ######")
    logger.info(f"memory_id: {memory_id}, namespace: {namespace}, max_results: {max_results}, next_token: {next_token}")

    params = {"memoryId": memory_id}
    if namespace is not None:
        params["namespace"] = namespace
    if max_results is not None:
        params["maxResults"] = max_results
    if next_token is not None:
        params["nextToken"] = next_token
    return bedrock_agent_core_client.list_memory_records(**params)

def _extract_contents_from_response(response: Dict) -> List:
    contents = []
    if not isinstance(response, dict):
        return contents

    summaries = response.get("memoryRecordSummaries") or []
    for memory_record_summary in summaries:
        try:
            json_content = memory_record_summary["content"]["text"]
            content = json.loads(json_content)
            logger.info(f"content: {content}")
            contents.append(content)
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse memory record content: {e}")
            text = memory_record_summary.get("content", {}).get("text")
            if text:
                contents.append(text)
    return contents

def recall_memory(
    action: str,
    query: Optional[str] = None,
    memory_record_id: Optional[str] = None,
    max_results: Optional[int] = 10,
    next_token: Optional[str] = None,
) -> Dict:
    """
    Recall agent memories including user profile preferences.

    Supported Actions:
    - retrieve: Semantic search across memories and user profile namespaces
    - list: Browse stored memories including user profile records
    - get: Fetch a specific memory by ID
    """
    try:
        # Prefer user_id injected when the memory MCP process was spawned
        user_id = (os.environ.get("AGENTCORE_USER_ID") or "").strip()
        if not user_id:
            user_id = "default"
            logger.info(f"AGENTCORE_USER_ID was empty, using default: {user_id}")
        memory_id, actor_id, session_id, namespace = agentcore_memory.load_memory_variables(user_id)
        logger.info(f"memory_id: {memory_id}, user_id: {user_id}, actor_id: {actor_id}, session_id: {session_id}, namespace: {namespace}")

        search_namespaces = get_search_namespaces(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            default_namespace=namespace,
        )
        
        # Execute the appropriate action
        action = (action or "retrieve").strip().lower()
        if action == "retrieve" and not (query or "").strip():
            query = "집 회사 주소 통근 교통 선호 프로필 요약 사실 user preferences home office commute summary facts"
            logger.info(f"retrieve query was empty; using default profile query: {query}")

        logger.info(f"###### action: {action} ######")
        try:
            if action == "retrieve":
                contents = []
                seen = set()
                errors = []
                for ns in search_namespaces:
                    try:
                        response = retrieve_memory_records(
                            memory_id=memory_id,
                            namespace=ns,
                            search_query=query,
                            max_results=max_results,
                            next_token=next_token if ns == search_namespaces[0] else None,
                        )
                        for content in _extract_contents_from_response(response):
                            key = json.dumps(content, sort_keys=True, default=str)
                            if key not in seen:
                                seen.add(key)
                                contents.append(content)
                    except Exception as ns_error:
                        logger.warning(f"Retrieve failed for namespace {ns}: {ns_error}")
                        errors.append(f"{ns}: {ns_error}")

                if not contents and errors:
                    return {
                        "status": "error",
                        "content": [{
                            "text": (
                                "Memory retrieve failed for all namespaces "
                                f"(often IAM AccessDenied on RetrieveMemoryRecords): "
                                f"{'; '.join(errors)}"
                            )
                        }],
                    }

                return {
                    "text": contents
                }
            elif action == "list":
                relevant_data = {"memoryRecordSummaries": []}
                seen_ids = set()
                errors = []
                for ns in search_namespaces:
                    try:
                        response = list_memory_records(
                            memory_id=memory_id,
                            namespace=ns,
                            max_results=max_results,
                            next_token=next_token if ns == search_namespaces[0] else None,
                        )
                        if isinstance(response, dict):
                            for summary in response.get("memoryRecordSummaries") or []:
                                record_id = summary.get("memoryRecordId")
                                if record_id and record_id in seen_ids:
                                    continue
                                if record_id:
                                    seen_ids.add(record_id)
                                relevant_data["memoryRecordSummaries"].append(summary)
                            if "nextToken" in response and ns == search_namespaces[0]:
                                relevant_data["nextToken"] = response["nextToken"]
                    except Exception as ns_error:
                        logger.warning(f"List failed for namespace {ns}: {ns_error}")
                        errors.append(f"{ns}: {ns_error}")

                if not relevant_data["memoryRecordSummaries"] and errors:
                    return {
                        "status": "error",
                        "content": [{
                            "text": (
                                "Memory list failed for all namespaces "
                                f"(often IAM AccessDenied on ListMemoryRecords): "
                                f"{'; '.join(errors)}"
                            )
                        }],
                    }

                return {
                    "status": "success",
                    "content": [
                        {"text": f"Memories listed successfully: {json.dumps(relevant_data, default=str)}"}
                    ],
                }
            elif action == "get":
                response = get_memory_record(
                    memory_id=memory_id,
                    memory_record_id=memory_record_id,
                )
                # Extract only the relevant "memoryRecord" field from the response
                memory_record = response.get("memoryRecord", {}) if isinstance(response, dict) else {}
                return {
                    "status": "success",
                    "content": [
                        {"text": f"Memory retrieved successfully: {json.dumps(memory_record, default=str)}"}
                    ],
                }
            else:
                return {
                    "status": "error",
                    "content": [{"text": f"Unsupported action: {action}. Supported actions: retrieve, list, get"}],
                }
        except Exception as e:
            error_msg = f"API error: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "content": [{"text": error_msg}]}

    except Exception as e:
        logger.error(f"Unexpected error in recall_memory tool: {str(e)}")
        return {"status": "error", "content": [{"text": str(e)}]}
