from __future__ import annotations

from app.claim_gate import evaluate_claim, evaluate_claim_bundle, known_claim_types


def test_speedup_claim_is_blocked_until_all_measurement_roles_exist() -> None:
    incomplete = evaluate_claim(
        "measured_speedup",
        ["experiment_manifest", "raw_measurements", "machine_profile"],
    )
    assert incomplete.allowed is False
    assert "statistical_summary" in incomplete.missing_roles
    assert "baseline_manifest" in incomplete.missing_roles
    assert incomplete.evidence_state == "CLAIM_EVIDENCE_INCOMPLETE"

    complete = evaluate_claim(
        "measured_speedup",
        ["experiment_manifest", "raw_measurements", "statistical_summary", "machine_profile", "baseline_manifest"],
    )
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert complete.evidence_state == "CLAIM_EVIDENCE_GATE_SATISFIED"


def test_distribution_calibration_claim_requires_manifest_raw_and_machine() -> None:
    incomplete = evaluate_claim("distribution_calibration_evidence", ["raw_measurements", "machine_profile"])
    assert incomplete.allowed is False
    assert incomplete.missing_roles == ("distribution_calibration_manifest",)

    complete = evaluate_claim(
        "distribution_calibration_evidence",
        ["distribution_calibration_manifest", "raw_measurements", "machine_profile"],
    )
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert "not end-to-end candidate performance evidence" in complete.truth_boundary


def test_distribution_calibration_decision_quality_requires_heldout_evaluation() -> None:
    decision = evaluate_claim(
        "distribution_calibration_improves_decisions",
        ["experiment_manifest", "distribution_calibration_manifest", "raw_measurements", "machine_profile"],
    )
    assert decision.allowed is False
    assert decision.missing_roles == ("prediction_evaluation",)


def test_generated_migration_claim_requires_its_verified_manifest() -> None:
    incomplete = evaluate_claim("same_process_generated_migration", [])
    assert incomplete.allowed is False
    assert incomplete.missing_roles == ("generated_migration_verification_manifest",)

    complete = evaluate_claim("same_process_generated_migration", ["generated_migration_verification_manifest"])
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert "same-process publication" in complete.truth_boundary
    assert "cross-process/distributed" in complete.truth_boundary


def test_generated_migration_transition_cost_claim_requires_complete_evidence_chain() -> None:
    roles_without_attestation = [
        "experiment_manifest",
        "generated_migration_campaign",
        "generated_migration_campaign_summary",
        "machine_profile",
    ]
    incomplete = evaluate_claim("generated_migration_transition_cost_measured", roles_without_attestation)
    assert incomplete.allowed is False
    assert incomplete.missing_roles == ("generated_migration_transition_cost_evidence",)

    complete = evaluate_claim(
        "generated_migration_transition_cost_measured",
        [*roles_without_attestation, "generated_migration_transition_cost_evidence"],
    )
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert "complete frozen RQ7 matrix" in complete.truth_boundary
    assert "CI-smoke" in complete.truth_boundary
    assert "does not establish a scaling law" in complete.truth_boundary


def test_rq7_record_count_effect_claim_requires_analysis_and_complete_local_attestation() -> None:
    base = [
        "experiment_manifest",
        "generated_migration_campaign",
        "generated_migration_transition_cost_evidence",
        "machine_profile",
    ]
    incomplete = evaluate_claim("rq7_systematic_record_count_effect", base)
    assert incomplete.allowed is False
    assert incomplete.missing_roles == ("rq7_confirmatory_analysis",)

    complete = evaluate_claim("rq7_systematic_record_count_effect", [*base, "rq7_confirmatory_analysis"])
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert "systematic record-count effect" in complete.truth_boundary
    assert "not an asymptotic complexity law" in complete.truth_boundary
    assert "single machine/toolchain" in complete.truth_boundary


def test_generated_migration_manifest_does_not_satisfy_broader_hot_swap_claim() -> None:
    decision = evaluate_claim("live_hot_swap", ["generated_migration_verification_manifest"])
    assert decision.allowed is False
    assert set(decision.missing_roles) == {"live_swap_manifest", "concurrent_stress_report", "rollback_report"}
    assert "narrower same-process generated-migration verifier" in decision.truth_boundary


def test_hot_swap_claim_cannot_be_satisfied_by_control_plane_roles() -> None:
    decision = evaluate_claim("live_hot_swap", ["migration_plan", "verification_manifest", "runtime_trace"])
    assert decision.allowed is False
    assert set(decision.missing_roles) == {"live_swap_manifest", "concurrent_stress_report", "rollback_report"}


def test_release_bundle_fails_closed_if_any_claim_lacks_evidence() -> None:
    bundle = evaluate_claim_bundle(
        [("generated_cpp20", ["generated_header"]), ("artifact_compiles", [])]
    )
    assert bundle["allowed"] is False
    assert bundle["evidence_state"] == "RELEASE_CLAIM_BUNDLE_BLOCKED_BY_MISSING_EVIDENCE"


def test_known_claim_types_include_high_risk_public_claims() -> None:
    names = known_claim_types()
    assert "measured_speedup" in names
    assert "same_process_generated_migration" in names
    assert "generated_migration_transition_cost_measured" in names
    assert "rq7_systematic_record_count_effect" in names
    assert "live_hot_swap" in names
    assert "state_of_art" in names
    assert "distribution_calibration_evidence" in names
    assert "distribution_calibration_improves_decisions" in names
