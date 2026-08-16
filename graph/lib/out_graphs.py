"""Split a graphify graph.json by author/user and write out/graph.html."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from lib.corpus import safe_slug


def _atomic_write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)


def _load_graph(path: Path) -> nx.Graph:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        G = json_graph.node_link_graph(data, edges="links")
    except TypeError:
        G = json_graph.node_link_graph(data)
    if "hyperedges" in data:
        G.graph["hyperedges"] = data["hyperedges"]
    return G


def _author_of(node_id: str, data: dict[str, Any]) -> str:
    author = (data.get("author") or "").strip()
    if author:
        return author
    source = data.get("source_file") or ""
    m = re.search(r"turn-\d+-([^-/]+)", source)
    if m:
        return m.group(1)
    return "unknown"


def group_nodes_by_user(G: nx.Graph) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for node_id, data in G.nodes(data=True):
        groups[_author_of(node_id, data)].append(node_id)
    return dict(groups)


def subgraph_for_user(G: nx.Graph, node_ids: list[str]) -> nx.Graph:
    H = G.subgraph(node_ids).copy()
    # Keep hyperedges that still have ≥2 members in this subgraph
    keep = set(node_ids)
    hyper = []
    for he in G.graph.get("hyperedges", []) or []:
        members = [n for n in he.get("nodes", []) if n in keep]
        if len(members) >= 2:
            hyper.append({**he, "nodes": members})
    if hyper:
        H.graph["hyperedges"] = hyper
    return H


def write_user_graph(
    H: nx.Graph,
    *,
    user_id: str,
    out_dir: Path,
    pattern: str | None = None,
) -> dict[str, Path]:
    """Cluster + export pattern HTML/JSON. Writes out/graph.html (+ graph.json)."""
    from graphify.cluster import cluster
    from graphify.export import to_json

    from lib.patterns import resolve_graph_pattern, write_pattern_html

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "graph.html"
    json_path = out_dir / "graph.json"

    if H.number_of_nodes() == 0:
        return {}

    communities = cluster(H)
    # Write JSON via temp so readers never see a partial file.
    tmp_json = json_path.with_suffix(json_path.suffix + ".tmp")
    to_json(H, communities, str(tmp_json))
    os.replace(tmp_json, json_path)
    pid = pattern or resolve_graph_pattern(user_id=user_id)
    write_pattern_html(
        pid,
        H,
        communities,
        html_path,
        title="Knowledge Graph",
        subtitle=(
            "지식 그래프 · 노드 클릭 시 출처·관계 상세를 볼 수 있습니다. "
            f"({H.number_of_nodes()} nodes / {H.number_of_edges()} edges)"
        ),
    )
    from lib.embeddings import maybe_build_node_embeddings

    emb = maybe_build_node_embeddings(json_path)
    if emb is not None:
        return {"html": html_path, "json": json_path, "embeddings": emb}
    return {"html": html_path, "json": json_path}


def publish_user_graphs(
    graph_json: Path,
    out_dir: Path,
    *,
    user: str | None = None,
    min_nodes: int = 1,
    pattern: str | None = None,
) -> list[dict[str, Any]]:
    """Split graph.json by author → out/graph.html (+ graph.json)."""
    from lib.patterns import resolve_graph_pattern

    G = _load_graph(graph_json)
    groups = group_nodes_by_user(G)
    results: list[dict[str, Any]] = []
    pid = pattern or resolve_graph_pattern(user_id=user)


    for user_id, node_ids in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        if user is not None and user_id != user and safe_slug(user_id) != safe_slug(user):
            continue
        if len(node_ids) < min_nodes:
            continue
        H = subgraph_for_user(G, node_ids)
        paths = write_user_graph(
            H, user_id=user_id, out_dir=out_dir, pattern=pid
        )
        if not paths:
            continue
        results.append(
            {
                "user_id": user_id,
                "slug": safe_slug(user_id),
                "nodes": H.number_of_nodes(),
                "edges": H.number_of_edges(),
                "pattern": pid,
                **{k: str(v) for k, v in paths.items()},
            }
        )
        # Per-user out dirs only hold one graph.html; stop after first match.
        if user is not None:
            break
    return results




def republish_html_from_json(
    out_dir: Path,
    *,
    user_id: str | None = None,
    pattern: str | None = None,
) -> Path | None:
    """Re-render graph.html from existing out/graph.json (no re-extract)."""
    from graphify.cluster import cluster

    from lib.patterns import resolve_graph_pattern, write_pattern_html

    json_path = out_dir / "graph.json"
    if not json_path.is_file():
        return None
    G = _load_graph(json_path)
    if G.number_of_nodes() == 0:
        return None
    communities: dict[int, list[str]] = {}
    for nid, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is None:
            continue
        communities.setdefault(int(cid), []).append(nid)
    if not communities:
        communities = cluster(G)
    html_path = out_dir / "graph.html"
    pid = pattern or resolve_graph_pattern(user_id=user_id)
    write_pattern_html(
        pid,
        G,
        communities,
        html_path,
        title="Knowledge Graph",
        subtitle=(
            "지식 그래프 · 노드 클릭 시 출처·관계 상세를 볼 수 있습니다. "
            f"({G.number_of_nodes()} nodes / {G.number_of_edges()} edges)"
        ),
    )
    # Pattern switch only rewrites HTML — do not rebuild embeddings here
    # (that blocks PATCH /api/session/settings and hangs the graph UI).
    return html_path


def collect_from_graphify_out(
    src: Path,
    out_dir: Path,
    *,
    user: str,
) -> dict[str, Path]:
    """Copy a single-user graphify-out run into out/graph.html (+ .json)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    mapping = {
        "graph.html": out_dir / "graph.html",
        "graph.json": out_dir / "graph.json",
        "GRAPH_REPORT.md": out_dir / "GRAPH_REPORT.md",
    }
    for name, dest in mapping.items():
        src_file = src / name
        if src_file.is_file():
            _atomic_write_bytes(dest, src_file.read_bytes())
            written[name] = dest
    graph_dest = written.get("graph.json")
    if graph_dest is not None:
        from lib.embeddings import maybe_build_node_embeddings

        emb = maybe_build_node_embeddings(graph_dest)
        if emb is not None:
            written["node_embeddings.json"] = emb
    return written
