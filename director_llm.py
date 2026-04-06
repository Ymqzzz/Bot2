from __future__ import annotations


def normalize_quota_mode(mode: str) -> str:
    """Normalize user-selected analysis depth/profile modes.

    The director accepts a small canonical set of modes but should also handle
    natural-language requests from operators (for example "excessive analysis"
    or "extreme technical analysis").
    """

    normalized = str(mode or "").strip().lower().replace("-", "_").replace(" ", "_")

    aliases = {
        "excessive_analysis": "extreme_technical",
        "extreme_technical_analysis": "extreme_technical",
        "extreme_technical": "extreme_technical",
        "technical_deep_dive": "extreme_technical",
        "commodity_focus": "commodity_technical",
        "commodity_technical_analysis": "commodity_technical",
        "market_and_commodity_extreme": "commodity_technical",
    }

    normalized = aliases.get(normalized, normalized)

    if normalized in {
        "normal",
        "expand_breadth",
        "scalp_mode",
        "extreme_technical",
        "commodity_technical",
    }:
        return normalized
    return "normal"
