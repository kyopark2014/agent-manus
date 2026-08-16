"""Build NetworkX graph from extraction JSON and write graphify artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
