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
        [
            "experiment_manifest",
            "raw_measurements",
            "statistical_summary",
            "machine_profile",
            "baseline_manifest",
        ],
    )
    assert complete.allowed is True
    assert complete.missing_roles == ()
    assert complete.evidence_state == "CLAIM_EVIDENCE_GATE_SATISFIED"


def test_hot_swap_claim_cannot_be_satisfied_by_control_plane_roles() -> None:
    decision = evaluate_claim(
        "live_hot_swap",
        ["migration_plan", "verification_manifest", "runtime_trace"],
    )
    assert decision.allowed is False
    assert set(decision.missing_roles) == {
        "live_swap_manifest",
        "concurrent_stress_report",
        "rollback_report",
    }


def test_release_bundle_fails_closed_if_any_claim_lacks_evidence() -> None:
    bundle = evaluate_claim_bundle(
        [
            ("generated_cpp20", ["generated_header"]),
            ("artifact_compiles", []),
        ]
    )
    assert bundle["allowed"] is False
    assert bundle["evidence_state"] == "RELEASE_CLAIM_BUNDLE_BLOCKED_BY_MISSING_EVIDENCE"


def test_known_claim_types_include_high_risk_public_claims() -> None:
    names = known_claim_types()
    assert "measured_speedup" in names
    assert "live_hot_swap" in names
    assert "state_of_art" in names
