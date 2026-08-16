#!/usr/bin/env python3
"""Full standalone pipeline: tasks.db → corpus → LLM extract → out/graph.html.

Does NOT use the Cursor /graphify skill. Requires LiteLLM gateway credentials.

When --user is set, corpus / graphify-out / out are written under
{SESSION_STORAGE_DIR}/{user}/graph/ (same root as artifacts & skills).

Default for --user is incremental: delta corpus sync + extract-from-queue.
Pass --full to rebuild the corpus and re-extract uncached turns.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(HERE), env=env)


def _corpus_md_count(corpus: Path) -> int:
    if not corpus.is_dir():
        return 0
    # Match semantic.extract_corpus: skip converted/.pdf_pages intermediates.
    root = corpus.resolve()
    count = 0
    for p in corpus.rglob("*.md"):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        try:
            if ".pdf_pages" in p.resolve().relative_to(root).parts:
                continue
        except ValueError:
            continue
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_pipeline.py\n"
            "  python run_pipeline.py --user ksdyb --limit 10\n"
            "  python run_pipeline.py --user ksdyb --full\n"
            "  python run_pipeline.py --skip-export   # reuse corpus/\n"
            "  python run_pipeline.py --skip-extract  # reuse graphify-out/graph.json\n"
        ),
    )
    parser.add_argument("--user", default=None, help="Filter export by user_id")
    parser.add_argument("--limit", type=int, default=None, help="Max turns on export")
    parser.add_argument("--per-user", action="store_true", help="corpus/{user}/ layout")
    parser.add_argument("--deep", action="store_true", help="Deep semantic extraction")
    parser.add_argument("--model", default=None, help="Override GRAPHIFY_LLM_MODEL")
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--file-limit", type=int, default=None, help="Max .md files to extract")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full corpus rebuild + extract uncached (ignore incremental queue-only path)",
    )
    parser.add_argument(
        "--no-session-storage",
        action="store_true",
        help="Keep outputs under graph/corpus|graphify-out|out instead of session storage",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    out_hint = "out/graph.html"
    incremental = bool(args.user) and not args.full and not args.per_user

    if args.user and not args.no_session_storage:
        from lib.config import configure_user_session_dirs, graphify_out_dir, resolve_tasks_db_for_user

        paths = configure_user_session_dirs(args.user)
        # Child processes must see the redirected dirs (graphify-out ≡ out).
        env["CORPUS_DIR"] = str(paths["corpus"])
        env["GRAPHIFY_OUT_DIR"] = str(paths["out"])
        env["OUT_DIR"] = str(paths["out"])
        if "TASKS_DB_PATH" not in env:
            env["TASKS_DB_PATH"] = str(resolve_tasks_db_for_user(args.user))
        print(f"Session graph workspace: {paths['root']}")
        print(f"  corpus → {paths['corpus']}")
        print(f"  out    → {paths['out']}  (extract + publish)")
        print(f"  db     → {env['TASKS_DB_PATH']}")
        if incremental:
            print("  mode   → incremental (delta export + extract queue)")
        elif args.full:
            print("  mode   → full rebuild")
        out_hint = str(paths["out"] / "graph.html")
    else:
        from lib.config import graphify_out_dir

    py = sys.executable

    if not args.skip_export:
        cmd = [py, "export_corpus.py"]
        if args.user:
            cmd += ["--user", args.user]
        if args.limit is not None:
            cmd += ["--limit", str(args.limit)]
        if args.per_user:
            cmd.append("--per-user")
        if args.full:
            cmd.append("--full")
        elif incremental:
            cmd.append("--delta")
        _run(cmd, env=env)

    from lib.config import corpus_dir

    corpus_path = Path(env.get("CORPUS_DIR", str(corpus_dir()))).expanduser().resolve()
    if _corpus_md_count(corpus_path) == 0:
        print(
            f"No corpus markdown under {corpus_path}; "
            "skip extract/publish (no chat turns for this user yet)."
        )
        print()
        print("Done (empty corpus). Graph will appear after chat turns exist.")
        return

    if not args.skip_extract:
        cmd = [py, "run_extract.py", "--chunk-size", str(args.chunk_size)]
        if incremental and not args.full:
            cmd.append("--from-queue")
        if args.deep:
            cmd.append("--deep")
        if args.model:
            cmd += ["--model", args.model]
        if args.file_limit is not None and not (incremental and not args.full):
            cmd += ["--limit", str(args.file_limit)]
        _run(cmd, env=env)

    if not args.skip_publish:
        # Prefer env-configured graphify-out (session storage when --user).
        graph = Path(env.get("GRAPHIFY_OUT_DIR", str(graphify_out_dir()))) / "graph.json"
        if not graph.is_file():
            graph = graphify_out_dir() / "graph.json"
        cmd = [py, "publish_out.py", "--graph", str(graph)]
        if args.user:
            cmd += ["--user", args.user]
            from lib.patterns import resolve_graph_pattern

            env["GRAPH_PATTERN"] = resolve_graph_pattern(user_id=args.user)
            cmd += ["--pattern", env["GRAPH_PATTERN"]]
        _run(cmd, env=env)

    print()
    print(f"Done. Open e.g.: open {out_hint}")


if __name__ == "__main__":
    main()
