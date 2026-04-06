from director_llm import normalize_quota_mode


def test_preserves_existing_modes() -> None:
    assert normalize_quota_mode("normal") == "normal"
    assert normalize_quota_mode("expand_breadth") == "expand_breadth"
    assert normalize_quota_mode("scalp_mode") == "scalp_mode"


def test_maps_excessive_and_extreme_analysis_requests() -> None:
    assert normalize_quota_mode("excessive analysis") == "extreme_technical"
    assert normalize_quota_mode("extreme technical analysis") == "extreme_technical"
    assert normalize_quota_mode("technical-deep-dive") == "extreme_technical"


def test_maps_commodity_technical_requests() -> None:
    assert normalize_quota_mode("commodity focus") == "commodity_technical"
    assert normalize_quota_mode("commodity technical analysis") == "commodity_technical"


def test_falls_back_to_normal_for_unknown_mode() -> None:
    assert normalize_quota_mode("unsupported") == "normal"
