from __future__ import annotations

import pytest

from app.feature_registry import (
    FEATURE_REGISTRY_SCHEMA,
    FeatureDefinition,
    FeatureMaturity,
    evaluate_feature_activation,
    feature_registry,
    feature_registry_fingerprint,
    registry_payload,
    validate_feature_registry,
)


def test_registry_is_valid_versioned_unique_and_fingerprinted() -> None:
    validate_feature_registry()
    payload = registry_payload()
    assert payload["schema"] == FEATURE_REGISTRY_SCHEMA
    assert len(payload["sha256"]) == 64
    assert payload["sha256"] == feature_registry_fingerprint()
    assert payload["sha256"] == feature_registry_fingerprint(feature_registry())
    features = payload["features"]
    ids = [item["id"] for item in features]
    assert len(ids) == len(set(ids))
    assert "native_cross_process_hot_swap" in ids
    assert "trace_workload_drafting" in ids
    trace_drafting = next(item for item in features if item["id"] == "trace_workload_drafting")
    assert trace_drafting["maturity"] == "research"
    assert trace_drafting["default_enabled"] is True
    assert trace_drafting["automatic_control_allowed"] is False
    assert trace_drafting["dependencies"] == ["trace_distribution_classifier"]
    ai_provider = next(item for item in features if item["id"] == "optional_ai_language_provider")
    ai_drafting = next(item for item in features if item["id"] == "ai_workload_drafting")
    assert ai_provider["maturity"] == "guarded"
    assert ai_provider["automatic_control_allowed"] is False
    assert ai_drafting["maturity"] == "guarded"
    assert ai_drafting["automatic_control_allowed"] is False
    assert "optional_ai_language_provider" in ai_drafting["dependencies"]
    doctor = next(item for item in features if item["id"] == "hot_path_doctor")
    assert doctor["maturity"] == "guarded"
    assert doctor["default_enabled"] is True
    assert doctor["automatic_control_allowed"] is False
    assert "generated_candidate_measurement" in doctor["dependencies"]
    watch = next(item for item in features if item["id"] == "hot_path_watch")
    assert watch["maturity"] == "guarded"
    assert watch["default_enabled"] is True
    assert watch["automatic_control_allowed"] is False
    assert set(watch["dependencies"]) == {"hot_path_doctor", "trace_distribution_classifier"}
    freshness = next(item for item in features if item["id"] == "decision_freshness_passport")
    assert freshness["maturity"] == "guarded"
    assert freshness["default_enabled"] is True
    assert freshness["automatic_control_allowed"] is False
    assert freshness["dependencies"] == ["hot_path_watch"]


def test_feature_policy_fingerprint_changes_when_authority_changes() -> None:
    original = feature_registry()
    first = original[0]
    changed = (
        FeatureDefinition(
            id=first.id,
            version=first.version,
            maturity=first.maturity,
            default_enabled=first.default_enabled,
            automatic_control_allowed=not first.automatic_control_allowed,
            dependencies=first.dependencies,
            update_policy=first.update_policy,
            truth_boundary=first.truth_boundary,
        ),
        *original[1:],
    )
    assert feature_registry_fingerprint(changed) != feature_registry_fingerprint(original)


def test_optional_ai_features_are_fail_closed_for_automatic_control() -> None:
    for feature_id in ("optional_ai_language_provider", "ai_workload_drafting", "hot_path_doctor", "hot_path_watch", "decision_freshness_passport"):
        report = evaluate_feature_activation([feature_id], automatic_control=True)
        assert report["allowed"] is False
        assert report["decision"] == "DENY_FAIL_CLOSED"
        assert any(item["feature"] == feature_id for item in report["blockers"])


def test_research_feature_is_fail_closed_for_automatic_control() -> None:
    report = evaluate_feature_activation(
        ["trace_distribution_classifier"],
        automatic_control=True,
    )
    assert report["allowed"] is False
    assert report["decision"] == "DENY_FAIL_CLOSED"
    assert any(item["feature"] == "trace_distribution_classifier" for item in report["blockers"])


def test_blocked_feature_cannot_be_activated_even_without_control() -> None:
    report = evaluate_feature_activation(["native_cross_process_hot_swap"])
    assert report["allowed"] is False
    assert report["decision"] == "DENY_FAIL_CLOSED"
    assert any(item["reason"] == "feature maturity is blocked" for item in report["blockers"])


def test_guarded_runtime_feature_expands_dependencies() -> None:
    report = evaluate_feature_activation(
        ["runtime_declared_distribution_drift"],
        automatic_control=True,
    )
    assert report["allowed"] is True
    assert "workload_ir_v2_distribution_semantics" in report["expanded_features"]


def test_registry_rejects_research_feature_with_control_permission() -> None:
    bad = FeatureDefinition(
        id="unsafe",
        version="1",
        maturity=FeatureMaturity.RESEARCH,
        default_enabled=False,
        automatic_control_allowed=True,
        dependencies=(),
        update_policy="invalid",
        truth_boundary="invalid",
    )
    with pytest.raises(ValueError, match="cannot allow automatic control"):
        validate_feature_registry([bad])


def test_registry_rejects_dependency_cycle() -> None:
    first = FeatureDefinition(
        id="first",
        version="1",
        maturity=FeatureMaturity.GUARDED,
        default_enabled=False,
        automatic_control_allowed=False,
        dependencies=("second",),
        update_policy="test",
        truth_boundary="test",
    )
    second = FeatureDefinition(
        id="second",
        version="1",
        maturity=FeatureMaturity.GUARDED,
        default_enabled=False,
        automatic_control_allowed=False,
        dependencies=("first",),
        update_policy="test",
        truth_boundary="test",
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_feature_registry([first, second])
