"""Graphify-style BFS/DFS query over a user's graph.json + source text excerpts.

Start-node selection is hybrid: lexical label/body match plus optional
LiteLLM embedding similarity (see ``graph_embeddings`` / ``node_embeddings.json``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from networkx.readwrite import json_graph

_MAX_FILE_BYTES = 500_000
_MAX_SOURCES = 6
_MAX_EXCERPT_CHARS = 1800
_MAX_TOTAL_EXCERPT_CHARS = 8000
_MAX_LABELS_FOR_EXCERPT = 3
_QUERY_TERM_WEIGHT = 10
_LABEL_TERM_WEIGHT = 1
_PAGE_HEADING_RE = re.compile(r"^## Page (\d+)\s*$", re.MULTILINE)
_PAGE_LOC_RE = re.compile(
    r"(?:pages?|p\.?)\s*(\d+)(?:\s*[-–—]\s*(\d+))?",
    re.IGNORECASE,
)
# Minimal bilingual aliases so English queries hit Korean converted pages.
_TERM_ALIASES: dict[str, list[str]] = {
    "biden": ["바이든"],
    "trump": ["트럼프"],
    "comparison": ["비교"],
    "tariff": ["관세"],
    "deficit": ["적자", "무역적자"],
    "바이든": ["biden"],
    "트럼프": ["trump"],
    "비교": ["comparison"],
    "관세": ["tariff"],
    "무역적자": ["deficit", "trade deficit"],
}


# Prefer these for excerpts / body search (never dump PDF binary into the UI).
_TEXT_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".text",
    ".rst",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".h",
}
_BINARY_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".mp4",
    ".mp3",
    ".wav",
    ".docx",
    ".pptx",
    ".xlsx",
    ".zip",
}

_KNOWN_SUFFIXES = _TEXT_SUFFIXES | _BINARY_SUFFIXES


def _document_stem(path: Path) -> str:
    """Stem used to find ``converted/{stem}_part*.md``.

    Extraction sometimes stores ``source_file`` as a bare document title
    (e.g. ``WB_Troubleshooting Manual_KOR_4.4`` without ``.pdf``). ``Path.stem``
    would treat ``.4`` as a suffix and look for the wrong converted files.
    """
    suffix = path.suffix.lower()
    if suffix in _KNOWN_SUFFIXES:
        return path.stem
    return path.name


def _load_graph(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        return json_graph.node_link_graph(data, edges="links")
    except TypeError:
        return json_graph.node_link_graph(data)


def _query_terms(question: str) -> list[str]:
    """Tokenize question for label matching.

    English tokens shorter than 3 chars are skipped (a, of, …).
    CJK tokens keep length >= 2 so queries like \"여행\" still match.
    """
    raw_parts = [t for t in re.split(r"\s+", question.strip()) if t]
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        low = part.lower()
        # Keep whole token if CJK-ish or long enough
        has_cjk = bool(re.search(r"[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]", part))
        candidates = [low]
        # Also split on punctuation for mixed tokens (서울-제주)
        candidates.extend(
            p.lower()
            for p in re.split(r"[^\w\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]+", part)
            if p
        )
        for t in candidates:
            if not t or t in seen:
                continue
            if has_cjk or re.search(r"[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]", t):
                if len(t) < 2:
                    continue
            elif len(t) <= 2:
                continue
            seen.add(t)
            out.append(t)
    return _expand_query_terms(out)


def _expand_query_terms(terms: list[str]) -> list[str]:
    """Attach a few EN↔KO aliases without dropping the original tokens."""
    out: list[str] = []
    seen: set[str] = set()
    for term in terms:
        candidates = [term, *(_TERM_ALIASES.get(term.lower(), []))]
        for cand in candidates:
            key = cand.lower()
            if not cand or key in seen:
                continue
            seen.add(key)
            out.append(cand)
    return out


def _score_label(label: str, terms: list[str]) -> int:
    low = (label or "").lower()
    return sum(1 for t in terms if t in low)


def _text_term_score(text: str, terms: list[str]) -> int:
    if not text or not terms:
        return 0
    low = text.lower()
    return sum(1 for t in terms if t in low)


def _find_nodes_by_source_content(
    G,
    terms: list[str],
    roots: list[Path],
    *,
    limit: int = 24,
) -> list[tuple[int, str]]:
    """Score nodes by whether their source_file body contains query terms."""
    by_file: dict[str, list[str]] = {}
    for nid, data in G.nodes(data=True):
        src = str(data.get("source_file") or "").strip()
        if src:
            by_file.setdefault(src, []).append(nid)

    scored: list[tuple[int, str]] = []
    checked = 0
    for src, nids in by_file.items():
        if checked >= 80:
            break
        _path, text, err = _read_readable_source(Path(src), roots)
        if err or not text:
            continue
        checked += 1
        score = _text_term_score(text, terms)
        if score <= 0:
            continue
        for nid in nids:
            # Prefer higher-degree hubs slightly so BFS starts somewhere useful.
            boost = min(3, int(G.degree(nid) or 0) // 3)
            scored.append((score * 10 + boost, nid))

    scored.sort(reverse=True)
    # unique node ids preserving rank
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    for score, nid in scored:
        if nid in seen:
            continue
        seen.add(nid)
        out.append((score, nid))
        if len(out) >= limit:
            break
    return out


def _source_path_candidates(path: Path) -> list[Path]:
    """Absolute extract paths may point at another host/mount; try graph-relative forms."""
    candidates: list[Path] = [path]
    parts = path.parts
    for marker in ("corpus", "out", "raw", "graphify-out", "converted"):
        if marker in parts:
            idx = parts.index(marker)
            candidates.append(Path(*parts[idx:]))
            break
    name = path.name
    if name:
        candidates.append(Path(name))
        candidates.append(Path("corpus") / name)
        candidates.append(Path("out") / name)
        candidates.append(Path("raw") / name)
        candidates.append(Path("graphify-out") / "converted" / name)
        stem = _document_stem(path)
        suffix = path.suffix.lower()
        if suffix == ".pdf" or suffix not in _KNOWN_SUFFIXES:
            candidates.append(Path("graphify-out") / "converted" / f"{stem}.md")
            candidates.append(Path("raw") / f"{stem}.pdf")
            candidates.append(Path(f"{stem}.pdf"))
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


def _allowed_source(path: Path, roots: list[Path]) -> Path | None:
    """Resolve source_file under allowed graph roots.

    Extraction stores absolute paths (``/mnt/app-data/...`` or a laptop path).
    AgentCore Runtime mounts the same tree at ``/mnt/workspace/{user}/graph``,
    so we remap by ``corpus/`` / ``out/`` suffix or basename when the absolute
    path is missing.
    """
    for cand in _source_path_candidates(path):
        try:
            if cand.is_absolute():
                resolved = cand.expanduser().resolve()
                if resolved.is_file():
                    for root in roots:
                        try:
                            resolved.relative_to(root.resolve())
                            return resolved
                        except ValueError:
                            continue
            for root in roots:
                try:
                    resolved = (root / cand).expanduser().resolve()
                    if not resolved.is_file():
                        continue
                    resolved.relative_to(root.resolve())
                    return resolved
                except (OSError, ValueError):
                    continue
        except OSError:
            continue
    return None



def _looks_binary(raw: bytes) -> bool:
    if not raw:
        return False
    if raw.startswith(b"%PDF") or raw[:4] == b"\x89PNG" or raw[:2] == b"\xff\xd8":
        return True
    sample = raw[:4096]
    if b"\x00" in sample:
        return True
    # Count ASCII controls/printables and UTF-8 multibyte bytes. Lead bytes are
    # >= 0xC0, but continuation bytes are 0x80-0xBF — omitting those falsely
    # marks Korean/CJK markdown as binary (ratio often ~0.65 < 0.75).
    textish = sum(
        1
        for b in sample
        if b in (9, 10, 13) or 32 <= b < 127 or b >= 0x80
    )
    return textish < len(sample) * 0.75


def _converted_markdown_for(
    src: Path, roots: list[Path]
) -> list[Path]:
    """Find wiki ``graphify-out/converted/{stem}*.md`` sidecars for a binary source."""
    stems = [_document_stem(src)]
    # Also try Path.stem for real extensions (already covered) and bare title edge cases.
    if src.stem and src.stem not in stems:
        stems.append(src.stem)
    if src.name and src.name not in stems:
        stems.append(src.name)
    dirs: list[Path] = []
    seen: set[str] = set()

    def _add_dir(d: Path) -> None:
        key = str(d)
        if key in seen:
            return
        seen.add(key)
        dirs.append(d)

    for root in roots:
        try:
            r = root.resolve()
        except OSError:
            continue
        _add_dir(r / "converted")
        _add_dir(r / "graphify-out" / "converted")
        if r.name == "graphify-out":
            _add_dir(r / "converted")
        if (r / "graph.json").is_file():
            _add_dir(r / "converted")

    found: list[Path] = []
    found_keys: set[str] = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for stem in stems:
            exact = d / f"{stem}.md"
            if exact.is_file():
                key = str(exact.resolve())
                if key not in found_keys:
                    found_keys.add(key)
                    found.append(exact)
            parts = sorted(d.glob(f"{stem}_part*.md"))
            for p in parts:
                key = str(p.resolve())
                if key not in found_keys:
                    found_keys.add(key)
                    found.append(p)
    return found


def _decode_text(raw: bytes) -> str:
    if len(raw) > _MAX_FILE_BYTES:
        raw = raw[:_MAX_FILE_BYTES]
    return raw.decode("utf-8", errors="replace")


def _parse_pages_from_location(loc: str | None) -> set[int]:
    """Parse page numbers from ``source_location`` values like ``Page 9`` / ``Page 9-11``."""
    if not loc:
        return set()
    pages: set[int] = set()
    for match in _PAGE_LOC_RE.finditer(str(loc)):
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        lo, hi = (start, end) if start <= end else (end, start)
        pages.update(range(lo, hi + 1))
    return pages


def _pages_in_markdown(text: str) -> set[int]:
    return {int(m.group(1)) for m in _PAGE_HEADING_RE.finditer(text or "")}


def _page_sections(text: str) -> list[tuple[int, str]]:
    """Return ``(page_num, section_markdown)`` for each ``## Page N`` block."""
    if not text:
        return []
    parts = _PAGE_HEADING_RE.split(text)
    sections: list[tuple[int, str]] = []
    i = 1
    while i + 1 < len(parts):
        try:
            page_num = int(parts[i])
        except ValueError:
            i += 2
            continue
        body = (parts[i + 1] or "").strip()
        section = f"## Page {page_num}\n\n{body}" if body else f"## Page {page_num}"
        sections.append((page_num, section))
        i += 2
    return sections


