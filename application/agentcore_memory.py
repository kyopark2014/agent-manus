import os
import json
import logging
import sys
import uuid
import time

from bedrock_agentcore.memory import MemoryClient
from datetime import datetime, timezone
import re

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("agentcore_memory")

def load_config():
    config = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config

config = load_config()

bedrock_region = config.get('region')
projectName = config.get('projectName')
agentcore_memory_role = config.get('agentcore_memory_role')

memory_client = MemoryClient(region_name=bedrock_region)

# AgentCore Memory namespace pattern rejects emails (@, .):
# [a-zA-Z0-9/*][a-zA-Z0-9-_/*]*(?::[a-zA-Z0-9-_/*]+)*[a-zA-Z0-9-_/*]*
_INVALID_ACTOR_CHARS = re.compile(r"[^a-zA-Z0-9_-]+")


def sanitize_memory_actor_id(user_id: str) -> str:
    """Make a user id safe for AgentCore Memory actor_id / namespace / strategy name."""
    raw = (user_id or "").strip() or "default"
    cleaned = _INVALID_ACTOR_CHARS.sub("_", raw).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        cleaned = "default"
    if not re.match(r"^[a-zA-Z0-9]", cleaned):
        cleaned = f"u_{cleaned}"
    return cleaned[:128]


def resolve_memory_actor_id(user_id: str) -> str:
    """Map application user_id → API-safe AgentCore Memory actor_id."""
    actor_id = sanitize_memory_actor_id(user_id)
    if actor_id != (user_id or "").strip():
        logger.info(f"memory actor_id sanitized: {user_id!r} -> {actor_id!r}")
    return actor_id


def load_memory_variables(user_id: str):
    """
    Resolve AgentCore memory identifiers for a user.

    memory_id comes from config.json (installer) or is retrieved/created.
    actor_id / namespace are derived from sanitized user_id.
    session_id is ephemeral — no per-user JSON cache file.
    """
    actor_id = resolve_memory_actor_id(user_id)
    session_id = uuid.uuid4().hex
    namespace = f"/users/{actor_id}/preferences"

    memory_id = config.get("memory_id")
    if memory_id:
        logger.info(f"memory_id from config.json: {memory_id}")
    else:
        logger.info("memory_id is None, attempting to retrieve existing memory...")
        memory_id = retrieve_memory_id()
        if memory_id is None:
            logger.info("No existing memory found, creating new memory...")
            memory_id = create_memory()

    logger.info(
        f"memory_id: {memory_id}, actor_id: {actor_id}, "
        f"session_id: {session_id}, namespace: {namespace}"
    )
    return memory_id, actor_id, session_id, namespace

# CUSTOM_PROMPT = (
#     "You are tasked with analyzing conversations to extract the user's general preferences."
#      "You'll be analyzing two sets of data:"
#      "<past_conversation>"
#      "[Past conversations between the user and system will be placed here for context]"
#      "</past_conversation>"
#      "<current_conversation>"
#      "[The current conversation between the user and system will be placed here]"
#      "</current_conversation>"
#      "Your job is to identify and categorize the user's general preferences across various topics and domains."
#      "- Extract user preferences for different types of content, services, or products they show interest in."
#      "- Identify communication style preferences, such as formal vs casual, detailed vs concise."
#      "- Recognize technology preferences, such as specific platforms, tools, or applications they prefer."
#      "- Note any recurring themes or topics the user is particularly interested in or knowledgeable about."
#      "- Capture any specific requirements or constraints they mention in their interactions."
#      "use Korean."
# )

USER_PREFERENCE_PROMPT = (
    "You are tasked with analyzing conversations to extract the user's preferences. You'll be analyzing two sets of data:\n"
    "<past_conversation>\n"
    "[Past conversations between the user and system will be placed here for context]\n"
    "</past_conversation>\n"
    "<current_conversation>\n"
    "[The current conversation between the user and system will be placed here]\n"
    "</current_conversation>\n"
    "Your job is to identify and categorize the user's preferences into two main types:\n"
    "- Explicit preferences: Directly stated preferences by the user.\n"
    "- Implicit preferences: Inferred from patterns, repeated inquiries, or contextual clues. Take a close look at user's request for implicit preferences.\n"
    "For explicit preference, extract only preference that the user has explicitly shared. Do not infer user's preference.\n"
    "For implicit preference, it is allowed to infer user's preference, but only the ones with strong signals, such as requesting something multiple times.\n"
    "Use Korean.\n"
)

SUMMARY_PROMPT = (
    "You will be given a text block and a list of summaries you previously generated when available.\n"
    "<task>\n"
    "- When the previously generated is not available, your goal is to summarize the given text block.\n"
    "- When there is existing summary, your goal is to extend summary by taking into account the given text block.\n"
    "- If there are queries/topics specified in the text block, your generated summary need to cover those queries/topics.\n"
    "- If there are instructions in the text block **guiding you how to generate suummary**, you MUST follow them.\n"
    "</task>\n"
    "Use Korean.\n"
)

