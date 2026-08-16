"""Paths and LiteLLM gateway settings for standalone graph pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
AGENT_SKILLS = HERE.parent

DEFAULT_DB = AGENT_SKILLS / "application" / "data" / "tasks.db"
DEFAULT_CORPUS = HERE / "corpus"
DEFAULT_GRAPHIFY_OUT = HERE / "graphify-out"
DEFAULT_OUT = HERE / "out"
DEFAULT_APP_CONFIG = AGENT_SKILLS / "application" / "config.json"
DEFAULT_LLM_MODEL = "claude-haiku-4-5"


def load_env() -> None:
    load_dotenv(HERE / ".env")


def _resolve(path: Path | str, *, base: Path = HERE) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def tasks_db_path() -> Path:
    load_env()
    return _resolve(os.getenv("TASKS_DB_PATH", str(DEFAULT_DB)))




def resolve_tasks_db_for_user(user_id: str) -> Path:
    """Prefer per-user working/durable DB; fall back to shared legacy tasks.db."""
    load_env()
    if os.getenv("TASKS_DB_PATH"):
        return tasks_db_path()
    segment = _user_path_segment(user_id)
    working = AGENT_SKILLS / "application" / "data" / "users" / f"{segment}.db"
    if working.is_file() and working.stat().st_size > 0:
        return working.resolve()
    durable = session_storage_dir() / segment / f"{segment}.db"
    if durable.is_file() and durable.stat().st_size > 0:
        return durable.resolve()
    return tasks_db_path()


def corpus_dir() -> Path:
    load_env()
    return _resolve(os.getenv("CORPUS_DIR", str(DEFAULT_CORPUS)))


def graphify_out_dir() -> Path:
    load_env()
    return _resolve(os.getenv("GRAPHIFY_OUT_DIR", str(DEFAULT_GRAPHIFY_OUT)))


def out_dir() -> Path:
    load_env()
    return _resolve(os.getenv("OUT_DIR", str(DEFAULT_OUT)))


def session_storage_dir() -> Path:
    load_env()
    default = AGENT_SKILLS / "application" / ".session_storage"
    return Path(os.getenv("SESSION_STORAGE_DIR", str(default))).expanduser().resolve()


def _user_path_segment(user_id: str) -> str:
    """Mirror application.utils.sanitize_user_path_segment for session folders."""
    raw = (user_id or "").strip()
    if not raw or (raw.startswith("v1.") and raw.count(".") >= 2) or len(raw) > 128:
        return "default"
    segment = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return segment or "default"


def user_graph_workspace(user_id: str) -> dict[str, Path]:
    """Per-user graph dirs under SESSION_STORAGE_DIR/{user}/graph/.

    Extraction artifacts and published HTML share the same ``out/`` folder.
    """
    root = session_storage_dir() / _user_path_segment(user_id) / "graph"
    out = root / "out"
    return {
        "root": root,
        "corpus": root / "corpus",
        "out": out,
        # Alias: graphify pipeline writes into the same out/ directory.
        "graphify_out": out,
    }


def configure_user_session_dirs(user_id: str) -> dict[str, Path]:
    """Point CORPUS_DIR / GRAPHIFY_OUT_DIR / OUT_DIR at the user's session storage.

    GRAPHIFY_OUT_DIR and OUT_DIR both resolve to ``{user}/graph/out``.
    """
    paths = user_graph_workspace(user_id)
    paths["corpus"].mkdir(parents=True, exist_ok=True)
    paths["out"].mkdir(parents=True, exist_ok=True)
    os.environ["CORPUS_DIR"] = str(paths["corpus"])
    os.environ["GRAPHIFY_OUT_DIR"] = str(paths["out"])
    os.environ["OUT_DIR"] = str(paths["out"])
    return paths


def load_app_config() -> dict[str, Any]:
    """Load agent-skills application/config.json only (no other repos)."""
    path = Path(os.getenv("APP_CONFIG_PATH", str(DEFAULT_APP_CONFIG))).expanduser()
    if not path.is_absolute():
        path = (AGENT_SKILLS / path).resolve()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def llm_gateway_settings() -> dict[str, str] | None:
    """LiteLLM from application/config.json, then env. None if unavailable."""
    load_env()
    cfg = load_app_config()

    cfg_url = (cfg.get("llm_gateway_url") or "").strip().rstrip("/")
    cfg_key = (cfg.get("llm_gateway_key") or "").strip()

    env_url = (os.getenv("LLM_GATEWAY_URL") or "").strip().rstrip("/")
    env_key = (os.getenv("LLM_GATEWAY_KEY") or "").strip()

    if cfg_url and cfg_key:
        url, key, source = cfg_url, cfg_key, "application/config.json"
    elif env_url and env_key:
        url, key, source = env_url, env_key, "env"
    else:
        return None

    model = (os.getenv("GRAPHIFY_LLM_MODEL") or DEFAULT_LLM_MODEL).strip()
    return {
        "url": url,
        "key": key,
        "base_url": f"{url}/v1",
        "model": model,
        "source": source,
    }



def is_hybrid_graph_search_enabled() -> bool:
    """True when config.json hybrid_graph_search is enable (embedding vector search)."""
    load_env()
    raw = str(load_app_config().get("hybrid_graph_search") or "").strip().lower()
    return raw in {"enable", "enabled", "on", "true", "1", "yes"}


def graphify_llm_model() -> str:
    """GRAPHIFY_LLM_MODEL from .env (gateway id or Bedrock-friendly alias)."""
    load_env()
    return (os.getenv("GRAPHIFY_LLM_MODEL") or DEFAULT_LLM_MODEL).strip()


def bedrock_settings() -> dict[str, str]:
    """Bedrock runtime settings when LiteLLM gateway is not configured.

    Uses application/config.json ``region`` and AWS default credential chain
    (same pattern as agentic-work graph / langgraph).
    """
    load_env()
    cfg = load_app_config()
    region = (
        (os.getenv("GRAPHIFY_BEDROCK_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or (os.getenv("AWS_DEFAULT_REGION") or "").strip()
        or (cfg.get("region") or "").strip()
        or "us-west-2"
    )
    model = (
        (os.getenv("GRAPHIFY_BEDROCK_MODEL") or "").strip()
        or graphify_llm_model()
    )
    return {
        "region": region,
        "model": model,
        "source": "bedrock",
    }
