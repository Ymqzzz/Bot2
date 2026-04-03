from __future__ import annotations


class FillQualityArchive:
    def summarize(self, records: list[dict]) -> dict[str, float]:
        if not records:
            return {
                "passive_fill_quality": 0.5,
                "aggressive_fill_quality": 0.5,
                "expected_slippage_bps": 2.0,
                "cancel_success_rate": 0.7,
            }
        n = len(records)
        return {
            "passive_fill_quality": sum(float(r.get("passive_quality", 0.5)) for r in records) / n,
            "aggressive_fill_quality": sum(float(r.get("aggressive_quality", 0.5)) for r in records) / n,
            "expected_slippage_bps": sum(float(r.get("slippage_bps", 2.0)) for r in records) / n,
            "cancel_success_rate": sum(float(r.get("cancel_success", 0.7)) for r in records) / n,
        }
