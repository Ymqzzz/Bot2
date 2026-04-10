from __future__ import annotations


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


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

    # Lightweight intent extraction so free-form prompts still map to
    # deterministic operating modes.
    if normalized not in aliases:
        tokens = set(part for part in normalized.split("_") if part)

        if _contains_any(normalized, {"scalp", "quick", "fast"}) and _contains_any(
            normalized, {"mode", "trading", "entries"}
        ):
            normalized = "scalp_mode"
        elif _contains_any(normalized, {"breadth", "broad", "multi_asset", "cross_asset"}) and _contains_any(
            normalized, {"expand", "wider", "scan", "coverage"}
        ):
            normalized = "expand_breadth"
        elif {"commodity", "oil", "gold", "metals", "energy"} & tokens and _contains_any(
            normalized, {"technical", "focus", "analysis", "signals"}
        ):
            normalized = "commodity_technical"
        elif _contains_any(normalized, {"ai_like", "intelligent", "smart", "reasoning"}) or (
            _contains_any(normalized, {"extreme", "deep", "advanced", "high"})
            and _contains_any(normalized, {"technical", "analysis", "detail"})
        ):
            normalized = "extreme_technical"

    if normalized in {
        "normal",
        "expand_breadth",
        "scalp_mode",
        "extreme_technical",
        "commodity_technical",
    }:
        return normalized
    return "normal"
