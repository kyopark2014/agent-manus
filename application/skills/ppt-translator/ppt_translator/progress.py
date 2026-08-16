"""
Rich-based progress display for the CLI.

Translation work is slow and I/O-heavy — the user needs to know something's
happening, roughly how long it will take, and (with caching) how effective
the cache is. This module exposes a single Progress factory plus a callback
builder that pulls live numbers out of `TranslationMetrics`.

Gracefully degrades to a silent no-op Progress if `rich` isn't installed.
"""
import logging
from contextlib import contextmanager
from typing import Optional

from .pricing import estimate_cost

logger = logging.getLogger(__name__)


try:
    from rich.progress import (
        BarColumn,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    _HAS_RICH = True
except ImportError:  # pragma: no cover
    _HAS_RICH = False


class _NullTask:
    id = 0


class _NullProgress:
    """Fallback when rich is unavailable — prints minimal text updates."""

    def __init__(self):
        self._counters = {}

    def add_task(self, description, total=None, extra=""):
        tid = len(self._counters)
        self._counters[tid] = {'description': description, 'total': total, 'done': 0}
        print(f"[progress] {description} (0/{total})")
        return tid

    def update(self, task_id, advance=0, extra=None, **kwargs):
        state = self._counters.get(task_id)
        if state is None:
            return
        state['done'] += advance
        if advance > 0:
            print(f"[progress] {state['description']}: {state['done']}/{state['total']}"
                  + (f" — {extra}" if extra else ""))

    class _ConsoleStub:
        def log(self, *args, **kwargs):
            print(*args)

    @property
    def console(self):
        return _NullProgress._ConsoleStub()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_progress():
    """Return a Progress context manager. Use as `with make_progress() as p:`.

    The bar has a fixed width so the overall row doesn't stretch across wide
    terminals — it used to swallow the whole line when only a few tasks were
    running, pushing the cache/cost text off-screen.
    """
    if not _HAS_RICH:
        return _NullProgress()
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=20),
        TaskProgressColumn(),  # "42%"
        TextColumn("[cyan]{task.completed}/{task.total}"),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[extra]}"),
    )


def _metric(m, key: str, default: int = 0) -> int:
    """Pull a counter out of either a TranslationMetrics object or a plain dict.

    The batch listener receives events over a multiprocessing.Queue, so counters
    arrive as dicts — but single-file callers hand in the live object. Supporting
    both keeps one rendering path for the whole CLI.
    """
    if isinstance(m, dict):
        return int(m.get(key, default))
    return int(getattr(m, key, default))


def render_metrics_line(metrics, model_id: str) -> str:
    """One-line summary of cache/token/cost state. Safe to call anytime."""
    hits = _metric(metrics, 'cache_hits')
    misses = _metric(metrics, 'cache_misses')
    tin = _metric(metrics, 'tokens_in')
    tout = _metric(metrics, 'tokens_out')
    total = hits + misses
    cache_str = f"cache={hits}/{total}" if total else "cache=—"
    cost = estimate_cost(tin, tout, model_id)
    cost_str = f"${cost:.4f}" if cost > 0 else "$—"
    return f"{cache_str}  tokens={tin}+{tout}  {cost_str}"


def make_slide_progress_callback(progress, task_id, metrics, model_id: str):
    """Build a per-slide callback that updates the progress bar."""
    def _callback(slide_idx: int, _metrics=metrics):
        extra = render_metrics_line(_metrics, model_id)
        progress.update(task_id, advance=1, extra=extra)
    return _callback
