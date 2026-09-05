"""Build NetworkX graph from extraction JSON and write graphify artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def sanitize_extraction(extraction: dict[str, Any]) -> dict[str, Any]:
    """Drop/repair malformed edges so graphify ``build_from_json`` does not crash.

    LLM chunks occasionally emit an edge with ``id`` instead of ``source`` (or
    omit endpoints entirely). Treat ``id`` as ``source`` when present; otherwise
    skip the edge.
    """
    raw_edges = extraction.get("edges") or []
    cleaned: list[dict[str, Any]] = []
    fixed = 0
    dropped = 0
    for edge in raw_edges:
        if not isinstance(edge, dict):
            dropped += 1
            continue
        item = dict(edge)
        if not item.get("source") and item.get("id"):
            item["source"] = item.pop("id")
            fixed += 1
        if item.get("source") and item.get("target"):
            cleaned.append(item)
        else:
            dropped += 1
    if fixed or dropped:
        print(
            f"[graph] sanitized edges: fixed={fixed} dropped={dropped} "
            f"kept={len(cleaned)}/{len(raw_edges)}"
        )
    out = dict(extraction)
    out["edges"] = cleaned
    return out


def prune_extraction_to_existing_sources(
    extraction: dict[str, Any],
    *,
    corpus_dir: Path | None = None,
    valid_names: set[str] | None = None,
) -> dict[str, Any]:
    """Drop nodes/edges whose ``source_file`` is missing from disk (or name set).

    Prevents stale extract/graph from pointing at deleted corpus turns — the UI
    error ``source file not readable or outside allowed roots``.
    """
    names = set(valid_names or ())
    resolved_ok: set[str] = set()
    if corpus_dir is not None:
        root = Path(corpus_dir).expanduser().resolve()
        if root.is_dir():
            for p in root.rglob("*.md"):
                if not p.is_file() or p.name == ".gitkeep":
                    continue
                try:
                    resolved_ok.add(str(p.resolve()))
                    names.add(p.name)
                except OSError:
                    continue

    def _ok(src: Any) -> bool:
        if not src:
            return True
        try:
            path = Path(str(src))
            if names and path.name in names:
                return True
            if resolved_ok and str(path.expanduser().resolve()) in resolved_ok:
                return True
            if path.is_file():
                return True
        except OSError:
            return False
        return False

    nodes = [n for n in (extraction.get("nodes") or []) if _ok(n.get("source_file"))]
    edges = [e for e in (extraction.get("edges") or []) if _ok(e.get("source_file"))]
    hyper = [
        h for h in (extraction.get("hyperedges") or []) if _ok(h.get("source_file"))
    ]
    dropped_nodes = len(extraction.get("nodes") or []) - len(nodes)
    if dropped_nodes:
        print(
            f"[graph] pruned missing sources: nodes -{dropped_nodes} "
            f"→ {len(nodes)}; edges → {len(edges)}"
        )
    out = dict(extraction)
    out["nodes"] = nodes
    out["edges"] = edges
    out["hyperedges"] = hyper
    return out


def build_and_export(
    extraction: dict[str, Any],
    artifact_dir: Path,
    *,
    corpus_label: str = "corpus",
) -> Path:
    """cluster + graph.json (+ GRAPH_REPORT). Returns graph.json path.

    ``artifact_dir`` is the output folder (session ``out/`` or legacy ``graphify-out/``).
    Files are written directly into it (no nested graphify-out/ subfolder).
    """
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.export import to_json
    from graphify.report import generate

    out = artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    corpus_dir: Path | None = None
    label_path = Path(corpus_label).expanduser()
    if label_path.is_dir():
        corpus_dir = label_path
    else:
        # Session layout: …/graph/out → sibling corpus/
        sibling = out.parent / "corpus"
        if sibling.is_dir():
            corpus_dir = sibling

    extraction = sanitize_extraction(extraction)
    extraction = prune_extraction_to_existing_sources(
        extraction, corpus_dir=corpus_dir
    )
    # Persist repaired extract so incremental --from-queue reuse stays valid.
    extract_path = out / ".graphify_extract.json"
    try:
        extract_path.write_text(
            json.dumps(extraction, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    G = build_from_json(extraction)
    if G.number_of_nodes() == 0:
        raise SystemExit("Graph is empty — extraction produced no nodes.")

    communities = cluster(G)
    cohesion = score_all(G, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    tokens = {
        "input": extraction.get("input_tokens", 0),
        "output": extraction.get("output_tokens", 0),
    }
    detection = {
        "total_files": len(
            {
                n.get("source_file")
                for n in (extraction.get("nodes") or [])
                if n.get("source_file")
            }
        ),
        "total_words": 0,
        "files": [],
        "code": 0,
        "docs": len(extraction.get("nodes") or []),
        "papers": 0,
        "images": 0,
    }

    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        tokens,
        corpus_label,
        suggested_questions=questions,
    )
    (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")

    graph_json = out / "graph.json"
    to_json(G, communities, str(graph_json))

    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
    }
    (out / ".graphify_analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{len(communities)} communities → {graph_json}"
    )
    return graph_json
