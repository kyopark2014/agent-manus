"""
Chart text collection and update.

Scope: chart title, axis titles, category labels, and series names. We do
NOT touch numeric data (<c:val>, <c:numRef>) — that would silently break
the chart. Categories that look like numbers/dates/percentages are skipped.

python-pptx exposes titles and series.name as writable objects, but category
strings live in the underlying <c:cat><c:strRef><c:strCache><c:pt><c:v>…</c:v>
XML and must be replaced there.
"""
import logging
import re
from typing import Dict, List, Optional

from .text_utils import TextProcessor

logger = logging.getLogger(__name__)

# Chart XML namespaces used by DrawingML charts.
_NS_C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
_NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'

# Extra skip patterns on top of TextProcessor.should_skip_translation.
# Chart category axes often carry years, percentages, or unit values.
_EXTRA_SKIP = [
    re.compile(r'^\d{4}(-\d{1,2})?(-\d{1,2})?$'),       # 2024, 2024-01, 2024-01-15
    re.compile(r'^\d{1,2}/\d{1,2}(/\d{2,4})?$'),        # 1/15, 1/15/2024
    re.compile(r'^\d+(\.\d+)?\s*%$'),                   # 12%, 3.5%
    re.compile(r'^[-+]?\d+(\.\d+)?\s*(ms|s|m|h|d|MB|GB|KB|TB|%|°C|°F)$', re.IGNORECASE),
]


def _should_skip_chart_text(text: str) -> bool:
    """Stricter skip rule than normal text: categories are often numeric."""
    if not text or not text.strip():
        return True
    if TextProcessor.should_skip_translation(text):
        return True
    stripped = text.strip()
    for pattern in _EXTRA_SKIP:
        if pattern.match(stripped):
            return True
    return False


class ChartTextCollector:
    """Collects translatable strings from a chart shape."""

    @staticmethod
    def collect(shape, text_items: List[Dict], current_path: str) -> None:
        """Append chart text_items in place. Silent no-op for non-chart shapes."""
        if not getattr(shape, 'has_chart', False):
            return
        try:
            chart = shape.chart
        except Exception as e:
            logger.debug(f"Chart access failed: {e}")
            return

        ChartTextCollector._collect_title(chart, text_items, current_path)
        ChartTextCollector._collect_axis_titles(chart, text_items, current_path)
        ChartTextCollector._collect_series_names(chart, text_items, current_path)
        ChartTextCollector._collect_categories(chart, text_items, current_path)

    @staticmethod
    def _collect_title(chart, text_items: List[Dict], current_path: str) -> None:
        try:
            if not chart.has_title:
                return
            tf = chart.chart_title.text_frame
            text = tf.text.strip()
            if text and not _should_skip_chart_text(text):
                text_items.append({
                    'type': 'chart_title',
                    'path': f"{current_path}.chart.title",
                    'text': text,
                    'text_frame': tf,
                })
        except Exception as e:
            logger.debug(f"Chart title collect failed: {e}")

    @staticmethod
    def _collect_axis_titles(chart, text_items: List[Dict], current_path: str) -> None:
        for axis_attr, axis_name in (('category_axis', 'category'), ('value_axis', 'value')):
            try:
                axis = getattr(chart, axis_attr, None)
                if axis is None:
                    continue
                if not getattr(axis, 'has_title', False):
                    continue
                tf = axis.axis_title.text_frame
                text = tf.text.strip()
                if text and not _should_skip_chart_text(text):
                    text_items.append({
                        'type': f'chart_axis_{axis_name}_title',
                        'path': f"{current_path}.chart.{axis_name}_axis.title",
                        'text': text,
                        'text_frame': tf,
                    })
            except Exception as e:
                logger.debug(f"Chart {axis_attr} title collect failed: {e}")

    @staticmethod
    def _collect_series_names(chart, text_items: List[Dict], current_path: str) -> None:
        try:
            for s_idx, series in enumerate(chart.series):
                name = getattr(series, 'name', None)
                if not name:
                    continue
                name = str(name).strip()
                if not name or _should_skip_chart_text(name):
                    continue
                text_items.append({
                    'type': 'chart_series_name',
                    'path': f"{current_path}.chart.series.{s_idx}",
                    'text': name,
                    'chart': chart,
                    'series_idx': s_idx,
                })
        except Exception as e:
            logger.debug(f"Chart series names collect failed: {e}")

    @staticmethod
    def _collect_categories(chart, text_items: List[Dict], current_path: str) -> None:
        """Extract category labels from <c:cat><c:strRef><c:strCache><c:pt>."""
        try:
            chart_space = chart._chartSpace  # private but stable within python-pptx
        except Exception as e:
            logger.debug(f"Chart space access failed: {e}")
            return

        try:
            # Look for every <c:cat> → <c:strRef> → <c:strCache> → <c:pt>.
            # We restrict to strRef on purpose; numRef is numeric data that
            # must not be translated.
            cats = chart_space.findall(
                f'.//{{{_NS_C}}}cat/{{{_NS_C}}}strRef/{{{_NS_C}}}strCache/{{{_NS_C}}}pt'
            )
            for pt in cats:
                v = pt.find(f'{{{_NS_C}}}v')
                if v is None or not v.text:
                    continue
                text = v.text.strip()
                if not text or _should_skip_chart_text(text):
                    continue
                text_items.append({
                    'type': 'chart_category',
                    'path': f"{current_path}.chart.cat.{pt.get('idx', '?')}",
                    'text': text,
                    'xml_v_element': v,
                })
        except Exception as e:
            logger.debug(f"Chart categories collect failed: {e}")


