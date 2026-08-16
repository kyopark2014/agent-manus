"""Semantic extraction for markdown corpus (replaces /graphify skill Part B)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.config import bedrock_settings, llm_gateway_settings
from lib.llm import chat_json, default_model, resolve_bedrock_model_id

EXTRACT_SYSTEM = """You are a graphify extraction agent. Read the documents and extract a knowledge graph fragment.
Output ONLY valid JSON matching the schema - no explanation, no markdown fences, no preamble.

Rules:
- EXTRACTED: relationship explicit in source (import, call, citation, "see §3.2")
- INFERRED: reasonable inference (shared data structure, implied dependency)
- AMBIGUOUS: uncertain - flag for review, do not omit

Doc files: extract named concepts, entities, citations. Also extract rationale — sections that explain WHY a decision was made, trade-offs chosen, or design intent. These become nodes with `rationale_for` edges pointing to the concept they explain.

Semantic similarity: if two concepts solve the same problem without structural link, add `semantically_similar_to` (INFERRED, confidence_score 0.6-0.95).

Hyperedges: if 3+ nodes clearly participate together beyond pairwise edges, add up to 3 hyperedges.

If a file has YAML frontmatter (--- ... ---), copy source_url, captured_at, author, contributor onto every node from that file.
Also copy user_id from frontmatter into author when author is null.

confidence_score is REQUIRED on every edge:
- EXTRACTED: always 1.0
- INFERRED: 0.6-0.9 typically
- AMBIGUOUS: 0.1-0.3

