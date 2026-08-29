from __future__ import annotations

import pytest

from app.feature_registry import (
    FEATURE_REGISTRY_SCHEMA,
    FeatureDefinition,
    FeatureMaturity,
    evaluate_feature_activation,
    registry_payload,
    validate_feature_registry,
)


def test_registry_is_valid_versioned_and_unique() -> None:
    validate_feature_registry()
    payload = registry_payload()
    assert payload["schema"] == FEATURE_REGISTRY_SCHEMA
    features = payload["features"]
    ids = [item["id"] for item in features]
    assert len(ids) == len(set(ids))
    assert "native_cross_process_hot_swap" in ids


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
