import logging
import sys
import json
import traceback
import boto3
import os
from urllib import parse
from botocore.exceptions import ClientError
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("utils")

aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
aws_session_token = os.environ.get('AWS_SESSION_TOKEN')

workingDir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(workingDir, "config.json")
favorite_tools_path = os.path.join(workingDir, "favorite_tools.json")
# Local session root for per-user artifacts/skills (no S3 Files /mnt mount).
SESSION_STORAGE_DIR = os.environ.get(
    "SESSION_STORAGE_DIR",
    os.path.join(workingDir, ".session_storage"),
)
SKILLS_DIR = os.path.join(workingDir, "skills")


def sanitize_user_path_segment(user_id: str | None) -> str | None:
    """Return a safe single path segment for per-user workspace folders, or None."""
    if not user_id:
        return None
    raw = str(user_id).strip()
    # Never treat opaque signed session cookies as folder names.
    if raw.startswith("v1.") and raw.count(".") >= 2:
        logger.warning("Refusing signed session token as artifacts path segment")
        return None
    if len(raw) > 128:
        logger.warning("Refusing oversized user_id as artifacts path segment")
        return None
    # Collapse path separators so user_id cannot escape the intended prefix.
    segment = (
        raw
        .replace("/", "_")
        .replace("\\", "_")
        .replace("..", "_")
    )
    return segment or None


def get_user_artifacts_dir(user_id: str | None) -> str:
    """Absolute path to {SESSION_STORAGE_DIR}/{user_id}/artifacts (does not create)."""
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        segment = "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "artifacts")


