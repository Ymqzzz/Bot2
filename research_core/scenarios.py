from __future__ import annotations

from research_core.models import ScenarioDefinition


def _make(scenario_id: str, name: str, description: str, parameter_overrides: dict[str, object] | None = None,
          feature_toggles: dict[str, bool] | None = None, policy_overrides: dict[str, object] | None = None,
          notes: str | None = None) -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id=scenario_id,
        name=name,
        description=description,
        parameter_overrides=parameter_overrides or {},
        feature_toggles=feature_toggles or {},
        policy_overrides=policy_overrides or {},
        notes=notes,
    )


def build_threshold_scenario(scenario_id: str, overrides: dict[str, object], notes: str | None = None) -> ScenarioDefinition:
    return _make(scenario_id, "threshold_change", "Threshold change scenario", parameter_overrides=overrides, notes=notes)


def build_policy_scenario(scenario_id: str, overrides: dict[str, object], notes: str | None = None) -> ScenarioDefinition:
    return _make(scenario_id, "policy_change", "Policy change scenario", policy_overrides=overrides, notes=notes)


def build_feature_toggle_scenario(scenario_id: str, toggles: dict[str, bool], notes: str | None = None) -> ScenarioDefinition:
    return _make(scenario_id, "feature_toggle", "Feature toggle scenario", feature_toggles=toggles, notes=notes)


def build_meta_scenario(scenario_id: str, overrides: dict[str, object], notes: str | None = None) -> ScenarioDefinition:
    return _make(scenario_id, "meta_approval_change", "Meta approval scenario", policy_overrides=overrides, notes=notes)