SEMANTIC_PROMPT = (
    "You are a long-term memory extraction agent supporting a lifelong learning system.\n"
    "Your task is to identify and extract meaningful information about the users from a given list of messages.\n"
    "Analyze the conversation and extract structured information about the user according to the schema below.\n"
    "Only include details that are explicitly stated or can be logically inferred from the conversation.\n"
    "- Extract information ONLY from the user messages. You should use assistant messages only as supporting context.\n"
    "- If the conversation contains no relevant or noteworthy information, return an empty list.\n"
    "- Do NOT extract anything from prior conversation history, even if provided. Use it solely for context.\n"
    "- Do NOT incorporate external knowledge.\n"
    "- Avoid duplicate extractions.\n"
    "Use Korean.\n"
)

# Backward-compatible alias
SEMENTIC_PROMPT = SEMANTIC_PROMPT

SEMANTIC_CONSOLIDATION_PROMPT = (
    "You consolidate newly extracted facts with existing long-term semantic memories.\n"
    "- Merge duplicates; keep the most specific and recent facts.\n"
    "- Do not invent facts that were not extracted.\n"
    "- Prefer clear, atomic statements in Korean.\n"
    "Use Korean.\n"
)

def retrieve_memory_id():
    memory_id = None
    memory_name = projectName.replace("-", "_")  # use projectName as memory name

    memories = memory_client.list_memories()
    logger.info(f"memories: {memories}")
    for memory in memories:            
        logger.info(f"Memory ID: {memory.get('id')}")
        if memory.get('id').split("-")[0] == memory_name:
            logger.info(f"The memory of {memory_name} was found")
            memory_id = memory.get('id')
            logger.info(f"Memory Arn: {memory.get('arn')}")
            break

    return memory_id

def load_memory_strategy(memory_id: str):
    strategies = memory_client.get_memory_strategies(memory_id)
    logger.info(f"strategies: {strategies}")
    return strategies

# Must be an inference profile available in the configured region (us-west-2).
# Foundation IDs like anthropic.claude-3-5-haiku-... fail UpdateMemory with:
# "Bedrock model is not available in region us-west-2"
MEMORY_EXTRACTION_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Shared strategies per memory_id (not per actor). Isolation via {actorId}/{sessionId}.
# AgentCore allows at most 6 strategies per memory — treat that as strategy *kinds*.
USER_PREFERENCE_STRATEGY_NAME = "UserPreference"
# Prefer a leaf path so /users/{actorId} does not prefix-match /facts or /sessions.
USER_PREFERENCE_NAMESPACE_TEMPLATE = "/users/{actorId}/preferences"
SUMMARY_STRATEGY_NAME = "Summary"
# AgentCore requires {sessionId} in Summary strategy namespaces.
SUMMARY_NAMESPACE_TEMPLATE = "/users/{actorId}/sessions/{sessionId}"
SEMANTIC_STRATEGY_NAME = "Semantic"
SEMANTIC_NAMESPACE_TEMPLATE = "/users/{actorId}/facts"


def _strategy_namespaces(strategy: dict) -> list:
    return list(strategy.get("namespaces") or strategy.get("namespaceTemplates") or [])


def _existing_strategy_names(strategies: list) -> set:
    return {(s.get("name") or "") for s in (strategies or []) if s.get("name")}


def _build_user_preference_strategy() -> dict:
    return {
        "customMemoryStrategy": {
            "name": USER_PREFERENCE_STRATEGY_NAME,
            "namespaces": [USER_PREFERENCE_NAMESPACE_TEMPLATE],
            "configuration": {
                "userPreferenceOverride": {
                    "extraction": {
                        "modelId": MEMORY_EXTRACTION_MODEL_ID,
                        "appendToPrompt": USER_PREFERENCE_PROMPT,
                    }
                }
            },
        }
    }


def _build_summary_strategy() -> dict:
    # Summary override supports consolidation only (no extraction step).
    return {
        "customMemoryStrategy": {
            "name": SUMMARY_STRATEGY_NAME,
            "namespaces": [SUMMARY_NAMESPACE_TEMPLATE],
            "configuration": {
                "summaryOverride": {
                    "consolidation": {
                        "modelId": MEMORY_EXTRACTION_MODEL_ID,
                        "appendToPrompt": SUMMARY_PROMPT,
                    }
                }
            },
        }
    }


def _build_semantic_strategy() -> dict:
    return {
        "customMemoryStrategy": {
            "name": SEMANTIC_STRATEGY_NAME,
            "namespaces": [SEMANTIC_NAMESPACE_TEMPLATE],
            "configuration": {
                "semanticOverride": {
                    "extraction": {
                        "modelId": MEMORY_EXTRACTION_MODEL_ID,
                        "appendToPrompt": SEMANTIC_PROMPT,
                    },
                    "consolidation": {
                        "modelId": MEMORY_EXTRACTION_MODEL_ID,
                        "appendToPrompt": SEMANTIC_CONSOLIDATION_PROMPT,
                    },
                }
            },
        }
    }


