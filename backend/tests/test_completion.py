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
        "calibration_import": "IMPLEMENTED_TESTED",
        "calibration_persistence": "IMPLEMENTED_SQLITE_DURABLE",
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
        "reproducibility_manifest": "IMPLEMENTED_LOCAL_HASH_MANIFEST",
    }


def test_completion_report_counts_engineering_gates_without_external_outcomes() -> None:
    report = engineering_completion_report(_capabilities())
    assert report["passed_gates"] == report["total_gates"]
    assert report["engineering_percent"] == 100.0
    assert all(phase["state"] == "ENGINEERING_GATES_COMPLETE" for phase in report["phases"])
    assert "publication acceptance" in report["excluded_outcomes"]


def test_completion_report_fails_closed_on_missing_capability() -> None:
    capabilities = _capabilities()
    del capabilities["release_evidence_package"]
    report = engineering_completion_report(capabilities)
    assert report["engineering_percent"] < 100.0
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    package_gate = next(gate for gate in p11["gates"] if gate["id"] == "package")
    assert package_gate["passed"] is False
    assert package_gate["value"] == "MISSING"
