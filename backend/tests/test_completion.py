from __future__ import annotations

from app.completion import engineering_completion_report


def _capabilities() -> dict[str, str]:
    return {
        "mws": "IMPLEMENTED_TESTED",
        "deterministic_search": "IMPLEMENTED_TESTED",
        "bplus_tree_primitive": "IMPLEMENTED_TESTED",
        "windows_msvc_cpp20_ci": "IMPLEMENTED_CI",
        "core_sanitizer_gate": "IMPLEMENTED_CI_ASAN_UBSAN",
        "artifact_codegen": "IMPLEMENTED_TESTED",
        "artifact_compile_gate": "IMPLEMENTED_LOCAL_TOOLCHAIN",
        "artifact_stateful_differential_gate": "IMPLEMENTED_SCHEMA_DERIVED",
        "feature_policy_registry": "IMPLEMENTED_TESTED_FAIL_CLOSED_PROMOTION",
        "distribution_bound_calibration": "IMPLEMENTED_TESTED_EXACT_IMPLEMENTATION_OPERATION_SCALE_DISTRIBUTION",
        "workload_calibration_coverage": "IMPLEMENTED_TESTED_FAIL_CLOSED_SCALE_DISTRIBUTION",
        "distribution_aware_mutation_cost": "IMPLEMENTED_TESTED_EXACT_OPERATION_DISTRIBUTION",
        "api_contract_fingerprint": "IMPLEMENTED_TESTED_ROUTE_FINGERPRINT",
        "calibration_import": "IMPLEMENTED_TESTED",
        "calibration_persistence": "IMPLEMENTED_SQLITE_DURABLE",
        "distribution_calibration_matrix": "IMPLEMENTED_TESTED_CI_SMOKE_EXPLORATORY_PACKAGE",
        "paired_baseline_matrix": "IMPLEMENTED_MEASURED_CI_SMOKE",
        "beam_search": "IMPLEMENTED_TESTED",
        "pareto_front": "IMPLEMENTED_TESTED",
        "search_quality_oracle_evaluation": "IMPLEMENTED_TESTED_MODEL_ORACLE",
        "runtime_drift_detection": "IMPLEMENTED_TESTED",
        "runtime_gated_migration": "IMPLEMENTED_CONTROL_PLANE_ONLY",
        "local_dataplane_swap": "IMPLEMENTED_TESTED_IN_PROCESS",
        "persistent_run_metadata": "IMPLEMENTED_SQLITE",
        "tamper_evident_evidence_ledger": "IMPLEMENTED_SHA256_HASH_CHAIN",
        "optional_api_key_and_rate_limit": "IMPLEMENTED_PROCESS_LOCAL",
        "bounded_local_worker": "IMPLEMENTED_TESTED_HOST_PROCESS",
        "copilot_evidence_mode": "IMPLEMENTED_DETERMINISTIC",
        "copilot_llm": "NOT_IMPLEMENTED",
        "heldout_prediction_evaluation": "IMPLEMENTED_TESTED_CALLER_MEASUREMENTS",
        "research_experiment_suite": "IMPLEMENTED_TESTED",
        "release_claim_gate": "IMPLEMENTED_TESTED",
        "release_evidence_package": "IMPLEMENTED_TESTED",
        "distribution_release_provenance": "IMPLEMENTED_TESTED_STRUCTURAL_AND_CROSS_HASH_VALIDATION",
        "reproducibility_manifest": "IMPLEMENTED_LOCAL_HASH_MANIFEST",
        "contract_bound_reproducibility": "IMPLEMENTED_TESTED_EXACT_COMMIT_API_FEATURE_POLICY_HASHES",
    }


def test_completion_report_counts_engineering_gates_without_external_outcomes() -> None:
    report = engineering_completion_report(_capabilities())
    assert report["passed_gates"] == report["total_gates"]
    assert report["engineering_percent"] == 100.0
    assert all(phase["state"] == "ENGINEERING_GATES_COMPLETE" for phase in report["phases"])
    assert "publication acceptance" in report["excluded_outcomes"]
    p4 = next(phase for phase in report["phases"] if phase["id"] == "P4")
    assert p4["engineering_percent"] == 100.0
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    assert p11["engineering_percent"] == 100.0


def test_completion_report_fails_closed_on_missing_capability() -> None:
    capabilities = _capabilities()
    del capabilities["release_evidence_package"]
    report = engineering_completion_report(capabilities)
    assert report["engineering_percent"] < 100.0
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    package_gate = next(gate for gate in p11["gates"] if gate["id"] == "package")
    assert package_gate["passed"] is False
    assert package_gate["value"] == "MISSING"


def test_release_phase_fails_closed_without_contract_bound_reproducibility() -> None:
    capabilities = _capabilities()
    del capabilities["contract_bound_reproducibility"]
    report = engineering_completion_report(capabilities)
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    gate = next(gate for gate in p11["gates"] if gate["id"] == "contract-repro")
    assert gate["passed"] is False
    assert gate["value"] == "MISSING"
    assert p11["state"] == "ENGINEERING_GATES_INCOMPLETE"


def test_release_phase_fails_closed_without_distribution_provenance() -> None:
    capabilities = _capabilities()
    del capabilities["distribution_release_provenance"]
    report = engineering_completion_report(capabilities)
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    gate = next(gate for gate in p11["gates"] if gate["id"] == "distribution-provenance")
    assert gate["passed"] is False
    assert gate["value"] == "MISSING"


def test_evidence_identity_phase_fails_closed_on_missing_distribution_gate() -> None:
    capabilities = _capabilities()
    del capabilities["distribution_aware_mutation_cost"]
    report = engineering_completion_report(capabilities)
    p4 = next(phase for phase in report["phases"] if phase["id"] == "P4")
    mutation_gate = next(gate for gate in p4["gates"] if gate["id"] == "mutation-cost")
    assert mutation_gate["passed"] is False
    assert mutation_gate["value"] == "MISSING"
    assert p4["state"] == "ENGINEERING_GATES_INCOMPLETE"
