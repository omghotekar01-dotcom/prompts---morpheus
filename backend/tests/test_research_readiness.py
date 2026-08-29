from __future__ import annotations

from app.research_readiness import distribution_research_readiness


def test_distribution_research_readiness_separates_implementation_from_promotion() -> None:
    payload = distribution_research_readiness()
    features = {item["feature"]: item for item in payload["features"]}

    assert payload["schema"] == "morpheus-distribution-research-readiness-v1"
    assert payload["evidence_state"] == "IMPLEMENTATION_AND_PROMOTION_BOUNDARIES_DECLARED"
    assert features["typed_access_distribution_mws_ir"]["implementation_state"] == "IMPLEMENTED_TESTED"
    assert features["generated_candidate_distribution_execution"]["automatic_control_allowed"] is True
    assert features["distribution_aware_primitive_cost_calibration"]["automatic_control_allowed"] is False
    assert features["access_trace_characterization"]["automatic_control_allowed"] is False
    assert features["rolling_trace_phase_candidates"]["automatic_control_allowed"] is False
    assert "synthetic accuracy is not real-workload generalization evidence" in payload["promotion_blockers"]
    assert "does not imply" in payload["truth_boundary"]
