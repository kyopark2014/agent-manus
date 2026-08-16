#!/usr/bin/env python3
"""Publish per-user graphs into out/graph.html (rich UI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.config import graphify_out_dir, out_dir
from lib.out_graphs import collect_from_graphify_out, publish_user_graphs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python publish_out.py\n"
            "  python publish_out.py --user ksdyb\n"
            "  open out/graph.html\n"
        ),
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=None,
        help="Source graph.json (default: graphify-out/graph.json)",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output dir (default: out/)")
    parser.add_argument("--user", default=None)
    parser.add_argument(
        "--pattern",
        default=None,
        help="HTML pattern: pattern1|pattern2|pattern3 (default: user settings / pattern1)",
    )
    parser.add_argument("--min-nodes", type=int, default=1)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument(
        "--republish",
        action="store_true",
        help="Re-render graph.html from existing out/graph.json (no extract)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=None,
        help="With --collect: graphify-out directory",
    )
    args = parser.parse_args()

    dest = (args.out or out_dir()).expanduser().resolve()
    default_src = graphify_out_dir()

    if args.republish:
        from lib.out_graphs import republish_html_from_json

        path = republish_html_from_json(
            dest, user_id=args.user, pattern=args.pattern
        )
        if path is None:
            raise SystemExit(f"No graph.json under {dest}")
        print(f"Republished → {path}")
        return

    if args.collect:
        if not args.user:
            raise SystemExit("--collect requires --user")
        src = (args.src or default_src).expanduser().resolve()
        written = collect_from_graphify_out(src, dest, user=args.user)
        if not written:
            raise SystemExit(f"No artifacts in {src}")
        print(f"Collected into {dest}")
        for name, path in written.items():
            print(f"  {name} → {path.name}")
        print(f"Open: open {dest / 'graph.html'}")
        return

    graph = (args.graph or (default_src / "graph.json")).expanduser().resolve()
    if not graph.is_file():
        raise SystemExit(
            f"graph.json not found: {graph}\n"
            "Run: python run_extract.py   # or python run_pipeline.py"
        )

    results = publish_user_graphs(
        graph,
        dest,
        user=args.user,
        min_nodes=args.min_nodes,
        pattern=args.pattern,
    )
    if not results:
        raise SystemExit("No user subgraphs written")

    print(f"Published {len(results)} user graph(s) → {dest}")
    for r in results:
        print(
            f"  - {r['user_id']}: {r['nodes']} nodes, {r['edges']} edges → {Path(r['html']).name}"
        )
    print(f"Open e.g.: open {results[0]['html']}")


if __name__ == "__main__":
    main()
