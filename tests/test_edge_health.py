from edge_health import EdgeHealthMonitor


def test_metrics_include_recent_and_drawdown_fields():
    monitor = EdgeHealthMonitor()
    for r in [0.5, -1.0, 0.7, -0.2, 0.3]:
        monitor.update("s1", r)

    m = monitor.metrics("s1")
    assert m["trade_count"] == 5
    assert "expectancy_recent" in m
    assert "win_rate_recent" in m
    assert "max_drawdown" in m


def test_edge_decay_detects_recent_breakdown_after_enough_trades():
    monitor = EdgeHealthMonitor()
    # Healthy start
    for _ in range(20):
        monitor.update("s2", 0.4)
    # Then sustained weakness and drawdown
    for _ in range(25):
        monitor.update("s2", -0.7)

    decayed, diag = monitor.edge_decayed("s2", min_trades=20)
    assert decayed is True
    assert diag["trade_count"] == 45


def test_edge_decay_requires_minimum_trade_count():
    monitor = EdgeHealthMonitor()
    for _ in range(10):
        monitor.update("s3", -1.0)

    decayed, diag = monitor.edge_decayed("s3", min_trades=20)
    assert decayed is False
    assert diag["reason"] == "insufficient_trades"
