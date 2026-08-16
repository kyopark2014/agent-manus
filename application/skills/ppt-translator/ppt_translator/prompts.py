"""
Translation prompt templates and generators
"""
from typing import Dict, Optional
from .config import Config


class PromptGenerator:
    """Generates translation prompts with consistent rules"""

    @classmethod
    def _build_terminology_rules(cls, target_language: str, glossary: Optional[Dict[str, str]] = None) -> str:
        """Build TERMINOLOGY section from an explicit glossary, or fall back to Config."""
        terminology = glossary
        if terminology is None:
            # Backwards-compat fallback: hardcoded dicts on Config.
            if target_language == 'ko':
                terminology = getattr(Config, 'KOREAN_TERMINOLOGY', None)
            elif target_language == 'ja':
                terminology = getattr(Config, 'JAPANESE_TERMINOLOGY', None)

        if not terminology:
            return ""

        rules = "\n\nTERMINOLOGY (use these exact translations):\n"
        for src, tgt in terminology.items():
            if src == tgt:
                rules += f"- \"{src}\" → keep as \"{tgt}\" (do not translate)\n"
            else:
                rules += f"- \"{src}\" → \"{tgt}\"\n"
        return rules

    @classmethod
    def _direction(cls, source_language: Optional[str], target_language: str) -> str:
        """Build a 'from X to Y' phrase when source is known, otherwise just 'to Y'."""
        target_name = Config.LANGUAGE_MAP.get(target_language, target_language)
        if source_language:
            source_name = Config.LANGUAGE_MAP.get(source_language, source_language)
            return f"from {source_name} to {target_name}"
        return f"to {target_name}"

    @classmethod
    def create_single_prompt(cls, target_language: str, enable_polishing: bool = True,
                             glossary: Optional[Dict[str, str]] = None,
                             source_language: Optional[str] = None) -> str:
        """Create prompt for single text translation"""
        direction = cls._direction(source_language, target_language)
        terminology = cls._build_terminology_rules(target_language, glossary)
        return f"""Translate {direction}.
CRITICAL: Provide ONLY the translation. No explanations, alternatives, context notes, or additional text.{terminology}"""

    @classmethod
    def create_batch_prompt(cls, target_language: str, enable_polishing: bool = True,
                            glossary: Optional[Dict[str, str]] = None,
                            source_language: Optional[str] = None) -> str:
        """Create optimized batch translation prompt"""
        direction = cls._direction(source_language, target_language)
        terminology = cls._build_terminology_rules(target_language, glossary)
        return f"""Translate each numbered text {direction}.
CRITICAL RULES:
- Provide ONLY the translation, no explanations
- No alternative translations or context notes
- No markdown formatting (**bold**, *italic*)
- No arrows (→) or additional text
- Keep the same numbered format: [1] translation [2] translation [3] translation
- Do not skip any numbers{terminology}

Example:
[1] 첫 번째 번역
[2] 두 번째 번역
[3] 세 번째 번역"""

    @classmethod
    def create_context_prompt(cls, target_language: str, slide_context: str, enable_polishing: bool = True,
                              glossary: Optional[Dict[str, str]] = None,
                              source_language: Optional[str] = None) -> str:
        """Create context-aware translation prompt"""
        direction = cls._direction(source_language, target_language)
        return f"Translate numbered texts {direction}. Format: [1] translation [2] translation:"
