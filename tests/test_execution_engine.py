import unittest

from execution_engine import choose_entry_type, clip_staging_plan


class ExecutionEngineTests(unittest.TestCase):
    def test_choose_entry_type_prefers_stop_for_liquid_breakout(self):
        self.assertEqual(choose_entry_type("trend_breakout", 0.5, 0.7, 25.0), "STOP")

    def test_choose_entry_type_prefers_limit_when_spread_is_wide(self):
        self.assertEqual(choose_entry_type("mean_reversion", 0.1, 0.8, 85.0), "LIMIT")


    def test_choose_entry_type_uses_depth_and_spread_shock(self):
        self.assertEqual(
            choose_entry_type("squeeze_breakout", 0.8, 0.8, 45.0, velocity=0.9, depth_pressure=0.7),
            "STOP",
        )
        self.assertEqual(
            choose_entry_type("squeeze_breakout", 0.8, 0.8, 70.0, velocity=0.9, depth_pressure=0.7, spread_shock=True),
            "LIMIT",
        )

    def test_clip_staging_plan_balances_positive_units(self):
        self.assertEqual(clip_staging_plan(10, liquidity_factor=0.9, has_near_event=False), [3, 3, 2, 2])

    def test_clip_staging_plan_balances_negative_units(self):
        self.assertEqual(clip_staging_plan(-10, liquidity_factor=0.9, has_near_event=False), [-3, -3, -2, -2])

    def test_clip_staging_plan_avoids_staging_under_risk_conditions(self):
        self.assertEqual(clip_staging_plan(10, liquidity_factor=0.55, has_near_event=False), [10])
        self.assertEqual(clip_staging_plan(10, liquidity_factor=0.9, has_near_event=True), [10])


if __name__ == "__main__":
    unittest.main()
