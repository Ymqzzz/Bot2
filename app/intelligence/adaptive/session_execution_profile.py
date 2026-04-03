from __future__ import annotations


class SessionExecutionProfile:
    def profile(self, session: str) -> dict[str, float]:
        presets = {
            "asia": {"passive_bias": 0.75, "aggressive_bias": 0.4},
            "london": {"passive_bias": 0.6, "aggressive_bias": 0.65},
            "new_york": {"passive_bias": 0.5, "aggressive_bias": 0.72},
        }
        return presets.get(session.lower(), {"passive_bias": 0.55, "aggressive_bias": 0.55})
