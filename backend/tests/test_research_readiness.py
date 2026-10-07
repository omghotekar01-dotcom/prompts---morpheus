from __future__ import annotations

from fastapi.testclient import TestClient

from app.research_readiness import distribution_research_readiness
from app.server import app


def test_distribution_research_readiness_separates_implementation_from_promotion() -> None:
    payload = distribution_research_readiness()
    features = {item["feature"]: item for item in payload["features"]}

    assert payload["schema"] == "morpheus-distribution-research-readiness-v1"
    assert payload["evidence_state"] == "IMPLEMENTATION_AND_PROMOTION_BOUNDARIES_DECLARED"
    assert features["typed_access_distribution_mws_ir"]["implementation_state"] == "IMPLEMENTED_TESTED"
    assert features["generated_candidate_distribution_execution"]["automatic_control_allowed"] is True
    calibration = features["distribution_aware_primitive_cost_calibration"]
    assert calibration["implementation_state"] == "IMPLEMENTED_TESTED_CI_SMOKE_PROVENANCE_BOUND"
    assert calibration["evidence_scope"] == "MACHINE_LOCAL_DISTRIBUTION_BOUND_PRIMITIVE_CALIBRATION"
    assert calibration["automatic_control_allowed"] is False
    assert "controlled-hardware" in calibration["blocker"]
    assert features["access_trace_characterization"]["automatic_control_allowed"] is False
    assert features["rolling_trace_phase_candidates"]["automatic_control_allowed"] is False
    assert "synthetic accuracy is not real-workload generalization evidence" in payload["promotion_blockers"]
    assert "does not imply" in payload["truth_boundary"]


def test_distribution_research_readiness_api_preserves_nonpromotion_boundary() -> None:
    response = TestClient(app).get("/api/v2/research/distribution-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-distribution-research-readiness-v1"
    assert payload["evidence_state"] == "IMPLEMENTATION_AND_PROMOTION_BOUNDARIES_DECLARED"
    restricted = set(payload["restricted_research_features"])
    assert "access_trace_characterization" in restricted
    assert "trace_classifier_synthetic_evaluation" in restricted
    feature = next(
        item
        for item in payload["features"]
        if item["feature"] == "access_trace_characterization"
    )
    assert feature["automatic_control_allowed"] is False
    assert "must not be converted into autonomous runtime-control inputs" in payload["truth_boundary"]
