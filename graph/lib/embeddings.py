"""Node-label embeddings for hybrid document search.

Uses LiteLLM gateway ``/v1/embeddings`` when ``llm_gateway_url`` /
``llm_gateway_key`` are set; otherwise falls back to Bedrock
``amazon.titan-embed-text-v2:0`` (same credential chain as graph LLM).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from lib.config import bedrock_settings, llm_gateway_settings

logger = logging.getLogger("graph.embeddings")

INDEX_VERSION = 1
# LiteLLM gateway id → Bedrock amazon.titan-embed-text-v2:0
DEFAULT_EMBEDDING_MODEL = "titan-embed-v2"
BEDROCK_TITAN_V2_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_EMBEDDING_DIM = 1024
BATCH_SIZE = 64
DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.35
EMBEDDINGS_FILENAME = "node_embeddings.json"

_BEDROCK_MODEL_IDS: dict[str, str] = {
    "titan-embed-v2": BEDROCK_TITAN_V2_MODEL_ID,
    "titan-embed-text-v2": BEDROCK_TITAN_V2_MODEL_ID,
    "amazon.titan-embed-text-v2:0": BEDROCK_TITAN_V2_MODEL_ID,
}


def embedding_model() -> str:
    return (
        os.getenv("GRAPHIFY_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    ).strip()


def embedding_dim() -> int:
    raw = (os.getenv("GRAPHIFY_EMBEDDING_DIM") or str(DEFAULT_EMBEDDING_DIM)).strip()
    try:
        return max(8, int(raw))
    except ValueError:
        return DEFAULT_EMBEDDING_DIM


def resolve_bedrock_embedding_model_id(model: str | None = None) -> str:
    raw = (model or embedding_model()).strip()
    if raw in _BEDROCK_MODEL_IDS:
        return _BEDROCK_MODEL_IDS[raw]
    lower = raw.lower()
    for key, value in _BEDROCK_MODEL_IDS.items():
        if key.lower() == lower:
            return value
    if raw.startswith("amazon.titan-embed"):
        return raw
    # Default to Titan V2 for unknown aliases when on Bedrock path.
    return BEDROCK_TITAN_V2_MODEL_ID


def embeddings_path_for(graph_json: Path) -> Path:
    return Path(graph_json).resolve().parent / EMBEDDINGS_FILENAME


def _node_text(label: str, source_location: Any = None) -> str:
    label = (label or "").strip()
    loc = ""
    if source_location is not None:
        loc = str(source_location).strip()
    if label and loc:
        return f"{label} ({loc})"
    return label or loc


def _text_hash(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()[:32]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _embed_texts_gateway(
    texts: list[str],
    *,
    model: str,
    gw: dict[str, str],
) -> list[list[float]]:
    client = OpenAI(base_url=gw["base_url"], api_key=gw["key"])
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        cleaned = [t if t.strip() else " " for t in batch]
        resp = client.embeddings.create(model=model, input=cleaned)
        data = sorted(resp.data, key=lambda d: getattr(d, "index", 0))
        if len(data) != len(batch):
            raise RuntimeError(
                f"embedding count mismatch: sent {len(batch)}, got {len(data)}"
            )
        out.extend([list(item.embedding) for item in data])
    return out


def _embed_texts_bedrock(
    texts: list[str],
    *,
    model: str | None = None,
) -> list[list[float]]:
    """Embed via Bedrock InvokeModel (Titan Text Embeddings V2)."""
    import boto3

    bs = bedrock_settings()
    model_id = resolve_bedrock_embedding_model_id(model)
    dim = embedding_dim()
    client = boto3.client("bedrock-runtime", region_name=bs["region"])
    out: list[list[float]] = []
    for text in texts:
        cleaned = text if text.strip() else " "
        # Titan V2 truncates long inputs; keep a safe char budget.
        if len(cleaned) > 20000:
            cleaned = cleaned[:20000]
        body = {
            "inputText": cleaned,
            "dimensions": dim,
            "normalize": True,
        }
        resp = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(resp["body"].read())
        emb = payload.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError(f"Bedrock embedding empty for model {model_id}")
        out.append([float(x) for x in emb])
    return out


def embed_texts(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Embed texts via LiteLLM gateway, or Bedrock Titan when gateway is unset."""
    if not texts:
        return []
    model_id = (model or embedding_model()).strip()
    gw = llm_gateway_settings()
    if gw is not None:
        return _embed_texts_gateway(texts, model=model_id, gw=gw)
    logger.info(
        "LiteLLM gateway not configured; using Bedrock %s (region=%s)",
        resolve_bedrock_embedding_model_id(model_id),
        bedrock_settings()["region"],
    )
    return _embed_texts_bedrock(texts, model=model_id)


