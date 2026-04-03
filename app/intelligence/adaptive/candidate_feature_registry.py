from __future__ import annotations


class CandidateFeatureRegistry:
    def __init__(self) -> None:
        self._features: dict[str, dict[str, float | str]] = {}

    def register(self, name: str, metadata: dict[str, float | str]) -> None:
        self._features[name] = dict(metadata)

    def list_all(self) -> dict[str, dict[str, float | str]]:
        return dict(self._features)
