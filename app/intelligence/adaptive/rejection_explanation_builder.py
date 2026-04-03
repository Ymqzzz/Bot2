from __future__ import annotations


class RejectionExplanationBuilder:
    def explain(self, *, blocked: bool, veto_sources: list[str], penalties: dict[str, float]) -> str:
        if blocked:
            return f"Rejected due to vetoes from {', '.join(veto_sources) or 'unknown'}"
        major = sorted(penalties.items(), key=lambda item: item[1], reverse=True)
        if major and major[0][1] > 0.5:
            return f"Rejected due to high penalty: {major[0][0]}"
        return "Rejected due to aggregate confidence compression"
