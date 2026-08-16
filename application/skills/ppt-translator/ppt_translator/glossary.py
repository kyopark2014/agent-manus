"""
Glossary loading and lookup.

A glossary is a YAML file mapping source terms (English) to translations
per target language:

    ko:
      "API": "API"              # src == tgt means keep as-is
      "Cloud": "클라우드"
    ja:
      "Cloud": "クラウド"

The glossary is injected into translation prompts and its hash is included
in the cache key, so editing the glossary automatically invalidates stale
cache entries.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)

GlossaryMap = Dict[str, Dict[str, str]]


def load_glossary(path: Union[str, Path, None]) -> GlossaryMap:
    """Load a glossary YAML file. Returns {} on missing path or parse error.

    Soft-fails on missing PyYAML: logs a warning and returns {}, so the
    translator keeps working without a glossary rather than crashing.
    """
    if not path:
        return {}
    p = Path(path).expanduser()
    if not p.exists():
        logger.warning(f"Glossary file not found: {p}")
        return {}

    try:
        import yaml
    except ImportError:
        logger.warning(
            "PyYAML is not installed; glossary feature disabled. "
            "Install with `pip install pyyaml` to enable."
        )
        return {}

    try:
        with p.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse glossary {p}: {e}")
        return {}

    if not isinstance(data, dict):
        logger.error(f"Glossary root must be a mapping, got {type(data).__name__} in {p}")
        return {}

    # Minimal validation: each language block must be a str -> str mapping.
    cleaned: GlossaryMap = {}
    for lang, terms in data.items():
        if not isinstance(terms, dict):
            logger.warning(f"Glossary section '{lang}' is not a mapping, skipping")
            continue
        cleaned[str(lang)] = {str(k): str(v) for k, v in terms.items() if v is not None}

    logger.info(f"Loaded glossary from {p}: {sum(len(v) for v in cleaned.values())} terms across {len(cleaned)} languages")
    return cleaned


def get_glossary_for_language(glossary: GlossaryMap, target_language: str) -> Dict[str, str]:
    """Return the term map for a given target language, with base-language fallback.

    Example: `zh-CN` falls back to `zh` if `zh-CN` is not defined.
    """
    if not glossary or not target_language:
        return {}
    if target_language in glossary:
        return glossary[target_language]
    base = target_language.split('-')[0]
    return glossary.get(base, {})


def hash_glossary(terms: Dict[str, str]) -> str:
    """Stable short hash of a per-language glossary. Used as part of the cache key."""
    if not terms:
        return 'none'
    s = json.dumps(terms, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:8]


def find_default_glossary() -> Optional[Path]:
    """Search known locations for a default glossary.yaml."""
    candidates = [
        Path.cwd() / 'glossary.yaml',
        Path.home() / '.ppt-translator' / 'glossary.yaml',
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
