from app.governance.policy_engine import policy_check
from app.risk.tail_risk import dislocation_score, realized_returns, var_es


def _bars(n=120, jump=False):
    bars = []
    px = 1.0
    for i in range(n):
        if jump and i == n - 3:
            px *= 1.02
        else:
            px += 0.0002
        bars.append({"open": px - 0.0001, "high": px + 0.0003, "low": px - 0.0003, "close": px})
    return bars


def test_var_es_and_returns():
    rs = realized_returns(_bars())
    v, e = var_es(rs, alpha=0.95)
    assert len(rs) > 50
    assert v <= 0.001
    assert e <= 0.001


def test_dislocation_and_policy_block():
    bars = _bars(jump=True)
    d = dislocation_score(bars, spread_pctile=95.0)
    ok, reason = policy_check(spread_pctile=95.0, dislocation=d, near_event=True, max_spread_pctile=85.0)
    assert d > 1.0
    assert not ok
    assert reason in {"spread_policy_block", "dislocation_policy_block", "event_dislocation_block"}
