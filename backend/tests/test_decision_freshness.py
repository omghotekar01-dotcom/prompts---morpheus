from __future__ import annotations

from app.decision_freshness import build_decision_freshness_passport


def _doctor() -> dict:
    return {
        "launch_state": "RECOMMENDATION_REQUIRES_LOCAL_MEASUREMENT_AND_VERIFICATION",
        "migration_playbook": [
            {"gate": "LOCAL_MEASUREMENT_REQUIRED_BEFORE_PERFORMANCE_CLAIM"},
            {"gate": "COMPILE_AND_CORRECTNESS_VERIFICATION_REQUIRED"},
            {"gate": "CORRECTNESS_BEFORE_CUTOVER"},
            {"gate": "HUMAN_AUTHORIZED_DEPLOYMENT_ONLY"},
        ],
    }


def _build(
    *,
    action: str,
    drifted: bool = False,
    candidate_changed: bool = False,
    route_changed: bool = False,
    distribution_changed: bool = False,
    baseline_keys: list[int] | None = None,
    observed_keys: list[int] | None = None,
) -> dict:
    baseline_keys = baseline_keys or [1, 2, 3, 4]
    observed_keys = observed_keys or [1, 2, 3, 4]
    return build_decision_freshness_passport(
        source_spec_hash="a" * 64,
        query_index=0,
        current_structure="std_unordered_map",
        baseline_keys=baseline_keys,
        observed_keys=observed_keys,
        drift={"drifted": drifted},
        baseline={
            "draft_spec_hash": "b" * 64,
            "winner_candidate_id": "candidate-old",
            "route_primitive": "robin_hood_hash",
            "doctor": _doctor(),
        },
        observed={
            "draft_spec_hash": "c" * 64,
            "winner_candidate_id": "candidate-new" if candidate_changed else "candidate-old",
            "route_primitive": "ordered_tree" if route_changed else "robin_hood_hash",
            "doctor": _doctor(),
        },
        decision={
            "action": action,
            "candidate_changed": candidate_changed,
            "route_primitive_changed": route_changed,
            "distribution_label_changed": distribution_changed,
        },
    )


def test_stable_windows_keep_decision_current_without_rollout_authority() -> None:
    passport = _build(action="KEEP_AND_MONITOR")

    assert passport["freshness_state"] == "CURRENT_FOR_SUPPLIED_WINDOWS"
    assert passport["rollout_disposition"] == "NO_CHANGE_REQUIRED_CONTINUE_MONITORING"
    assert passport["eligible_for_runtime_automatic_control"] is False
    assert passport["change_ticket"]["automatic_stage_advance_allowed"] is False
    assert passport["change_ticket"]["automatic_cutover_allowed"] is False
    assert len(passport["passport_sha256"]) == 64


def test_drift_without_candidate_change_requires_remeasurement() -> None:
    passport = _build(
        action="REMEASURE_RECOMMENDATION_AFTER_DRIFT",
        drifted=True,
        distribution_changed=True,
    )

    assert passport["freshness_state"] == "REVIEW_REQUIRED_AFTER_DRIFT"
    assert passport["rollout_disposition"] == "HOLD_AND_REMEASURE_CURRENT_RECOMMENDATION"
    assert "TARGET_MACHINE_REMEASUREMENT_REQUIRED" in passport["change_ticket"]["required_evidence_gates"]
    assert "FRESH_TRACE_REVALIDATION_BEFORE_CUTOVER" in passport["change_ticket"]["required_evidence_gates"]


def test_changed_modeled_design_supersedes_prior_decision_for_supplied_windows() -> None:
    passport = _build(
        action="RESYNTHESIZE_MEASURE_VERIFY_SHADOW",
        drifted=True,
        candidate_changed=True,
        route_changed=True,
    )

    assert passport["freshness_state"] == "SUPERSEDED_FOR_SUPPLIED_WINDOWS"
    assert passport["rollout_disposition"] == "HOLD_PRIOR_DECISION_REVALIDATE_OBSERVED_CANDIDATE"
    stages = {item["id"]: item for item in passport["change_ticket"]["stages"]}
    assert stages["shadow"]["required"] is True
    assert stages["human_cutover"]["required"] is True
    assert "old and proposed implementations" in stages["shadow"]["action"]
    assert "reversible" in passport["change_ticket"]["rollback_requirements"][1].lower()


def test_infeasible_observed_workload_blocks_rollout() -> None:
    passport = _build(action="BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE", drifted=True)

    assert passport["freshness_state"] == "BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE"
    assert passport["rollout_disposition"] == "DO_NOT_ROLLOUT_RESOLVE_CONSTRAINTS"
    assert passport["change_ticket"]["stages"][0]["required"] is True


def test_passport_identity_changes_when_either_trace_window_changes() -> None:
    first = _build(action="KEEP_AND_MONITOR")
    second = _build(
        action="KEEP_AND_MONITOR",
        observed_keys=[1, 2, 3, 5],
    )

    assert first["evidence_binding"]["baseline_window_sha256"] == second["evidence_binding"]["baseline_window_sha256"]
    assert first["evidence_binding"]["observed_window_sha256"] != second["evidence_binding"]["observed_window_sha256"]
    assert first["passport_sha256"] != second["passport_sha256"]


def test_truth_boundary_refuses_clock_expiry_and_future_traffic_claims() -> None:
    passport = _build(action="KEEP_AND_MONITOR")

    assert "not a clock-based expiry" in passport["truth_boundary"]
    assert "future traffic" in passport["truth_boundary"]
    assert "deployment authorization" in passport["truth_boundary"]
