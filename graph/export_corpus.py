#!/usr/bin/env python3
"""Export agent-skills tasks.db turns to markdown corpus (no LLM).

Default for a single --user is incremental (delta): only create/update changed
turn files and enqueue cache misses into ``out/.extract_queue.json``.
Use --full to rebuild the corpus and re-queue everything that is not cached.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from lib.config import corpus_dir, graphify_out_dir, tasks_db_path
from lib.corpus import export_turns, safe_slug, stable_turn_filename, sync_corpus_turns
from lib.extract_queue import clear_queue, enqueue
from lib.tasks_db import build_turns, snapshot_db


def _enqueue_uncached(artifact_dir: Path, items: list[dict]) -> int:
    """Enqueue only items whose graphify content-hash cache misses."""
    if not items:
        return 0
    try:
        from graphify.cache import load_cached
    except ImportError:
        return enqueue(artifact_dir, items)

    # Flat cache dir under artifact/cache (same monkeypatch as semantic.py).
    import graphify.cache as gc

    _orig = gc.cache_dir

    def _flat_cache_dir(
        root: Path = Path("."),
        kind: str | None = None,
        prompt_fp: str | None = None,
    ) -> Path:
        base = Path(root).resolve() / "cache"
        d = base
        if kind:
            d = base / str(kind)
            if kind == "ast":
                ver = getattr(gc, "_EXTRACTOR_VERSION", None)
                if ver:
                    d = d / f"v{ver}"
            elif prompt_fp:
                d = d / f"p{prompt_fp}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    gc.cache_dir = _flat_cache_dir  # type: ignore[assignment]
    try:
        misses: list[dict] = []
        for item in items:
            path = Path(item["corpus_path"])
            if load_cached(path, artifact_dir) is None:
                misses.append(item)
        return enqueue(artifact_dir, misses)
    finally:
        gc.cache_dir = _orig  # type: ignore[assignment]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Examples:\n"
            "  python export_corpus.py                       # all users\n"
            "  python export_corpus.py --per-user            # corpus/{user}/\n"
            "  python export_corpus.py --user ksdyb          # delta for one user\n"
            "  python export_corpus.py --user ksdyb --full   # rebuild corpus\n"
            "  python export_corpus.py --user ksdyb --limit 20\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", type=Path, default=None, help="Path to tasks.db")
    parser.add_argument("--out", type=Path, default=None, help="Corpus output directory")
    parser.add_argument(
        "--user",
        default=None,
        help="Filter by user_id (omit to export all users)",
    )
    parser.add_argument(
        "--per-user",
        action="store_true",
        help="Write each user into corpus/{user}/",
    )
    parser.add_argument("--task-limit", type=int, default=None, help="Max tasks")
    parser.add_argument("--limit", type=int, default=None, help="Max turns")
    parser.add_argument("--prompt-max", type=int, default=2000, help="Max user chars")
    parser.add_argument("--reply-max", type=int, default=3000, help="Max assistant chars")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete existing turn-*.md before writing (legacy full export)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full corpus rebuild (clean stale files) and re-queue uncached turns",
    )
    parser.add_argument(
        "--delta",
        action="store_true",
        help="Incremental sync (default when --user is set)",
    )
    parser.add_argument(
        "--no-queue",
        action="store_true",
        help="Do not write .extract_queue.json",
    )
    args = parser.parse_args()

    db = (args.db or tasks_db_path()).expanduser().resolve()
    out = (args.out or corpus_dir()).expanduser().resolve()
    artifact = graphify_out_dir().expanduser().resolve()

    # Single-user default is delta; multi-user / per-user keep classic full write.
    use_delta = bool(args.user) and not args.full and not args.per_user
    if args.delta:
        use_delta = True
    if args.full:
        use_delta = False

    # Read a consistent backup so concurrent chat writes cannot tear the export.
    with snapshot_db(db) as snap:
        turns = build_turns(
            snap,
            user_id=args.user,
            task_limit=args.task_limit,
            turn_limit=args.limit,
        )

        if args.per_user:
            by_user: dict[str, list] = defaultdict(list)
            for turn in turns:
                by_user[turn.task.user_id].append(turn)
            total = 0
            print(f"Exporting {len(by_user)} user corpus folder(s) under {out}")
            for user_id, user_turns in sorted(
                by_user.items(), key=lambda x: (-len(x[1]), x[0])
            ):
                user_dir = out / safe_slug(user_id)
                paths = export_turns(
                    user_turns,
                    user_dir,
                    prompt_max=args.prompt_max,
                    reply_max=args.reply_max,
                    clean=not args.no_clean,
                )
                total += len(paths)
                print(f"  - {user_id}: {len(paths)} → {user_dir}")
            print(f"Exported {total} turn(s) from {db}")
            print()
            print("Next: python run_extract.py   # or python run_pipeline.py")
            return

        if use_delta or args.full:
            mode = "delta" if use_delta else "full"
            all_paths, changed = sync_corpus_turns(
                turns,
                out,
                prompt_max=args.prompt_max,
                reply_max=args.reply_max,
                full=args.full or not use_delta,
            )
            print(
                f"Corpus sync [{mode}]: {len(all_paths)} turn(s), "
                f"{len(changed)} created/updated → {out}"
            )
            if not args.no_queue:
                if args.full:
                    clear_queue(artifact)
                # Re-queue leftover inflight is handled at claim time; enqueue misses.
                # For full: treat every path as a candidate (cache may still hit).
                candidates = changed
                if args.full:
                    candidates = [
                        {
                            "message_id": t.user.id,
                            "task_id": t.task.id,
                            "corpus_path": str(
                                (out / stable_turn_filename(t)).resolve()
                            ),
                        }
                        for t in turns
                    ]
                added = _enqueue_uncached(artifact, candidates)
                print(f"Extract queue: enqueued {added} uncached turn(s) → {artifact}")
            by_user_counts = Counter(t.task.user_id for t in turns)
            scope = f"user={args.user}" if args.user else f"all users ({len(by_user_counts)})"
            print(f"From {db} [{scope}]")
            for uid, n in by_user_counts.most_common():
                print(f"  - {uid}: {n}")
            print()
            print("Next: python run_extract.py --from-queue && python publish_out.py")
            print("  # or: python run_pipeline.py")
            return

        paths = export_turns(
            turns,
            out,
            prompt_max=args.prompt_max,
            reply_max=args.reply_max,
            clean=not args.no_clean,
        )

        by_user_counts = Counter(t.task.user_id for t in turns)
        scope = f"user={args.user}" if args.user else f"all users ({len(by_user_counts)})"
        print(f"Exported {len(paths)} turn(s) from {db} [{scope}]")
        for uid, n in by_user_counts.most_common():
            print(f"  - {uid}: {n}")
        print(f"Corpus: {out}")
        if paths:
            print(f"Example: {paths[0].name}")
        print()
        print("Next: python run_extract.py && python publish_out.py")
        print("  # or: python run_pipeline.py")


if __name__ == "__main__":
    main()