def _extract_page_sections(text: str, pages: set[int]) -> str | None:
    """Keep only ``## Page N`` sections whose N is in *pages*."""
    if not text or not pages:
        return None
    sections = [
        section for page_num, section in _page_sections(text) if page_num in pages
    ]
    return "\n\n".join(sections) if sections else None


def _pages_matching_terms(text: str, terms: list[str]) -> dict[int, int]:
    """Map page number → count of distinct query terms hit in that section."""
    if not text or not terms:
        return {}
    lowered = [t.lower() for t in terms if t]
    scores: dict[int, int] = {}
    for page_num, section in _page_sections(text):
        low = section.lower()
        score = sum(1 for t in lowered if t in low)
        if score > 0:
            scores[page_num] = score
    return scores


def _best_term_pages(scores: dict[int, int]) -> set[int]:
    """Keep pages with the strongest query-term overlap (ties included)."""
    if not scores:
        return set()
    best = max(scores.values())
    # If the best page only matches one broad term, still return those pages;
    # multi-term queries naturally prefer the denser page (e.g. 바이든+무역적자).
    return {page for page, score in scores.items() if score == best}


def _load_converted_chunks(
    converted: list[Path],
    *,
    pages: set[int] | None = None,
    terms: list[str] | None = None,
) -> list[tuple[Path, str]]:
    """Read converted markdown, scoped to location pages and/or query-term pages."""
    if not converted:
        return []

    term_list = [t for t in (terms or []) if t]
    path_texts: list[tuple[Path, str]] = []
    term_scores: dict[int, int] = {}
    for path in converted:
        try:
            text = _decode_text(path.read_bytes())
        except OSError:
            continue
        path_texts.append((path, text))
        if term_list:
            for page_num, score in _pages_matching_terms(text, term_list).items():
                term_scores[page_num] = max(term_scores.get(page_num, 0), score)

    include_pages: set[int] = set(pages or ())
    best_term_pages = _best_term_pages(term_scores)
    if best_term_pages:
        # Prefer pages that both match the query densely and/or the node location.
        if include_pages:
            overlap = include_pages & best_term_pages
            include_pages = overlap or (include_pages | best_term_pages)
        else:
            include_pages = best_term_pages

    if include_pages:
        chunks: list[tuple[Path, str]] = []
        for path, text in path_texts:
            sliced = _extract_page_sections(text, include_pages)
            if sliced:
                chunks.append((path, sliced))
        if chunks:
            return chunks

    # No page headings / no page hits — return full converted parts (legacy).
    return path_texts