class ChartUpdater:
    """Applies a translated string back to a chart item."""

    @staticmethod
    def apply(item: Dict, translation: str, target_language: Optional[str] = None) -> bool:
        item_type = item['type']
        try:
            if item_type in ('chart_title', 'chart_axis_category_title', 'chart_axis_value_title'):
                return ChartUpdater._apply_text_frame(item, translation, target_language)
            if item_type == 'chart_series_name':
                return ChartUpdater._apply_series_name(item, translation)
            if item_type == 'chart_category':
                return ChartUpdater._apply_category(item, translation)
        except Exception as e:
            logger.error(f"Chart update failed for {item_type}: {e}")
        return False

    @staticmethod
    def _apply_text_frame(item: Dict, translation: str, target_language: Optional[str]) -> bool:
        # Late import to avoid a circular dependency between ppt_handler and chart_handler.
        from .ppt_handler import FormattingApplier, TextFrameUpdater

        tf = item.get('text_frame')
        if tf is None:
            return False
        TextFrameUpdater.update_text_frame(tf, translation, target_language)
        FormattingApplier._apply_language_font_to_text_frame(tf, target_language)
        return True

    @staticmethod
    def _apply_series_name(item: Dict, translation: str) -> bool:
        """Rewrite the <c:tx><c:strRef><c:strCache><c:pt><c:v> of a series."""
        chart = item.get('chart')
        s_idx = item.get('series_idx')
        if chart is None or s_idx is None:
            return False
        try:
            series_list = list(chart.series)
            if s_idx >= len(series_list):
                return False
            series = series_list[s_idx]
            ser = getattr(series, '_element', None)
            if ser is None:
                return False
            # <c:ser><c:tx><c:strRef><c:strCache><c:pt><c:v>
            v = ser.find(f'{{{_NS_C}}}tx/{{{_NS_C}}}strRef/{{{_NS_C}}}strCache/{{{_NS_C}}}pt/{{{_NS_C}}}v')
            if v is not None:
                v.text = translation
                return True
            # Fallback: inline <c:tx><c:v> (rare — some older files)
            v2 = ser.find(f'{{{_NS_C}}}tx/{{{_NS_C}}}v')
            if v2 is not None:
                v2.text = translation
                return True
        except Exception as e:
            logger.debug(f"Series name update failed: {e}")
        return False

    @staticmethod
    def _apply_category(item: Dict, translation: str) -> bool:
        v = item.get('xml_v_element')
        if v is None:
            return False
        v.text = translation
        return True