Output exactly this JSON shape:
{"nodes":[{"id":"filestem_entityname","label":"Human Readable Name","file_type":"document","source_file":"relative/path","source_location":null,"source_url":null,"captured_at":null,"author":null,"contributor":null}],"edges":[{"source":"node_id","target":"node_id","relation":"calls|implements|references|cites|conceptually_related_to|shares_data_with|semantically_similar_to|rationale_for","confidence":"EXTRACTED|INFERRED|AMBIGUOUS","confidence_score":1.0,"source_file":"relative/path","source_location":null,"weight":1.0}],"hyperedges":[{"id":"snake_case_id","label":"Human Readable Label","nodes":["n1","n2","n3"],"relation":"participate_in|implement|form","confidence":"EXTRACTED|INFERRED","confidence_score":0.75,"source_file":"relative/path"}],"input_tokens":0,"output_tokens":0}
"""


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)



def _is_corpus_md(path: Path, corpus_dir: Path) -> bool:
    """True for staged corpus markdown; excludes PDF foundation work dirs.

    Wiki Sync keeps progressive ``extracted.md`` under
    ``converted/.pdf_pages/{stem}_{hash}/``; those are intermediates and must
    not be fed to semantic extraction (final text lives in ``*_partNN.md``).
    """
    if not path.is_file() or path.name == ".gitkeep":
        return False
    try:
        rel = path.resolve().relative_to(corpus_dir.resolve())
    except ValueError:
        return False
    return ".pdf_pages" not in rel.parts


def _read_doc(path: Path, *, max_chars: int = 12000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return text


def chunk_files(files: list[Path], *, chunk_size: int = 8) -> list[list[Path]]:
    """Smaller chunks than skill (20-25) to fit API context with full file bodies."""
    files = sorted(files, key=lambda p: (str(p.parent), p.name))
    return [files[i : i + chunk_size] for i in range(0, len(files), chunk_size)]


def extract_chunk(
    files: list[Path],
    *,
    corpus_root: Path,
    chunk_num: int,
    total_chunks: int,
    deep: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    parts = [
        f"Files (chunk {chunk_num} of {total_chunks}):",
    ]
    for path in files:
        rel = _rel_path(path, corpus_root)
        parts.append(f"\n===== FILE: {rel} =====\n{_read_doc(path)}")

    if deep:
        parts.append(
            "\nDEEP_MODE: be aggressive with INFERRED edges - indirect deps, "
            "shared assumptions, latent couplings. Mark uncertain ones AMBIGUOUS."
        )

    user = "\n".join(parts)
    data = chat_json(
        [
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": user},
        ],
        model=model,
    )
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    data.setdefault("hyperedges", [])

    # Normalize source_file to absolute paths so graphify cache keys match
    abs_by_name = {p.name: str(p.resolve()) for p in files}
    abs_by_rel = {_rel_path(p, corpus_root): str(p.resolve()) for p in files}
    for n in data["nodes"]:
        src = n.get("source_file") or ""
        n["source_file"] = abs_by_rel.get(src) or abs_by_name.get(Path(src).name) or src
    for e in data["edges"]:
        src = e.get("source_file") or ""
        e["source_file"] = abs_by_rel.get(src) or abs_by_name.get(Path(src).name) or src
    for h in data["hyperedges"]:
        src = h.get("source_file") or ""
        h["source_file"] = abs_by_rel.get(src) or abs_by_name.get(Path(src).name) or src
    return data


def _dedupe_merge(parts: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict] = []
    edges: list[dict] = []
    hyper: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple] = set()
    seen_hyper: set[str] = set()
    in_tok = out_tok = 0

    for part in parts:
        in_tok += int(part.get("input_tokens") or 0)
        out_tok += int(part.get("output_tokens") or 0)
        for n in part.get("nodes") or []:
            nid = n.get("id")
            if not nid or nid in seen_nodes:
                continue
            seen_nodes.add(nid)
            nodes.append(n)
        for e in part.get("edges") or []:
            key = (e.get("source"), e.get("target"), e.get("relation"), e.get("source_file"))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(e)
        for h in part.get("hyperedges") or []:
            hid = h.get("id") or json.dumps(h, sort_keys=True)
            if hid in seen_hyper:
                continue
            seen_hyper.add(hid)
            hyper.append(h)

    return {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": hyper,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
    }


def _load_existing_extract(artifact_dir: Path) -> dict[str, Any] | None:
    path = artifact_dir / ".graphify_extract.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    data.setdefault("hyperedges", [])
    data.setdefault("input_tokens", 0)
    data.setdefault("output_tokens", 0)
    return data


def _write_extract(artifact_dir: Path, extraction: dict[str, Any]) -> None:
    out_path = artifact_dir / ".graphify_extract.json"
    out_path.write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Extracted: {len(extraction['nodes'])} nodes, {len(extraction['edges'])} edges "
        f"(tokens in={extraction['input_tokens']} out={extraction['output_tokens']})"
    )


def _install_flat_cache_dir(gc: Any) -> Any:
    """Point graphify cache at artifact/cache; returns original cache_dir."""
    _orig_cache_dir = gc.cache_dir

    def _flat_cache_dir(
        root: Path = Path("."),
        kind: str | None = None,
        prompt_fp: str | None = None,
    ) -> Path:
        base = Path(root).resolve() / "cache"
        if kind:
            d = base / str(kind)
            if kind == "ast":
                ver = getattr(gc, "_EXTRACTOR_VERSION", None)
                if ver:
                    d = d / f"v{ver}"
            elif prompt_fp:
                d = d / f"p{prompt_fp}"
        else:
            d = base
        d.mkdir(parents=True, exist_ok=True)
        return d

    gc.cache_dir = _flat_cache_dir  # type: ignore[assignment]
    return _orig_cache_dir


def _log_llm_model(model: str) -> None:
    gw = llm_gateway_settings()
    if gw:
        print(f"LLM: {model} (gateway: {gw.get('source')})")
    else:
        bs = bedrock_settings()
        print(
            f"LLM: {resolve_bedrock_model_id(model)} "
            f"(bedrock:{bs['region']})"
        )


def extract_from_queue(
    corpus_dir: Path,
    artifact_dir: Path,
    *,
    deep: bool = False,
    chunk_size: int = 8,
    model: str | None = None,
) -> dict[str, Any]:
    """LLM-extract only queued corpus files and merge into existing extract JSON."""
    import graphify.cache as gc
    from graphify.cache import check_semantic_cache, save_semantic_cache

    from lib.extract_queue import (
        claim_pending,
        complete_items,
        fail_items,
        has_work,
    )

    corpus_dir = corpus_dir.resolve()
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if not has_work(artifact_dir):
        existing = _load_existing_extract(artifact_dir)
        if existing is not None and (existing.get("nodes") or existing.get("edges")):
            print("Extract queue empty — reusing existing .graphify_extract.json")
            return existing
        print("Extract queue empty — falling back to full corpus extract")
        return extract_corpus(
            corpus_dir,
            artifact_dir,
            deep=deep,
            chunk_size=chunk_size,
            model=model,
        )

    claimed = claim_pending(artifact_dir)
    paths: list[Path] = []
    for item in claimed:
        p = Path(item.get("corpus_path") or "")
        if p.is_file():
            paths.append(p.resolve())
        else:
            print(f"  WARNING: queued file missing: {p}")

    if not paths:
        fail_items(artifact_dir, claimed, error="corpus files missing")
        existing = _load_existing_extract(artifact_dir)
        if existing is not None:
            return existing
        raise SystemExit("Extract queue had items but no corpus files on disk")

    _orig = _install_flat_cache_dir(gc)
    try:
        abs_paths = [str(p) for p in paths]
        cached_nodes, cached_edges, cached_hyper, uncached = check_semantic_cache(
            abs_paths, root=artifact_dir
        )
        print(
            f"Queue: {len(paths)} file(s) · cache hit {len(paths) - len(uncached)} · "
            f"extract {len(uncached)}"
        )

        model = model or default_model()
        _log_llm_model(model)

        new_parts: list[dict[str, Any]] = []
        uncached_paths = [Path(p) for p in uncached]
        chunks = chunk_files(uncached_paths, chunk_size=chunk_size)
        failed_paths: set[str] = set()
        for i, chunk in enumerate(chunks, 1):
            names = ", ".join(p.name for p in chunk)
            print(f"  [{i}/{len(chunks)}] extracting {len(chunk)} file(s): {names[:80]}…")
            try:
                part = extract_chunk(
                    chunk,
                    corpus_root=corpus_dir,
                    chunk_num=i,
                    total_chunks=len(chunks),
                    deep=deep,
                    model=model,
                )
                new_parts.append(part)
                save_semantic_cache(
                    part.get("nodes") or [],
                    part.get("edges") or [],
                    part.get("hyperedges") or [],
                    root=artifact_dir,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: chunk {i} failed: {exc}")
                chunk_items = [
                    item
                    for item in claimed
                    if str(Path(item.get("corpus_path") or "").resolve())
                    in {str(p.resolve()) for p in chunk}
                ]
                fail_items(artifact_dir, chunk_items, error=str(exc))
                failed_paths.update(str(p.resolve()) for p in chunk)

        merged_new = (
            _dedupe_merge(new_parts)
            if new_parts
            else {
                "nodes": [],
                "edges": [],
                "hyperedges": [],
                "input_tokens": 0,
                "output_tokens": 0,
            }
        )
        existing = _load_existing_extract(artifact_dir) or {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }
        # Drop prior nodes/edges for files we just re-extracted so updates win.
        refreshed = {str(p.resolve()) for p in uncached_paths} - failed_paths
        if refreshed:
            existing = {
                "nodes": [
                    n
                    for n in (existing.get("nodes") or [])
                    if str(Path(n.get("source_file") or "").resolve()) not in refreshed
                ],
                "edges": [
                    e
                    for e in (existing.get("edges") or [])
                    if str(Path(e.get("source_file") or "").resolve()) not in refreshed
                ],
                "hyperedges": [
                    h
                    for h in (existing.get("hyperedges") or [])
                    if str(Path(h.get("source_file") or "").resolve()) not in refreshed
                ],
                "input_tokens": int(existing.get("input_tokens") or 0),
                "output_tokens": int(existing.get("output_tokens") or 0),
            }

        extraction = _dedupe_merge(
            [
                existing,
                {
                    "nodes": cached_nodes,
                    "edges": cached_edges,
                    "hyperedges": cached_hyper,
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
                merged_new,
            ]
        )
        # Drop nodes/edges that no longer map to corpus files (legacy paths etc.).
        valid_sources = {
            str(p.resolve())
            for p in corpus_dir.rglob("*.md")
            if _is_corpus_md(p, corpus_dir)
        }

        def _src_ok(src: Any) -> bool:
            if not src:
                return True
            try:
                return str(Path(str(src)).resolve()) in valid_sources
            except OSError:
                return False

        extraction = {
            "nodes": [n for n in extraction["nodes"] if _src_ok(n.get("source_file"))],
            "edges": [e for e in extraction["edges"] if _src_ok(e.get("source_file"))],
            "hyperedges": [
                h for h in extraction["hyperedges"] if _src_ok(h.get("source_file"))
            ],
            "input_tokens": extraction.get("input_tokens", 0),
            "output_tokens": extraction.get("output_tokens", 0),
        }
        _write_extract(artifact_dir, extraction)

        done_paths = {str(p) for p in paths} - failed_paths
        complete_items(
            artifact_dir,
            message_ids={
                (i.get("message_id") or "").strip()
                for i in claimed
                if (i.get("message_id") or "").strip()
                and str(Path(i.get("corpus_path") or "").resolve()) in done_paths
            },
            corpus_paths=done_paths,
        )
        return extraction
    finally:
        gc.cache_dir = _orig  # type: ignore[assignment]


def extract_corpus(
    corpus_dir: Path,
    artifact_dir: Path,
    *,
    deep: bool = False,
    chunk_size: int = 8,
    limit: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Extract semantic graph from corpus/*.md using LiteLLM + optional file cache.

    ``artifact_dir`` receives ``.graphify_extract.json`` and ``cache/`` (shared
    with publish output when using session storage ``out/``).
    """
    import graphify.cache as gc
    from graphify.cache import check_semantic_cache, save_semantic_cache

    corpus_dir = corpus_dir.resolve()
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    _orig_cache_dir = _install_flat_cache_dir(gc)

    try:
        files = sorted(
            p for p in corpus_dir.rglob("*.md") if _is_corpus_md(p, corpus_dir)
        )
        if limit is not None:
            files = files[:limit]
        if not files:
            raise SystemExit(f"No markdown files under {corpus_dir}")

        abs_paths = [str(p.resolve()) for p in files]
        cached_nodes, cached_edges, cached_hyper, uncached = check_semantic_cache(
            abs_paths, root=artifact_dir
        )
        print(
            f"Corpus: {len(files)} files · cache hit {len(files) - len(uncached)} · "
            f"extract {len(uncached)}"
        )

        model = model or default_model()
        _log_llm_model(model)

        new_parts: list[dict[str, Any]] = []
        uncached_paths = [Path(p) for p in uncached]
        chunks = chunk_files(uncached_paths, chunk_size=chunk_size)
        for i, chunk in enumerate(chunks, 1):
            names = ", ".join(p.name for p in chunk)
            print(f"  [{i}/{len(chunks)}] extracting {len(chunk)} file(s): {names[:80]}…")
            try:
                part = extract_chunk(
                    chunk,
                    corpus_root=corpus_dir,
                    chunk_num=i,
                    total_chunks=len(chunks),
                    deep=deep,
                    model=model,
                )
                new_parts.append(part)
                save_semantic_cache(
                    part.get("nodes") or [],
                    part.get("edges") or [],
                    part.get("hyperedges") or [],
                    root=artifact_dir,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: chunk {i} failed: {exc}")

        merged_new = _dedupe_merge(new_parts) if new_parts else {
            "nodes": [],
            "edges": [],
            "hyperedges": [],
            "input_tokens": 0,
            "output_tokens": 0,
        }
        extraction = _dedupe_merge(
            [
                {
                    "nodes": cached_nodes,
                    "edges": cached_edges,
                    "hyperedges": cached_hyper,
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
                merged_new,
            ]
        )

        _write_extract(artifact_dir, extraction)
        return extraction
    finally:
        gc.cache_dir = _orig_cache_dir  # type: ignore[assignment]
