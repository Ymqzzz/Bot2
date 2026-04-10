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
    assert normalize_quota_mode("gold signals technical") == "commodity_technical"


def test_maps_free_form_ai_like_requests_to_extreme_mode() -> None:
    assert normalize_quota_mode("make it more ai-like") == "extreme_technical"
    assert normalize_quota_mode("advanced technical detail") == "extreme_technical"


def test_maps_free_form_speed_and_breadth_requests() -> None:
    assert normalize_quota_mode("fast trading entries mode") == "scalp_mode"
    assert normalize_quota_mode("wider cross asset coverage") == "expand_breadth"


def test_falls_back_to_normal_for_unknown_mode() -> None:
    assert normalize_quota_mode("unsupported") == "normal"