def _pick_display_path(
    chunks: list[tuple[Path, str]],
    pages: set[int] | None,
    terms: list[str] | None = None,
) -> Path:
    """Choose the converted path that best represents the returned text."""
    if not chunks:
        raise ValueError("chunks must be non-empty")
    if len(chunks) == 1:
        return chunks[0][0]

    def _term_density(item: tuple[Path, str]) -> tuple[int, int]:
        text = item[1]
        if not terms:
            return (0, len(_pages_in_markdown(text)))
        scores = _pages_matching_terms(text, terms)
        return (sum(scores.values()), len(scores))

    if terms:
        return max(chunks, key=_term_density)[0]
    if pages:
        return max(
            chunks,
            key=lambda item: len(_pages_in_markdown(item[1]) & pages),
        )[0]
    return max(chunks, key=lambda item: len(_pages_in_markdown(item[1])))[0]


def _read_readable_source(
    src: Path,
    roots: list[Path],
    *,
    pages: set[int] | None = None,
    terms: list[str] | None = None,
) -> tuple[Path | None, str, str | None]:
    """Load excerptable text for ``src``.

    Graph nodes often point at the original PDF (provenance). For reading we
    prefer Sync's converted markdown under ``graphify-out/converted/``.
    When *pages* / query *terms* are set, only matching ``## Page N`` sections
    are used so citations point at the relevant ``*_partNN.md``.
    Returns ``(path_used, text, error)``.
    """
    allowed = _allowed_source(src, roots)
    suffix = src.suffix.lower()

    need_converted = suffix in _BINARY_SUFFIXES or (
        suffix not in _TEXT_SUFFIXES and suffix != ""
    )
    converted = _converted_markdown_for(src, roots)

    def _from_converted() -> tuple[Path | None, str, str | None] | None:
        if not converted:
            return None
        chunks = _load_converted_chunks(
            converted, pages=pages, terms=terms
        )
        if not chunks:
            return None
        display_pages = set(pages or ())
        if terms:
            term_scores: dict[int, int] = {}
            for _, text in chunks:
                for page_num, score in _pages_matching_terms(text, terms).items():
                    term_scores[page_num] = max(term_scores.get(page_num, 0), score)
            display_pages |= _best_term_pages(term_scores)
        path_used = _pick_display_path(
            chunks, display_pages or None, terms=terms
        )
        return path_used, "\n\n".join(text for _, text in chunks), None

    if need_converted and converted:
        loaded = _from_converted()
        if loaded is not None:
            return loaded

    if allowed is None:
        loaded = _from_converted()
        if loaded is not None:
            return loaded
        return None, "", "source file not readable or outside allowed roots"

    try:
        raw = allowed.read_bytes()
    except OSError as exc:
        loaded = _from_converted()
        if loaded is not None:
            return loaded
        return None, "", str(exc)

    # Known text extensions (.md, .txt, …) are always decoded — do not let the
    # binary heuristic discard corpus markdown with heavy CJK UTF-8.
    if suffix in _TEXT_SUFFIXES:
        text = _decode_text(raw)
        include_pages = set(pages or ())
        if terms:
            include_pages |= _best_term_pages(
                _pages_matching_terms(text, terms)
            )
        if include_pages:
            sliced = _extract_page_sections(text, include_pages)
            if sliced:
                return allowed, sliced, None
        return allowed, text, None

    if _looks_binary(raw) or suffix in _BINARY_SUFFIXES:
        loaded = _from_converted()
        if loaded is not None:
            return loaded
        return (
            allowed,
            "",
            "binary source (e.g. PDF); no converted markdown under graphify-out/converted",
        )

    return allowed, _decode_text(raw), None


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n+", text)
    out: list[str] = []
    for chunk in chunks:
        cleaned = re.sub(r"[ \t]+\n", "\n", chunk).strip()
        if len(cleaned) >= 40:
            out.append(cleaned)
    if out:
        return out
    # Fallback: sliding windows of lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    joined = "\n".join(lines)
    return [joined[i : i + 600] for i in range(0, min(len(joined), 3000), 500)]


