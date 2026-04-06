from ui_dashboard import _bar_chart_svg, _line_chart_svg, _monte_carlo_svg, _simulate_monte_carlo


def test_chart_helpers_render_svg_markup() -> None:
    bar_svg = _bar_chart_svg(["A", "B", "C"], [12.0, 7.5, 3.1])
    line_svg = _line_chart_svg(["x1", "x2", "x3"], [4.0, 6.0, 5.0])

    assert "<svg" in bar_svg
    assert "bar chart" in bar_svg.lower()
    assert "<svg" in line_svg
    assert "line chart" in line_svg.lower()


def test_monte_carlo_helpers_are_sorted_and_visualizable() -> None:
    samples = _simulate_monte_carlo(base_value=100.0, dispersion=0.03, trials=120, steps=10)

    assert len(samples) == 120
    assert samples == sorted(samples)
    histogram_svg = _monte_carlo_svg(samples)
    assert "<svg" in histogram_svg
    assert "P95" in histogram_svg