def load_node_embeddings(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load embeddings %s: %s", path, exc)
        return None
    if not isinstance(data, dict) or "nodes" not in data:
        return None
    return data


def is_stale(graph_json: Path, emb_path: Path | None = None) -> bool:
    """True if embeddings are missing, wrong model, or older than graph.json."""
    graph_json = Path(graph_json)
    emb_path = Path(emb_path) if emb_path else embeddings_path_for(graph_json)
    if not emb_path.is_file():
        return True
    try:
        if emb_path.stat().st_mtime < graph_json.stat().st_mtime:
            return True
    except OSError:
        return True
    data = load_node_embeddings(emb_path)
    if not data:
        return True
    if int(data.get("version") or 0) != INDEX_VERSION:
        return True
    if (data.get("model") or "") != embedding_model():
        return True
    return False


def _load_graph_nodes(graph_json: Path) -> list[tuple[str, str, str]]:
    """Return (node_id, label, text) triples from graph.json."""
    raw = json.loads(Path(graph_json).read_text(encoding="utf-8"))
    nodes_raw = raw.get("nodes") or []
    triples: list[tuple[str, str, str]] = []
    for n in nodes_raw:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        if not nid:
            continue
        label = str(n.get("label") or nid)
        text = _node_text(label, n.get("source_location"))
        triples.append((nid, label, text))
    return triples


def build_node_embeddings(
    graph_json: Path,
    out_path: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Build or refresh ``node_embeddings.json`` next to ``graph.json``.

    Reuses vectors when node text + model hash matches the previous index.
    """
    graph_json = Path(graph_json).resolve()
    if not graph_json.is_file():
        raise FileNotFoundError(f"graph not found: {graph_json}")
    out_path = Path(out_path) if out_path else embeddings_path_for(graph_json)
    model = embedding_model()
    dim = embedding_dim()

    triples = _load_graph_nodes(graph_json)
    prev = None if force else load_node_embeddings(out_path)
    prev_nodes: dict[str, Any] = {}
    if (
        prev
        and prev.get("model") == model
        and int(prev.get("version") or 0) == INDEX_VERSION
    ):
        prev_nodes = prev.get("nodes") or {}

    to_embed: list[tuple[int, str]] = []  # (index into triples, text)
    reused: dict[str, dict[str, Any]] = {}
    for i, (nid, label, text) in enumerate(triples):
        th = _text_hash(model, text)
        old = prev_nodes.get(nid)
        if (
            isinstance(old, dict)
            and old.get("hash") == th
            and isinstance(old.get("vector"), list)
            and old["vector"]
        ):
            reused[nid] = {
                "label": label,
                "hash": th,
                "vector": old["vector"],
            }
        else:
            to_embed.append((i, text))

    new_vectors: dict[int, list[float]] = {}
    if to_embed:
        vectors = embed_texts([t for _, t in to_embed], model=model)
        for (idx, _), vec in zip(to_embed, vectors):
            new_vectors[idx] = vec
            if dim != len(vec):
                dim = len(vec)

    nodes_out: dict[str, dict[str, Any]] = dict(reused)
    for i, (nid, label, text) in enumerate(triples):
        if nid in nodes_out:
            continue
        vec = new_vectors.get(i)
        if not vec:
            continue
        nodes_out[nid] = {
            "label": label,
            "hash": _text_hash(model, text),
            "vector": vec,
        }

    payload = {
        "version": INDEX_VERSION,
        "model": model,
        "dim": dim,
        "graph": str(graph_json.name),
        "node_count": len(nodes_out),
        "nodes": nodes_out,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out_path)
    logger.info(
        "Wrote %s (%d nodes, %d newly embedded, model=%s)",
        out_path,
        len(nodes_out),
        len(to_embed),
        model,
    )
    return payload


def ensure_node_embeddings(graph_json: Path) -> dict[str, Any] | None:
    """Load embeddings, rebuilding if stale. Returns None on failure / disabled."""
    from lib.config import is_hybrid_graph_search_enabled

    if not is_hybrid_graph_search_enabled():
        return None
    graph_json = Path(graph_json)
    emb_path = embeddings_path_for(graph_json)
    try:
        if is_stale(graph_json, emb_path):
            return build_node_embeddings(graph_json, emb_path)
        return load_node_embeddings(emb_path)
    except Exception as exc:  # noqa: BLE001 — soft-fail for search path
        logger.warning("ensure_node_embeddings failed: %s", exc)
        return None


def maybe_build_node_embeddings(graph_json: Path) -> Path | None:
    """Publish-time helper: build embeddings or log and return None.

    No-ops when ``hybrid_graph_search`` is not enable in application/config.json.
    """
    from lib.config import is_hybrid_graph_search_enabled

    if not is_hybrid_graph_search_enabled():
        logger.info(
            "hybrid_graph_search is not enable — skip node embeddings for %s",
            graph_json,
        )
        return None
    graph_json = Path(graph_json)
    if not graph_json.is_file():
        return None
    try:
        out = embeddings_path_for(graph_json)
        build_node_embeddings(graph_json, out)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Skipping node embeddings for %s: %s", graph_json, exc
        )
        print(f"[embeddings] skip: {exc}")
        return None


def cosine_top_k(
    query_vec: list[float],
    index: dict[str, Any],
    *,
    k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[tuple[float, str]]:
    """Return [(score, node_id), ...] sorted descending, filtered by min_score."""
    nodes = index.get("nodes") or {}
    scored: list[tuple[float, str]] = []
    for nid, meta in nodes.items():
        if not isinstance(meta, dict):
            continue
        vec = meta.get("vector")
        if not isinstance(vec, list) or not vec:
            continue
        score = _cosine(query_vec, vec)
        if score >= min_score:
            scored.append((score, str(nid)))
    scored.sort(reverse=True)
    return scored[: max(0, int(k))]


def find_start_nodes_by_embedding(
    question: str,
    graph_json: Path,
    *,
    k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[tuple[float, str]]:
    """Embed question and return top-k node ids (score, id). Empty on failure."""
    question = (question or "").strip()
    if not question:
        return []
    index = ensure_node_embeddings(graph_json)
    if not index or not index.get("nodes"):
        return []
    try:
        qvec = embed_texts([question], model=index.get("model") or embedding_model())[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("query embedding failed: %s", exc)
        return []
    return cosine_top_k(qvec, index, k=k, min_score=min_score)
