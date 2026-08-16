#!/usr/bin/env python3
"""Extract knowledge graph from corpus/ via LiteLLM or Bedrock.

Uses OpenAI-compatible LiteLLM gateway when configured; otherwise AWS
Bedrock Converse (boto3 credential chain).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.build_graph import build_and_export
from lib.config import corpus_dir, graphify_out_dir
from lib.semantic import extract_corpus, extract_from_queue


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_extract.py\n"
            "  python run_extract.py --from-queue\n"
            "  python run_extract.py --corpus corpus --deep\n"
            "  python run_extract.py --limit 5   # smoke test\n"
        ),
    )
    parser.add_argument("--corpus", type=Path, default=None, help="Corpus directory")
    parser.add_argument(
        "--work",
        type=Path,
        default=None,
        help="Artifact dir for graph.json/cache (default: GRAPHIFY_OUT_DIR)",
    )
    parser.add_argument("--model", default=None, help="Override GRAPHIFY_LLM_MODEL")
    parser.add_argument("--chunk-size", type=int, default=8, help="Files per LLM call")
    parser.add_argument("--limit", type=int, default=None, help="Max corpus files")
    parser.add_argument("--deep", action="store_true", help="Aggressive INFERRED edges")
    parser.add_argument(
        "--from-queue",
        action="store_true",
        help="Only extract files listed in out/.extract_queue.json (incremental)",
    )
    args = parser.parse_args()

    corpus = (args.corpus or corpus_dir()).expanduser().resolve()
    # Prefer GRAPHIFY_OUT_DIR (session out/ when --user pipeline configured it).
    artifact = (args.work or graphify_out_dir()).expanduser().resolve()

    if args.from_queue:
        extraction = extract_from_queue(
            corpus,
            artifact,
            deep=args.deep,
            chunk_size=args.chunk_size,
            model=args.model,
        )
    else:
        extraction = extract_corpus(
            corpus,
            artifact,
            deep=args.deep,
            chunk_size=args.chunk_size,
            limit=args.limit,
            model=args.model,
        )
    graph_json = build_and_export(extraction, artifact, corpus_label=str(corpus))
    print()
    print("Next:")
    print("  python publish_out.py")
    print(f"  # or: python publish_out.py --graph {graph_json}")


if __name__ == "__main__":
    main()