def shared_memory_strategies() -> list:
    """Strategy definitions shared by create_memory / installer / ensure."""
    return [
        _build_user_preference_strategy(),
        _build_summary_strategy(),
        _build_semantic_strategy(),
    ]


def add_strategy(memory_id: str, strategy: dict):
    name = (strategy.get("customMemoryStrategy") or {}).get("name")
    namespaces = (strategy.get("customMemoryStrategy") or {}).get("namespaces")
    memory_client.add_strategy(memory_id, strategy)
    logger.info(
        f"Added shared strategy {name!r} namespaces={namespaces!r} to memory_id={memory_id}"
    )
    time.sleep(5)


def create_strategy_if_not_exists(memory_id: str):
    """
    Ensure this memory_id has the shared UserPreference / Summary / Semantic strategies.

    Do NOT create a strategy per actor_id — that hits the 6-strategy quota.
    """
    try:
        strategies = load_memory_strategy(memory_id)
        for strategy in strategies or []:
            logger.info(f"strategy: {strategy}")
        existing = _existing_strategy_names(strategies)
        for strategy_def in shared_memory_strategies():
            name = strategy_def["customMemoryStrategy"]["name"]
            if name in existing:
                logger.info(f"Shared strategy already present: {name}")
                continue
            logger.info(f"{name} strategy not found, adding...")
            try:
                add_strategy(memory_id, strategy_def)
                existing.add(name)
                logger.info(f"{name} strategy was added...")
            except Exception as add_err:
                logger.error(f"Failed to add strategy {name!r}: {add_err}")
    except Exception as e:
        # Do not block CreateEvent short-term save if strategy UpdateMemory fails
        logger.error(f"Failed to ensure memory strategy (continuing without update): {e}")


def create_memory():
    """Create project Memory with shared UserPreference + Summary + Semantic strategies."""
    result = memory_client.create_memory_and_wait(
        name=projectName.replace("-", "_"),
        description=f"Memory for {projectName}",
        event_expiry_days=365,  # 7 - 365 days
        strategies=shared_memory_strategies(),
        memory_execution_role_arn=agentcore_memory_role,
    )
    logger.info(f"result of memory creation: {result}")
    memory_id = result.get("id")
    logger.info(f"created memory_id: {memory_id}")
    return memory_id

def save_conversation_to_memory(memory_id, actor_id, session_id, query, result):
    logger.info(f"###### save_conversation_to_memory ######")

    # Validate query and result are not empty
    if not query or not isinstance(query, str) or len(query.strip()) == 0:
        logger.warning(f"Query is empty or invalid, skipping memory save")
        return
    
    if not result or not isinstance(result, str) or len(result.strip()) == 0:
        logger.warning(f"Result is empty or invalid, skipping memory save")
        return

    # Truncate text to AWS Bedrock limit (9000 characters)
    max_length = 9000
    truncate_suffix = "... [truncated]"
    suffix_length = len(truncate_suffix)
    max_content_length = max_length - suffix_length  # Reserve space for suffix
    
    query_trimmed = query.strip()
    result_trimmed = result.strip()
    
    if len(query_trimmed) > max_length:
        logger.warning(f"Query text exceeds {max_length} characters, truncating")
        query_trimmed = query_trimmed[:max_content_length] + truncate_suffix
        # Ensure final length doesn't exceed max_length
        if len(query_trimmed) > max_length:
            query_trimmed = query_trimmed[:max_length]
    
    if len(result_trimmed) > max_length:
        logger.warning(f"Result text exceeds {max_length} characters, truncating")
        result_trimmed = result_trimmed[:max_content_length] + truncate_suffix
        # Ensure final length doesn't exceed max_length
        if len(result_trimmed) > max_length:
            result_trimmed = result_trimmed[:max_length]

    event_timestamp = datetime.now(timezone.utc)
    conversation = [
        (query_trimmed, "USER"),
        (result_trimmed, "ASSISTANT")
    ]

    try:
        memory_result = memory_client.create_event(
            memory_id=memory_id,
            actor_id=actor_id, 
            session_id=session_id, 
            event_timestamp=event_timestamp,
            messages=conversation
        )
        logger.info(f"result of save conversation to memory: {memory_result}")
    except Exception as e:
        logger.error(f"Error saving conversation to memory: {e}")
        raise

def get_memory_record(user_id: str):
    logger.info(f"###### get_memory_record ######")    

    memory_id, actor_id, session_id, namespace = load_memory_variables(user_id)
    logger.info(f"memory_id: {memory_id}, user_id: {user_id}, actor_id: {actor_id}, session_id: {session_id}, namespace: {namespace}")
    
    conversations = memory_client.list_events(
        memory_id=memory_id,
        actor_id=actor_id,
        session_id=session_id,
        max_results=5,
    )
    logger.info(f"conversations: {conversations}")

    return conversations

