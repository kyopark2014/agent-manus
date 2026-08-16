"""
Rough token and cost estimation for dry-run reports.

These are approximations — actual Bedrock usage depends on tokenizer specifics,
prompt overhead, and output length. Enough to give the user a ballpark before
they spend money, not a quote.

Pricing table is kept small on purpose: we list the models we see most often
and show "pricing unavailable" for everything else rather than guessing.
Update as AWS pricing changes.
"""
from typing import Dict, Tuple

# (input $/1M tokens, output $/1M tokens)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # Anthropic Claude (Bedrock, US prices as of 2025)
    'us.anthropic.claude-3-7-sonnet-20250219-v1:0': (3.00, 15.00),
    'us.anthropic.claude-3-5-sonnet-20241022-v2:0': (3.00, 15.00),
    'us.anthropic.claude-3-5-sonnet-20240620-v1:0': (3.00, 15.00),
    'us.anthropic.claude-3-5-haiku-20241022-v1:0': (0.80, 4.00),
    'us.anthropic.claude-3-haiku-20240307-v1:0': (0.25, 1.25),
    'us.anthropic.claude-3-opus-20240229-v1:0': (15.00, 75.00),
    'us.anthropic.claude-sonnet-4-20250514-v1:0': (3.00, 15.00),
    'us.anthropic.claude-opus-4-20250514-v1:0': (15.00, 75.00),
    # Global inference profiles (cross-region)
    'global.anthropic.claude-sonnet-4-5-20250929-v1:0': (3.00, 15.00),
    'global.anthropic.claude-opus-4-5-20251101-v1:0': (15.00, 75.00),
    'global.anthropic.claude-haiku-4-5-20251001-v1:0': (1.00, 5.00),
    # Claude 4.6 / 4.7 (prices follow published Anthropic tier pricing;
    # verify on aws.amazon.com/bedrock/pricing before using as authoritative)
    'anthropic.claude-sonnet-4-6': (3.00, 15.00),
    'us.anthropic.claude-sonnet-4-6': (3.00, 15.00),
    'eu.anthropic.claude-sonnet-4-6': (3.00, 15.00),
    'au.anthropic.claude-sonnet-4-6': (3.00, 15.00),
    'global.anthropic.claude-sonnet-4-6': (3.00, 15.00),
    'anthropic.claude-opus-4-6-v1': (15.00, 75.00),
    'us.anthropic.claude-opus-4-6-v1': (15.00, 75.00),
    'eu.anthropic.claude-opus-4-6-v1': (15.00, 75.00),
    'au.anthropic.claude-opus-4-6-v1': (15.00, 75.00),
    'global.anthropic.claude-opus-4-6-v1': (15.00, 75.00),
    'anthropic.claude-opus-4-7': (15.00, 75.00),
    'us.anthropic.claude-opus-4-7': (15.00, 75.00),
    'eu.anthropic.claude-opus-4-7': (15.00, 75.00),
    'jp.anthropic.claude-opus-4-7': (15.00, 75.00),
    'global.anthropic.claude-opus-4-7': (15.00, 75.00),
    # Amazon Nova
    'us.amazon.nova-micro-v1:0': (0.035, 0.14),
    'us.amazon.nova-lite-v1:0': (0.06, 0.24),
    'us.amazon.nova-pro-v1:0': (0.80, 3.20),
    'us.amazon.nova-premier-v1:0': (2.50, 12.50),
    # Meta Llama 4
    'us.meta.llama4-scout-17b-instruct-v1:0': (0.17, 0.66),
    'us.meta.llama4-maverick-17b-instruct-v1:0': (0.24, 0.97),
}


# Rough chars-per-token by language family. CJK scripts pack fewer chars per
# token than Latin scripts, so we use a lower divisor to stay conservative.
_CHARS_PER_TOKEN = {
    'en': 4.0, 'fr': 4.0, 'de': 4.0, 'es': 4.0, 'it': 4.0, 'pt': 4.0,
    'ru': 3.5, 'ar': 3.0,
    'ko': 1.5, 'ja': 1.5, 'zh': 1.5,
}


def estimate_tokens(total_chars: int, lang: str = 'en') -> int:
    """Rough char-count → token-count estimate for the given language."""
    if total_chars <= 0:
        return 0
    base = lang.split('-')[0].lower() if lang else 'en'
    divisor = _CHARS_PER_TOKEN.get(base, 4.0)
    return max(1, int(total_chars / divisor))


def estimate_cost(input_tokens: int, output_tokens: int, model_id: str) -> float:
    """Estimated USD cost for a translation run. Returns 0.0 for unknown models."""
    pricing = MODEL_PRICING.get(model_id)
    if pricing is None:
        return 0.0
    p_in, p_out = pricing
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000