def _label_terms(labels: list[str], *, limit: int = _MAX_LABELS_FOR_EXCERPT) -> list[str]:
    """Tokenize a small set of node labels for weak excerpt scoring."""
    out: list[str] = []
    seen: set[str] = set()
    for lab in labels[: max(0, limit)]:
        for token in re.split(r"[\s/()\[\]|,:-]+", str(lab)):
            tok = token.lower().strip()
            if len(tok) <= 2 or tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
    return out


def _extract_excerpts(
    text: str,
    *,
    terms: list[str],
    labels: list[str],
    source_location: str | None,
) -> list[str]:
    """Rank paragraphs with query terms weighted far above label tokens."""
    paras = _paragraphs(text)
    if not paras:
        return []

    query_terms = [t.lower() for t in terms if t]
    label_terms = _label_terms(labels)
    pages = _parse_pages_from_location(source_location)

    ranked: list[tuple[int, int, str]] = []
    for para in paras:
        low = para.lower()
        q_hits = sum(1 for t in query_terms if t in low)
        l_hits = sum(1 for t in label_terms if t in low)
        if q_hits == 0 and l_hits == 0:
            continue
        # Query matches dominate; label-only hits stay weak so BFS neighbor
        # labels cannot drown page-local evidence.
        score = q_hits * _QUERY_TERM_WEIGHT + l_hits * _LABEL_TERM_WEIGHT
        if pages:
            covered = _pages_in_markdown(para)
            if covered & pages:
                score += 5
            elif any(f"page {n}" in low for n in pages):
                score += 3
        ranked.append((score, q_hits, para))

    ranked.sort(key=lambda item: (-item[0], -item[1], -len(item[2])))
    preferred = [item for item in ranked if item[1] > 0] if query_terms else ranked
    pool = preferred if preferred else ranked

    excerpts: list[str] = []
    used = 0
    for _, _, para in pool[:4]:
        snippet = (
            para if len(para) <= _MAX_EXCERPT_CHARS else para[: _MAX_EXCERPT_CHARS - 1] + "…"
        )
        if used + len(snippet) > _MAX_EXCERPT_CHARS:
            remain = _MAX_EXCERPT_CHARS - used
            if remain < 80:
                break
            snippet = snippet[: remain - 1] + "…"
        excerpts.append(snippet)
        used += len(snippet)
        if used >= _MAX_EXCERPT_CHARS:
            break

    if excerpts:
        return excerpts
    # No keyword hit: return a short head preview
    head = text.strip()
    if not head:
        return []
    return [head[: min(700, _MAX_EXCERPT_CHARS)] + ("…" if len(head) > 700 else "")]