def ensure_user_artifacts_dir(user_id: str | None) -> str:
    """Create {SESSION_STORAGE_DIR}/{user_id}/artifacts if needed and return it."""
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(
            "Invalid user_id for artifacts path; expected a plain user id, "
            "not a signed session cookie"
        )
    artifacts_dir = os.path.join(SESSION_STORAGE_DIR, segment, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    logger.info("user artifacts dir ready: %s", artifacts_dir)
    return artifacts_dir


def get_user_skills_dir(user_id: str | None) -> str:
    """Absolute path to {SESSION_STORAGE_DIR}/{user_id}/skills (does not create)."""
    segment = sanitize_user_path_segment(user_id) or "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "skills")


def ensure_user_skills_dir(user_id: str | None) -> str:
    """Create {SESSION_STORAGE_DIR}/{user_id}/skills if needed and return it."""
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(
            "Invalid user_id for skills path; expected a plain user id, "
            "not a signed session cookie"
        )
    skills_dir = os.path.join(SESSION_STORAGE_DIR, segment, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    logger.info("user skills dir ready: %s", skills_dir)
    return skills_dir


def get_user_graph_dir(user_id: str | None) -> str:
    """Absolute path to {SESSION_STORAGE_DIR}/{user_id}/graph (does not create)."""
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        segment = "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "graph")


def ensure_user_graph_dir(user_id: str | None) -> str:
    """Create session graph workspace: corpus/ + out/ (shared extract+publish).

    Returns the graph root: {SESSION_STORAGE_DIR}/{user_id}/graph
    """
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(
            "Invalid user_id for graph path; expected a plain user id, "
            "not a signed session cookie"
        )
    graph_dir = os.path.join(SESSION_STORAGE_DIR, segment, "graph")
    for name in ("corpus", "out"):
        os.makedirs(os.path.join(graph_dir, name), exist_ok=True)
    logger.info("user graph dir ready: %s", graph_dir)
    return graph_dir


def user_graph_html_path(user_id: str | None) -> str:
    """Published HTML: {SESSION_STORAGE_DIR}/{user_id}/graph/out/graph.html"""
    segment = sanitize_user_path_segment(user_id) or "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "graph", "out", "graph.html")


GRAPH_PATTERNS = ("pattern1", "pattern2", "pattern3")
DEFAULT_GRAPH_PATTERN = "pattern1"

_DEFAULT_USER_SETTINGS: dict[str, object] = {
    "knowledge_graph_enabled": True,
    "graph_pattern": DEFAULT_GRAPH_PATTERN,
}


def normalize_graph_pattern(value: object | None) -> str:
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



def get_user_db_path(user_id: str | None) -> str:
    """Durable per-user tasks/messages DB: {SESSION_STORAGE_DIR}/{user_id}/{user_id}.db."""
    segment = sanitize_user_path_segment(user_id) or "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, f"{segment}.db")


def get_user_settings_path(user_id: str | None) -> str:
    """Absolute path to {SESSION_STORAGE_DIR}/{user_id}/settings.json (does not create)."""
    segment = sanitize_user_path_segment(user_id) or "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "settings.json")


def _normalize_string_list(value: object) -> list[str]:
    """Return a cleaned list of non-empty strings (stable order, no duplicates)."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def load_user_settings(user_id: str | None) -> dict[str, object]:
    """Load per-user UI/feature settings. Missing file → defaults (KG on).

    ``skills`` / ``mcp_servers`` are omitted until the user has saved them so
    callers can fall back to favorite_tools.json.
    """
    settings = dict(_DEFAULT_USER_SETTINGS)
    path = get_user_settings_path(user_id)
    if not os.path.isfile(path):
        return settings
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            if "knowledge_graph_enabled" in raw:
                settings["knowledge_graph_enabled"] = bool(raw["knowledge_graph_enabled"])
            if "graph_pattern" in raw:
                settings["graph_pattern"] = normalize_graph_pattern(raw.get("graph_pattern"))
            if "skills" in raw:
                settings["skills"] = _normalize_string_list(raw.get("skills"))
            if "mcp_servers" in raw:
                settings["mcp_servers"] = _normalize_string_list(raw.get("mcp_servers"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load user settings %s: %s", path, e)
    return settings


def save_user_settings(user_id: str | None, **updates: object) -> dict[str, object]:
    """Merge updates into per-user settings.json and return the full settings."""
    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(
            "Invalid user_id for settings path; expected a plain user id, "
            "not a signed session cookie"
        )
    user_dir = os.path.join(SESSION_STORAGE_DIR, segment)
    os.makedirs(user_dir, exist_ok=True)
    settings = load_user_settings(user_id)
    for key, value in updates.items():
        if key == "knowledge_graph_enabled":
            settings[key] = bool(value)
        elif key == "graph_pattern":
            settings[key] = normalize_graph_pattern(value)
        elif key == "skills":
            settings[key] = _normalize_string_list(value)
        elif key == "mcp_servers":
            settings[key] = _normalize_string_list(value)
    path = get_user_settings_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    logger.info("user settings saved: %s -> %s", path, settings)
    return settings


def is_knowledge_graph_enabled(user_id: str | None) -> bool:
    """True when Knowledge Graph feature is on (default)."""
    return bool(load_user_settings(user_id).get("knowledge_graph_enabled", True))



def is_hybrid_graph_search_enabled() -> bool:
    """True when config.json hybrid_graph_search is enable (embedding vector search)."""
    cfg = load_config() or {}
    raw = str(cfg.get("hybrid_graph_search") or "").strip().lower()
    return raw in {"enable", "enabled", "on", "true", "1", "yes"}


def get_graph_pattern(user_id: str | None) -> str:
    """Selected Knowledge Graph HTML pattern (pattern1|pattern2|pattern3)."""
    return normalize_graph_pattern(
        load_user_settings(user_id).get("graph_pattern", DEFAULT_GRAPH_PATTERN)
    )


def get_user_skills_list_path(user_id: str | None) -> str:
    """Absolute path to {SESSION_STORAGE_DIR}/{user_id}/skills.list (does not create)."""
    segment = sanitize_user_path_segment(user_id) or "default"
    return os.path.join(SESSION_STORAGE_DIR, segment, "skills.list")


def _list_skill_dir_names(skills_dir: str) -> list[str]:
    """Return subdirectory names that contain SKILL.md."""
    if not os.path.isdir(skills_dir):
        return []
    names: list[str] = []
    try:
        entries = sorted(os.listdir(skills_dir))
    except OSError as e:
        logger.warning("Failed to list skills directory %s: %s", skills_dir, e)
        return []
    for entry in entries:
        if os.path.isfile(os.path.join(skills_dir, entry, "SKILL.md")):
            names.append(entry)
    return names


def _load_skills_list_file(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
    except FileNotFoundError:
        return []
    except OSError as e:
        logger.warning("Failed to read skills.list %s: %s", path, e)
        return []


def _seed_skill_names(user_id: str | None) -> list[str]:
    """Builtin application/skills.list + skill-creator dirs under the user skills path."""
    default_path = os.path.join(workingDir, "skills.list")
    builtin = _load_skills_list_file(default_path)
    user_skills = _list_skill_dir_names(get_user_skills_dir(user_id))
    merged: list[str] = []
    seen: set[str] = set()
    for name in builtin + user_skills:
        if name not in seen:
            merged.append(name)
            seen.add(name)
    return merged


def write_user_skills_list(user_id: str | None, names: list[str] | None = None) -> str:
    """Write {SESSION_STORAGE_DIR}/{user_id}/skills.list and return its path."""
    ensure_user_skills_dir(user_id)
    path = get_user_skills_list_path(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    merged = names if names is not None else _seed_skill_names(user_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(merged) + ("\n" if merged else ""))
    logger.info(
        "wrote user skills.list (%d skills) -> %s",
        len(merged),
        path,
    )
    return path


def update_user_skills_list(user_id: str | None) -> str:
    """Rewrite per-user skills.list from application/skills.list + user skills dir."""
    return write_user_skills_list(user_id)


def _builtin_skill_exists(name: str) -> bool:
    return os.path.isfile(os.path.join(workingDir, "skills", name, "SKILL.md"))


def _user_skill_exists(user_id: str | None, name: str) -> bool:
    return os.path.isfile(
        os.path.join(get_user_skills_dir(user_id), name, "SKILL.md")
    )


def ensure_user_skills_list(user_id: str | None) -> str:
    """Use {SESSION_STORAGE_DIR}/{user_id}/skills.list; create it if missing.

    When the file already exists, keep user ordering/custom entries, but:
    - append new builtin names from application/skills.list
    - append newly discovered skill-creator dirs under ``{user_id}/skills/``
    - drop entries whose SKILL.md no longer exists in builtin or user skills
    """
    ensure_user_skills_dir(user_id)
    path = get_user_skills_list_path(user_id)
    if not os.path.isfile(path):
        return write_user_skills_list(user_id)

    existing = _load_skills_list_file(path)
    kept = [
        name
        for name in existing
        if _builtin_skill_exists(name) or _user_skill_exists(user_id, name)
    ]
    seen = set(kept)
    default_path = os.path.join(workingDir, "skills.list")
    candidates = _load_skills_list_file(default_path) + _list_skill_dir_names(
        get_user_skills_dir(user_id)
    )
    appended = [name for name in candidates if name not in seen]
    updated = kept + appended
    if updated != existing:
        return write_user_skills_list(user_id, updated)
    logger.info(
        "using existing user skills.list (%d skills) -> %s",
        len(existing),
        path,
    )
    return path


def load_config():
    config = None

    try: 
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        config = {}

        projectName = "agent-skills"
        session = boto3.Session()
        region = session.region_name
        config['region'] = region
        config['projectName'] = projectName
        
        sts = boto3.client("sts")
        response = sts.get_caller_identity()
        accountId = response["Account"]
        config['accountId'] = accountId
        config['s3_bucket'] = f'storage-for-rag-project-{accountId}-{region}'
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)    
    return config


def load_favorite_tools() -> dict[str, list[str]]:
    """Load favorite tool defaults for initial selections."""
    fallback = {"MCP": [], "SKILL": []}
    try:
        with open(favorite_tools_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("favorite_tools.json not found: %s", favorite_tools_path)
        return fallback
    except Exception as e:
        logger.warning("Failed to load favorite_tools.json: %s", e)
        return fallback

    if not isinstance(data, dict):
        return fallback

    favorites: dict[str, list[str]] = {}
    for key in ("MCP", "SKILL"):
        values = data.get(key, [])
        if isinstance(values, list):
            favorites[key] = [v for v in values if isinstance(v, str) and v.strip()]
        else:
            favorites[key] = []
    return favorites


def save_favorite_tools(*, skills: list[str] | None = None, mcp_servers: list[str] | None = None) -> dict[str, list[str]]:
    """Persist favorite tool defaults in favorite_tools.json."""
    favorites = load_favorite_tools()
    if skills is not None:
        favorites["SKILL"] = [v for v in skills if isinstance(v, str) and v.strip()]
    if mcp_servers is not None:
        favorites["MCP"] = [v for v in mcp_servers if isinstance(v, str) and v.strip()]

    with open(favorite_tools_path, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)
    return favorites


def get_initial_tool_defaults() -> tuple[list[str], list[str]]:
    """Return initial skill/MCP defaults from favorite_tools.json."""
    favorite_tools = load_favorite_tools()
    default_skills = favorite_tools.get("SKILL") or []
    default_mcp_servers = favorite_tools.get("MCP") or []
    return default_skills, default_mcp_servers


def get_user_tool_defaults(user_id: str | None) -> tuple[list[str], list[str]]:
    """Per-user skill/MCP defaults from settings.json, else favorite_tools.json."""
    fav_skills, fav_mcp = get_initial_tool_defaults()
    settings = load_user_settings(user_id)
    skills = settings.get("skills")
    mcp_servers = settings.get("mcp_servers")
    return (
        list(skills) if isinstance(skills, list) else fav_skills,
        list(mcp_servers) if isinstance(mcp_servers, list) else fav_mcp,
    )


def save_user_tool_defaults(
    user_id: str | None,
    *,
    skills: list[str] | None = None,
    mcp_servers: list[str] | None = None,
) -> dict[str, object]:
    """Persist the user's last skill/MCP selection into settings.json."""
    updates: dict[str, object] = {}
    if skills is not None:
        updates["skills"] = skills
    if mcp_servers is not None:
        updates["mcp_servers"] = mcp_servers
    if not updates:
        return load_user_settings(user_id)
    return save_user_settings(user_id, **updates)

config = load_config()

accountId = config.get('accountId')
if not accountId:
    sts = boto3.client("sts")
    response = sts.get_caller_identity()
    accountId = response["Account"]
    config['accountId'] = accountId
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

bedrock_region = config.get('region', 'us-west-2')
logger.info(f"bedrock_region: {bedrock_region}")
projectName = config.get('projectName', 'mop')
logger.info(f"projectName: {projectName}")


def persist_config_updates(updates):
    """Merge values fetched from Secrets Manager into config and write config.json."""
    global config
    if not updates:
        return
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        s = value.strip() if isinstance(value, str) else str(value)
        if not s:
            continue
        if config.get(key) != s:
            config[key] = s
            changed = True
    if not changed:
        return
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(
            "Saved Secrets Manager values to config.json: %s",
            ", ".join(str(k) for k in updates if updates.get(k)),
        )
    except Exception as e:
        logger.warning("Failed to write config.json: %s", e)


def get_contents_type(file_name):
    lower = file_name.lower()
    if lower.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    elif lower.endswith(".gif"):
        content_type = "image/gif"
    elif lower.endswith(".pdf"):
        content_type = "application/pdf"
    elif lower.endswith(".txt"):
        content_type = "text/plain"
    elif lower.endswith(".csv"):
        content_type = "text/csv"
    elif lower.endswith((".ppt", ".pptx")):
        content_type = "application/vnd.ms-powerpoint"
    elif lower.endswith(".docx"):
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif lower.endswith(".doc"):
        content_type = "application/msword"
    elif lower.endswith((".xls", ".xlsx")):
        content_type = "application/vnd.ms-excel"
    elif lower.endswith(".py"):
        content_type = "text/x-python"
    elif lower.endswith(".js"):
        content_type = "application/javascript"
    elif lower.endswith(".md"):
        content_type = "text/markdown"
    elif lower.endswith((".html", ".htm")):
        content_type = "text/html; charset=utf-8"
    else:
        content_type = "no info"
    return content_type

def load_mcp_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_env_path = os.path.join(script_dir, "mcp.env")
    
    with open(mcp_env_path, "r", encoding="utf-8") as f:
        mcp_env = json.load(f)
    return mcp_env

def save_mcp_env(mcp_env):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_env_path = os.path.join(script_dir, "mcp.env")
    
    with open(mcp_env_path, "w", encoding="utf-8") as f:
        json.dump(mcp_env, f)

# api key to get information in agent
if aws_access_key and aws_secret_key:
    secretsmanager = boto3.client(
        service_name='secretsmanager',
        region_name=bedrock_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        aws_session_token=aws_session_token,
    )
else:
    secretsmanager = boto3.client(
        service_name='secretsmanager',
        region_name=bedrock_region
    )

# Tavily Search API key: prefer config.json, else Secrets Manager
tavily_api_wrapper = ""
tavily_key = (config.get("tavily_api_key") or "").strip()
if tavily_key:
    tavily_api_wrapper = TavilySearchAPIWrapper(tavily_api_key=tavily_key)
    os.environ["TAVILY_API_KEY"] = tavily_key
else:
    try:
        get_tavily_api_secret = secretsmanager.get_secret_value(
            SecretId="tavilyapikey"
        )
        secret = json.loads(get_tavily_api_secret["SecretString"])

        if "tavily_api_key" in secret:
            tavily_key = (secret["tavily_api_key"] or "").strip()

        if tavily_key:
            tavily_api_wrapper = TavilySearchAPIWrapper(tavily_api_key=tavily_key)
            os.environ["TAVILY_API_KEY"] = tavily_key
            persist_config_updates({"tavily_api_key": tavily_key})
        else:
            logger.info("tavily_key is required.")
    except Exception as e:
        logger.info(f"Tavily credential is required: {e}")
        pass

# Notion API key: prefer config.json, else Secrets Manager
notion_api_key = (config.get("notion_api_key") or "").strip()
if notion_api_key:
    os.environ["NOTION_API_KEY"] = notion_api_key
else:
    try:
        get_notion_api_secret = secretsmanager.get_secret_value(
            SecretId="notionapikey"
        )
        secret = json.loads(get_notion_api_secret["SecretString"])

        if "notion_api_key" in secret:
            notion_api_key = (secret["notion_api_key"] or "").strip()

        if notion_api_key:
            os.environ["NOTION_API_KEY"] = notion_api_key
            persist_config_updates({"notion_api_key": notion_api_key})
        else:
            logger.info("notion_api_key is required.")
    except Exception as e:
        logger.info(f"Notion credential is required: {e}")
        pass

# Telegram API key: prefer config.json, else Secrets Manager
telegram_api_key = (config.get("telegram_api_key") or "").strip()
if telegram_api_key:
    os.environ["TELEGRAM_API_KEY"] = telegram_api_key
else:
    try:
        get_telegram_api_secret = secretsmanager.get_secret_value(
            SecretId="telegramapikey"
        )
        secret = json.loads(get_telegram_api_secret["SecretString"])

        if "telegram_api_key" in secret:
            telegram_api_key = (secret["telegram_api_key"] or "").strip()

        if telegram_api_key:
            os.environ["TELEGRAM_API_KEY"] = telegram_api_key
            persist_config_updates({"telegram_api_key": telegram_api_key})
        else:
            logger.info("telegram_api_key is required.")
    except Exception as e:
        logger.info(f"Telegram credential is required: {e}")
        pass

# Discord bot token: prefer config.json, else Secrets Manager
discord_bot_token = (config.get("discord_bot_token") or "").strip()
if discord_bot_token:
    os.environ["DISCORD_BOT_TOKEN"] = discord_bot_token
else:
    try:
        get_discord_secret = secretsmanager.get_secret_value(
            SecretId="discordapikey"
        )
        secret = json.loads(get_discord_secret["SecretString"])

        if "discord_bot_token" in secret:
            discord_bot_token = (secret["discord_bot_token"] or "").strip()

        if discord_bot_token:
            os.environ["DISCORD_BOT_TOKEN"] = discord_bot_token
            persist_config_updates({"discord_bot_token": discord_bot_token})
        else:
            logger.info("discord_bot_token is required.")
    except Exception as e:
        logger.info(f"Discord credential is required: {e}")
        pass

# Slack: prefer config.json; any missing fields are filled from Secrets Manager
slack_bot_token = (config.get("slack_bot_token") or "").strip()
slack_team_id = (config.get("slack_team_id") or "").strip()
slack_token_from_config = bool(slack_bot_token)
slack_team_from_config = bool(slack_team_id)
if slack_bot_token:
    os.environ["SLACK_BOT_TOKEN"] = slack_bot_token
if slack_team_id:
    os.environ["SLACK_TEAM_ID"] = slack_team_id

if not slack_bot_token or not slack_team_id:
    try:
        get_slack_secret = secretsmanager.get_secret_value(
            SecretId="slackapikey"
        )
        secret = json.loads(get_slack_secret["SecretString"])
        if not slack_bot_token:
            slack_bot_token = (secret.get("slack_bot_token") or "").strip()
            if slack_bot_token:
                os.environ["SLACK_BOT_TOKEN"] = slack_bot_token
        if not slack_team_id:
            slack_team_id = (secret.get("slack_team_id") or "").strip()
            if slack_team_id:
                os.environ["SLACK_TEAM_ID"] = slack_team_id
        slack_persist = {}
        if not slack_token_from_config and slack_bot_token:
            slack_persist["slack_bot_token"] = slack_bot_token
        if not slack_team_from_config and slack_team_id:
            slack_persist["slack_team_id"] = slack_team_id
        persist_config_updates(slack_persist)
    except Exception as e:
        logger.info(f"Slack credential is required: {e}")
        pass

def sanitize_data_source_name(name):
    """
    Sanitize a name to comply with AWS Bedrock data source name pattern:
    ([0-9a-zA-Z][_-]?){1,100}
    - Pattern means: alphanumeric, optionally followed by underscore or hyphen, repeated 1-100 times
    - Cannot have consecutive underscores or hyphens
    - Must start with alphanumeric
    """
    import re
    # Remove any characters that are not alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^0-9a-zA-Z_-]', '', name)
    
    # Replace consecutive underscores/hyphens with single hyphen
    # This ensures the pattern [0-9a-zA-Z][_-]? is followed correctly
    sanitized = re.sub(r'[_-]{2,}', '-', sanitized)
    
    # Ensure it starts with alphanumeric character
    if sanitized and not sanitized[0].isalnum():
        sanitized = 'ds' + sanitized
    
    # Remove trailing hyphens/underscores (they must be followed by alphanumeric per pattern)
    sanitized = sanitized.rstrip('_-')
    
    # Ensure it's not empty and limit to 100 characters
    if not sanitized:
        sanitized = 'datasource'
    
    # Final validation: ensure it matches the pattern exactly
    pattern = re.compile(r'^([0-9a-zA-Z][_-]?){1,100}$')
    if not pattern.match(sanitized):
        # If still doesn't match, create a safe default name
        # Use project name or create a simple alphanumeric name
        safe_name = re.sub(r'[^0-9a-zA-Z]', '', name.lower())
        if not safe_name:
            safe_name = 'datasource'
        sanitized = safe_name[:100]
    
    return sanitized[:100]

knowledge_base_id = config.get('knowledge_base_id')
data_source_id = config.get('data_source_id')
region = config.get('region', 'us-west-2')
s3_bucket = config.get('s3_bucket', f'storage-for-rag-project-{accountId}-{region}')
sharing_url = config.get('sharing_url', '')

def update_sharing_url():
    """Look up CloudFront distribution domain for this project and save as sharing_url."""
    try:
        cf_client = boto3.client('cloudfront', region_name=region)
        paginator = cf_client.get_paginator('list_distributions')
        target_origin_id = f"s3-{projectName}"

        for page in paginator.paginate():
            dist_list = page.get('DistributionList', {})
            for dist in dist_list.get('Items', []):
                origins = dist.get('Origins', {}).get('Items', [])
                for origin in origins:
                    if origin['Id'] == target_origin_id:
                        domain = dist['DomainName']
                        url = f"https://{domain}"
                        logger.info(f"sharing_url found: {url}")
                        config['sharing_url'] = url
                        with open(config_path, "w", encoding="utf-8") as f:
                            json.dump(config, f, indent=2)
                        return url
        logger.warning(f"CloudFront distribution with origin '{target_origin_id}' not found")
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"Failed to look up sharing_url: {err_msg}")
    return ''

if not sharing_url:
    sharing_url = update_sharing_url()

def update_rag_info():
    knowledge_base_id = None
    data_source_id = None
    try: 
        client = boto3.client(
            service_name='bedrock-agent',
            region_name=region
        )

        response = client.list_knowledge_bases(
            maxResults=50
        )
        logger.info(f"(list_knowledge_bases) response: {response}")
        
        knowledge_base_name = config.get("knowledge_base_name") or config.get(
            "projectName", projectName
        )
        if "knowledgeBaseSummaries" in response:
            summaries = response["knowledgeBaseSummaries"]
            for summary in summaries:
                if summary["name"] == knowledge_base_name:
                    knowledge_base_id = summary["knowledgeBaseId"]
                    logger.info(f"knowledge_base_id: {knowledge_base_id}")

        if not knowledge_base_id:
            logger.warning(f"Knowledge Base not found for project: {knowledge_base_name}")
            return knowledge_base_id, data_source_id

        if not s3_bucket:
            logger.warning(f"s3_bucket is not configured, skipping data source lookup")
            return knowledge_base_id, data_source_id

        response = client.list_data_sources(
            knowledgeBaseId=knowledge_base_id,
            maxResults=10
        )        
        logger.info(f"(list_data_sources) response: {response}")
        
        data_source_name = sanitize_data_source_name(s3_bucket)
        summaries = response.get("dataSourceSummaries") or []
        for data_source in summaries:
            logger.info(f"data_source: {data_source}")
            if data_source.get("name") == data_source_name:
                data_source_id = data_source["dataSourceId"]
                logger.info(f"data_source_id: {data_source_id}")
                break
        # Fall back to the first AVAILABLE (or first) data source when names diverge.
        if not data_source_id and summaries:
            preferred = next(
                (
                    ds
                    for ds in summaries
                    if (ds.get("status") or "").upper() == "AVAILABLE"
                ),
                summaries[0],
            )
            data_source_id = preferred.get("dataSourceId")
            logger.warning(
                "data source name mismatch (wanted=%s); using %s (%s)",
                data_source_name,
                preferred.get("name"),
                data_source_id,
            )

        if knowledge_base_id and data_source_id:
            config["knowledge_base_id"] = knowledge_base_id
            config["data_source_id"] = data_source_id
            config["s3_bucket"] = s3_bucket
            config["region"] = region
            config["projectName"] = projectName
            config["accountId"] = accountId
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                f.write("\n")

    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")

    return knowledge_base_id, data_source_id

if not knowledge_base_id or not data_source_id:
    knowledge_base_id, data_source_id = update_rag_info()

ACTIVE_INGESTION_STATUSES = ("STARTING", "IN_PROGRESS")


def refresh_rag_ids() -> bool:
    """Refresh in-memory KB/data-source IDs from AWS and persist to config.json."""
    global knowledge_base_id, data_source_id
    kb_id, ds_id = update_rag_info()
    if kb_id and ds_id:
        knowledge_base_id = kb_id
        data_source_id = ds_id
        logger.info(
            "Refreshed RAG ids: knowledge_base_id=%s data_source_id=%s",
            knowledge_base_id,
            data_source_id,
        )
        return True
    logger.error(
        "Failed to refresh RAG ids (knowledge_base_id=%s data_source_id=%s)",
        kb_id,
        ds_id,
    )
    return False


def _is_resource_not_found(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException"
    return "ResourceNotFoundException" in type(exc).__name__


def get_active_ingestion_job(*, _retried: bool = False) -> dict | None:
    """Return an in-flight ingestion job if Knowledge Base sync is already running."""
    if not knowledge_base_id or not data_source_id:
        logger.error("knowledge_base_id or data_source_id is not configured")
        if not _retried and refresh_rag_ids():
            return get_active_ingestion_job(_retried=True)
        return None

    try:
        bedrock_client = boto3.client(
            service_name="bedrock-agent",
            region_name=region,
        )
        for status in ACTIVE_INGESTION_STATUSES:
            response = bedrock_client.list_ingestion_jobs(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=data_source_id,
                filters=[
                    {
                        "attribute": "STATUS",
                        "operator": "EQ",
                        "values": [status],
                    }
                ],
                maxResults=1,
                sortBy={
                    "attribute": "STARTED_AT",
                    "order": "DESCENDING",
                },
            )
            summaries = response.get("ingestionJobSummaries") or []
            if not summaries:
                continue
            job = summaries[0]
            logger.info("Active ingestion job found: %s", job)
            return {
                "ingestion_job_id": job.get("ingestionJobId"),
                "status": job.get("status"),
                "started_at": str(job["startedAt"]) if job.get("startedAt") else None,
            }
        return None
    except Exception as e:
        if not _retried and _is_resource_not_found(e):
            logger.warning(
                "Stale knowledge_base_id/data_source_id (%s / %s); refreshing",
                knowledge_base_id,
                data_source_id,
            )
            if refresh_rag_ids():
                return get_active_ingestion_job(_retried=True)
        logger.error("Error listing ingestion jobs: %s", traceback.format_exc())
        raise


def sync_data_source(*, _retried: bool = False):
    """Start a Knowledge Base ingestion job for the configured data source."""
    if not knowledge_base_id or not data_source_id:
        logger.error("knowledge_base_id or data_source_id is not configured")
        if not _retried and refresh_rag_ids():
            return sync_data_source(_retried=True)
        return None

    try:
        bedrock_client = boto3.client(
            service_name="bedrock-agent",
            region_name=region,
        )
        response = bedrock_client.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )
        logger.info("(start_ingestion_job) response: %s", response)
        job = response.get("ingestionJob", {})
        return {
            "ingestion_job_id": job.get("ingestionJobId"),
            "status": job.get("status"),
        }
    except Exception as e:
        if not _retried and _is_resource_not_found(e):
            logger.warning(
                "Stale knowledge_base_id/data_source_id (%s / %s); refreshing",
                knowledge_base_id,
                data_source_id,
            )
            if refresh_rag_ids():
                return sync_data_source(_retried=True)
        logger.error("Error syncing data source: %s", traceback.format_exc())
        return None


def _sanitize_s3_user_segment(user_id: str | None) -> str | None:
    """Return a safe single path segment for per-user S3 folders, or None."""
    return sanitize_user_path_segment(user_id)


def docs_s3_prefix(project: str | None = None) -> str:
    """Return S3 key prefix for RAG docs: ``docs/{projectName}``."""
    name = (project or projectName or "").strip().strip("/")
    if not name:
        name = "default"
    return f"docs/{name}"


def upload_to_s3(
    file_bytes: bytes,
    file_name: str,
    user_id: str | None = None,
) -> dict | None:
    """Upload a file to S3 under docs/{projectName}/ (or images/) and return metadata.

    When ``user_id`` is provided, the object key becomes
    ``docs/{projectName}/{user_id}/{file_name}`` so each user has a separate folder.
    """
    if not s3_bucket:
        logger.error("s3_bucket is not configured")
        return None

    try:
        s3_client = boto3.client(service_name="s3", region_name=bedrock_region)
        content_type = get_contents_type(file_name)
        logger.info("content_type: %s", content_type)

        prefix = (
            "images"
            if isinstance(content_type, str) and content_type.startswith("image/")
            else docs_s3_prefix()
        )
        user_segment = _sanitize_s3_user_segment(user_id)
        if user_segment:
            s3_key = f"{prefix}/{user_segment}/{file_name}"
            relative_url_path = f"{prefix}/{parse.quote(user_segment)}/{parse.quote(file_name)}"
        else:
            s3_key = f"{prefix}/{file_name}"
            relative_url_path = f"{prefix}/{parse.quote(file_name)}"
        user_meta = {"content_type": content_type}

        put_params = {
            "Bucket": s3_bucket,
            "Key": s3_key,
            "Metadata": user_meta,
            "Body": file_bytes,
        }
        if content_type and content_type != "no info":
            put_params["ContentType"] = content_type
        if content_type == "application/pdf":
            put_params["ContentDisposition"] = "inline"

        response = s3_client.put_object(**put_params)
        logger.info("upload response: %s", response)

        url = None
        if sharing_url:
            url = f"{sharing_url.rstrip('/')}/{relative_url_path}"

        return {
            "file_name": file_name,
            "s3_key": s3_key,
            "content_type": content_type,
            "url": url,
        }
    except Exception:
        logger.error("Error uploading to S3: %s", traceback.format_exc())
        return None


async def generate_pdf_report(report_content: str, filename: str) -> str:
    """Generate a simple PDF (or text fallback) under artifacts/."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        os.makedirs("artifacts", exist_ok=True)
        filepath = f"artifacts/{filename}.pdf"
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        font_path = os.path.join(os.path.dirname(os.path.dirname(workingDir)), "assets", "NanumGothic-Regular.ttf")
        if not os.path.isfile(font_path):
            font_path = os.path.join(workingDir, "..", "assets", "NanumGothic-Regular.ttf")
        font_path = os.path.abspath(font_path)
        if os.path.isfile(font_path):
            pdfmetrics.registerFont(TTFont("NanumGothic", font_path))
            font_name = "NanumGothic"
        else:
            font_name = "Helvetica"
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Normal_KO", fontName=font_name, fontSize=10, spaceAfter=12))
        styles.add(ParagraphStyle(name="Heading1_KO", fontName=font_name, fontSize=16, spaceAfter=20, textColor=colors.HexColor("#0000FF")))
        styles.add(ParagraphStyle(name="Heading2_KO", fontName=font_name, fontSize=14, spaceAfter=16, textColor=colors.HexColor("#0000FF")))
        styles.add(ParagraphStyle(name="Heading3_KO", fontName=font_name, fontSize=12, spaceAfter=14, textColor=colors.HexColor("#0000FF")))
        elements = []
        for line in report_content.split("\n"):
            if line.startswith("# "):
                elements.append(Paragraph(line[2:], styles["Heading1_KO"]))
            elif line.startswith("## "):
                elements.append(Paragraph(line[3:], styles["Heading2_KO"]))
            elif line.startswith("### "):
                elements.append(Paragraph(line[4:], styles["Heading3_KO"]))
            elif line.strip():
                elements.append(Paragraph(line, styles["Normal_KO"]))
        doc.build(elements)
        return f"PDF report generated successfully: {filepath}"
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        try:
            os.makedirs("artifacts", exist_ok=True)
            text_filepath = f"artifacts/{filename}.txt"
            with open(text_filepath, "w", encoding="utf-8") as f:
                f.write(report_content)
            return f"PDF generation failed. Saved as text file instead: {text_filepath}"
        except Exception as text_error:
            return f"Error generating report: {str(e)}. Text fallback also failed: {str(text_error)}"


def _add_runs_with_markdown(paragraph, text: str) -> None:
    """Add text runs with basic **bold** / *italic* / `code` markdown."""
    import re

    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn

    pattern = re.compile(
        r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|[^*`]+)",
    )
    for token in pattern.findall(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        else:
            paragraph.add_run(token)


def _generate_docx_with_python_docx(report_content: str, filepath: str) -> str:
    """Fallback markdown→docx converter using python-docx (docx skill compatible)."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    style = document.styles["Normal"]
    style.font.name = "Malgun Gothic"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    style.font.size = Pt(11)

    lines = report_content.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            i += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                cells = [c.strip() for c in row.strip("|").split("|")]
                if all(set(c) <= set("-: ") and c for c in cells):
                    i += 1
                    continue
                table_rows.append(cells)
                i += 1
            if table_rows:
                cols = max(len(r) for r in table_rows)
                table = document.add_table(rows=len(table_rows), cols=cols)
                table.style = "Table Grid"
                for r_idx, row_cells in enumerate(table_rows):
                    for c_idx in range(cols):
                        cell = table.cell(r_idx, c_idx)
                        cell.text = ""
                        para = cell.paragraphs[0]
                        value = row_cells[c_idx] if c_idx < len(row_cells) else ""
                        _add_runs_with_markdown(para, value)
                        if r_idx == 0:
                            for run in para.runs:
                                run.bold = True
            continue

        if stripped.startswith("> "):
            para = document.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.5)
            _add_runs_with_markdown(para, stripped[2:])
            for run in para.runs:
                run.italic = True
                run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
            i += 1
            continue

        if stripped.startswith("# "):
            para = document.add_heading(stripped[2:].strip(), level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            i += 1
            continue
        if stripped.startswith("## "):
            document.add_heading(stripped[3:].strip(), level=2)
            i += 1
            continue
        if stripped.startswith("### "):
            document.add_heading(stripped[4:].strip(), level=3)
            i += 1
            continue
        if stripped.startswith("#### "):
            document.add_heading(stripped[5:].strip(), level=4)
            i += 1
            continue

        if stripped.startswith(("- ", "* ")):
            para = document.add_paragraph(style="List Bullet")
            _add_runs_with_markdown(para, stripped[2:])
            i += 1
            continue

        if len(stripped) > 2 and stripped[0].isdigit() and ". " in stripped[:4]:
            text = stripped.split(". ", 1)[1] if ". " in stripped else stripped
            para = document.add_paragraph(style="List Number")
            _add_runs_with_markdown(para, text)
            i += 1
            continue

        para = document.add_paragraph()
        _add_runs_with_markdown(para, stripped)
        i += 1

    document.save(filepath)
    return f"DOCX report generated successfully: {filepath}"


async def generate_docx_report(report_content: str, filename: str) -> str:
    """Generate a Word (.docx) report from markdown (docx skill / pandoc path).

    Prefer pandoc for high-quality markdown tables and headings; fall back to
    python-docx when pandoc is unavailable.
    """
    import shutil
    import subprocess
    import tempfile

    os.makedirs("artifacts", exist_ok=True)
    docx_path = os.path.abspath(f"artifacts/{filename}.docx")
    content = (report_content or "").strip()
    if not content:
        return "Error generating DOCX: empty report content"

    pandoc = shutil.which("pandoc")
    if pandoc:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                md_path = os.path.join(tmp, f"{filename}.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(content)
                result = subprocess.run(
                    [
                        pandoc,
                        md_path,
                        "-f",
                        "markdown",
                        "-t",
                        "docx",
                        "-o",
                        docx_path,
                        "--standalone",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                if result.returncode == 0 and os.path.isfile(docx_path):
                    logger.info("DOCX generated via pandoc: %s", docx_path)
                    return f"DOCX report generated successfully: {docx_path}"
                logger.warning(
                    "pandoc docx failed (code=%s): %s",
                    result.returncode,
                    (result.stderr or result.stdout or "")[:500],
                )
        except Exception as e:
            logger.warning("pandoc docx exception: %s", e)

    try:
        return _generate_docx_with_python_docx(content, docx_path)
    except Exception as e:
        logger.error("Error generating DOCX: %s", e)
        try:
            text_filepath = f"artifacts/{filename}.txt"
            with open(text_filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return (
                f"DOCX generation failed. Saved as text file instead: {text_filepath}"
            )
        except Exception as text_error:
            return (
                f"Error generating report: {str(e)}. "
                f"Text fallback also failed: {str(text_error)}"
            )
