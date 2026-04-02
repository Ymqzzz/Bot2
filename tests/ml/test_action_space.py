from app.ml.action_space import MetaAction, ensure_valid, valid_actions


def test_action_masking_restricts_invalid_actions_without_candidate():
    mask = valid_actions(has_candidate=False, in_position=False, risk_deterioration=False)
    assert mask.allowed[int(MetaAction.ALLOW_AS_IS)]
    assert not mask.allowed[int(MetaAction.VETO_TRADE)]
    assert ensure_valid(int(MetaAction.VETO_TRADE), mask) == int(MetaAction.ALLOW_AS_IS)