def query_user_graph(
    graph_json: Path,
    question: str,
    *,
    mode: str = "bfs",
    budget: int = 2000,
    allowed_roots: list[Path] | None = None,
    use_embeddings: bool | None = None,
) -> dict[str, Any]:
    """Run graphify-style traversal and attach source text excerpts.

    When ``use_embeddings`` is None, follows ``hybrid_graph_search`` in
    application/config.json (``enable`` → embedding hybrid on).
    """
    if use_embeddings is None:
        try:
            from application import utils as _app_utils

            use_embeddings = _app_utils.is_hybrid_graph_search_enabled()
        except Exception:  # noqa: BLE001
            use_embeddings = True
    use_embeddings = bool(use_embeddings)
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")
    if not graph_json.is_file():
        raise FileNotFoundError(f"graph not found: {graph_json}")

    mode = "dfs" if str(mode).lower() == "dfs" else "bfs"
    budget = max(200, min(int(budget), 8000))
    terms = _query_terms(question)
    if not terms:
        terms = [question.lower()]

    G = _load_graph(graph_json)
    roots = allowed_roots or [graph_json.parent.parent]

    scored: list[tuple[int, str]] = []
    for nid, ndata in G.nodes(data=True):
        score = _score_label(str(ndata.get("label") or ""), terms)
        if score > 0:
            scored.append((score, nid))
    scored.sort(reverse=True)
    start_nodes = [nid for _, nid in scored[:3]]
    match_parts: list[str] = []
    if start_nodes:
        match_parts.append("label")

    # Document search: also match corpus/source body text.
    # Needed when labels are English ("Weather…") but the query is Korean ("날씨").
    content_scored = _find_nodes_by_source_content(G, terms, roots)
    if not start_nodes:
        start_nodes = [nid for _, nid in content_scored[:3]]
        if start_nodes:
            match_parts.append("source")
    elif content_scored:
        # Augment starts with strong content matches not already selected.
        chosen = set(start_nodes)
        for _, nid in content_scored:
            if nid in chosen:
                continue
            start_nodes.append(nid)
            chosen.add(nid)
            if len(start_nodes) >= 3:
                break
        if "source" not in match_parts:
            match_parts.append("source")

    # Hybrid: embedding similarity for synonyms (날씨 ↔ Weather). Soft-fails.
    # Gated by application/config.json hybrid_graph_search=enable.
    embed_scored: list[tuple[float, str]] = []
    if use_embeddings:
        try:
            from application.graph_embeddings import find_start_nodes_by_embedding
        except ImportError:
            try:
                from graph_embeddings import find_start_nodes_by_embedding  # type: ignore
            except ImportError:
                find_start_nodes_by_embedding = None  # type: ignore
        if find_start_nodes_by_embedding is not None:
            try:
                embed_scored = find_start_nodes_by_embedding(question, graph_json)
            except Exception:  # noqa: BLE001
                embed_scored = []
    if embed_scored:
        chosen = set(start_nodes)
        for _, nid in embed_scored:
            if nid not in G:
                continue
            if nid in chosen:
                continue
            start_nodes.append(nid)
            chosen.add(nid)
            if len(start_nodes) >= 5:
                break
        start_set = set(start_nodes)
        if any(nid in start_set for _, nid in embed_scored if nid in G):
            match_parts.append("embed")

    match_via = "+".join(match_parts) if match_parts else "none"

    if not start_nodes:
        return {
            "question": question,
            "mode": mode,
            "match_via": match_via,
            "start_nodes": [],
            "nodes": [],
            "edges": [],
            "sources": [],
            "message": f"No matching nodes found for: {', '.join(terms)}",
        }

    content_score_by_id = {nid: score for score, nid in content_scored}
    embed_score_by_id = {nid: score for score, nid in embed_scored}

    subgraph_nodes: set[str] = set()
    subgraph_edges: list[tuple[str, str]] = []

    if mode == "dfs":
        visited: set[str] = set()
        stack = [(n, 0) for n in reversed(start_nodes)]
        while stack:
            node, depth = stack.pop()
            if node in visited or depth > 6:
                continue
            visited.add(node)
            subgraph_nodes.add(node)
            for neighbor in G.neighbors(node):
                if neighbor not in visited:
                    stack.append((neighbor, depth + 1))
                    subgraph_edges.append((node, neighbor))
    else:
        frontier = set(start_nodes)
        subgraph_nodes = set(start_nodes)
        for _ in range(3):
            next_frontier: set[str] = set()
            for n in frontier:
                for neighbor in G.neighbors(n):
                    if neighbor not in subgraph_nodes:
                        next_frontier.add(neighbor)
                        subgraph_edges.append((n, neighbor))
            subgraph_nodes.update(next_frontier)
            frontier = next_frontier

    def relevance(nid: str) -> int:
        return (
            _score_label(str(G.nodes[nid].get("label") or ""), terms) * 10
            + int(content_score_by_id.get(nid, 0))
            + int(embed_score_by_id.get(nid, 0.0) * 10)
        )

    ranked_nodes = sorted(subgraph_nodes, key=relevance, reverse=True)

    nodes_out: list[dict[str, Any]] = []
    for nid in ranked_nodes:
        d = G.nodes[nid]
        nodes_out.append(
            {
                "id": nid,
                "label": d.get("label") or nid,
                "source_file": d.get("source_file") or "",
                "source_location": d.get("source_location"),
                "community": d.get("community"),
                "file_type": d.get("file_type"),
            }
        )

    edges_out: list[dict[str, Any]] = []
    seen_e: set[tuple[str, str, str]] = set()
    for u, v in subgraph_edges:
        if u not in subgraph_nodes or v not in subgraph_nodes:
            continue
        ed = G.edges[u, v]
        key = (u, v, str(ed.get("relation") or ""))
        if key in seen_e:
            continue
        seen_e.add(key)
        edges_out.append(
            {
                "source": u,
                "target": v,
                "source_label": G.nodes[u].get("label") or u,
                "target_label": G.nodes[v].get("label") or v,
                "relation": ed.get("relation") or "",
                "confidence": ed.get("confidence") or "",
            }
        )

    # Group nodes by source file for excerpt extraction
    by_file: dict[str, list[dict[str, Any]]] = {}
    for n in nodes_out:
        src = str(n.get("source_file") or "").strip()
        if not src:
            continue
        by_file.setdefault(src, []).append(n)

    sources_out: list[dict[str, Any]] = []
    total_chars = 0
    for src, file_nodes in sorted(
        by_file.items(),
        key=lambda kv: -max(relevance(n["id"]) for n in kv[1]),
    ):
        if len(sources_out) >= _MAX_SOURCES or total_chars >= _MAX_TOTAL_EXCERPT_CHARS:
            break
        pages: set[int] = set()
        # Only top-relevance nodes drive page scoping — BFS neighbors from
        # other pages must not re-open the whole PDF into excerpt ranking.
        for n in file_nodes[:5]:
            pages |= _parse_pages_from_location(
                str(n.get("source_location") or "")
            )
        readable_path, text, err = _read_readable_source(
            Path(src),
            roots,
            pages=pages or None,
            terms=terms,
        )
        display_name = Path(src).name
        if readable_path is None or not text:
            sources_out.append(
                {
                    "path": src,
                    "name": display_name,
                    "readable": False,
                    "matched_labels": [n["label"] for n in file_nodes[:8]],
                    "excerpts": [],
                    "error": err or "source file not readable or outside allowed roots",
                }
            )
            continue

        loc = next(
            (
                str(n.get("source_location"))
                for n in file_nodes
                if n.get("source_location") not in (None, "", "None")
            ),
            None,
        )
        # Prefer the highest-relevance location that contributed page numbers.
        if pages:
            for n in file_nodes:
                cand = str(n.get("source_location") or "")
                if _parse_pages_from_location(cand) & pages:
                    loc = cand
                    break
        top_labels = [str(n["label"]) for n in file_nodes[:_MAX_LABELS_FOR_EXCERPT]]
        excerpts = _extract_excerpts(
            text,
            terms=terms,
            labels=top_labels,
            source_location=loc,
        )
        # Trim to remaining budget
        kept: list[str] = []
        for ex in excerpts:
            if total_chars + len(ex) > _MAX_TOTAL_EXCERPT_CHARS:
                remain = _MAX_TOTAL_EXCERPT_CHARS - total_chars
                if remain >= 80:
                    kept.append(ex[: remain - 1] + "…")
                    total_chars += remain
                break
            kept.append(ex)
            total_chars += len(ex)

        sources_out.append(
            {
                "path": str(readable_path),
                "name": readable_path.name if readable_path.suffix.lower() in {".md", ".markdown", ".txt"} else display_name,
                "readable": True,
                "matched_labels": [n["label"] for n in file_nodes[:8]],
                "excerpts": kept,
            }
        )

    # Soft token budget on node/edge listing (for parity with graphify CLI)
    char_budget = budget * 4
    approx = json.dumps(
        {"nodes": nodes_out, "edges": edges_out},
        ensure_ascii=False,
    )
    truncated = False
    if len(approx) > char_budget:
        # Keep highest-relevance nodes first
        keep_n = max(8, min(len(nodes_out), char_budget // 120))
        keep_ids = {n["id"] for n in nodes_out[:keep_n]}
        nodes_out = nodes_out[:keep_n]
        edges_out = [
            e
            for e in edges_out
            if e["source"] in keep_ids and e["target"] in keep_ids
        ]
        truncated = True

    return {
        "question": question,
        "mode": mode,
        "match_via": match_via,
        "start_nodes": [
            {"id": nid, "label": G.nodes[nid].get("label") or nid}
            for nid in start_nodes
        ],
        "nodes": nodes_out,
        "edges": edges_out,
        "sources": sources_out,
        "truncated": truncated,
        "message": None,
    }
