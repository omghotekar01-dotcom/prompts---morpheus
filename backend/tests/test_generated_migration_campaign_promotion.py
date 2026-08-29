from __future__ import annotations

from copy import deepcopy

import pytest

from app.generated_migration_benchmark import BENCHMARK_PROTOCOL, BENCHMARK_SCHEMA
from app.generated_migration_campaign_promotion import promote_generated_migration_campaign


H = {
    "workload": "1" * 64,
    "source_cfg": "2" * 64,
    "target_cfg": "3" * 64,
    "source_header": "4" * 64,
    "target_header": "5" * 64,
    "benchmark": "6" * 64,
}


def _report(index: int) -> dict:
    # Manifest identities vary per independently generated candidate artifact, while
    # the benchmark implementation remains fixed as the controlled experimental input.
    source_manifest = f"{index + 10:064x}"
    target_manifest = f"{index + 20:064x}"
    return {
        "schema": BENCHMARK_SCHEMA,
        "protocol": BENCHMARK_PROTOCOL,
        "success": True,
        "evidence_state": "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
        "source_candidate_id": "candidate.source",
        "target_candidate_id": "candidate.target",
        "workload_ir_hash": H["workload"],
        "source_configuration_ir_hash": H["source_cfg"],
        "target_configuration_ir_hash": H["target_cfg"],
        "source_manifest_sha256": source_manifest,
        "target_manifest_sha256": target_manifest,
        "source_header_sha256": H["source_header"],
        "target_header_sha256": H["target_header"],
        "benchmark_source_sha256": H["benchmark"],
        "config": {"readers": 2, "transitions": 4, "repetitions": 1, "record_count": 64},
        "compile_returncode": 0,
        "run_returncode": 0,
        "rows": [
            {
                "repetition": 0,
                "readers": 2,
                "transitions": 4,
                "record_count": 64,
                "migrate_validate_activate_ns_per": 100 + index,
                "rollback_ns_per": 50 + index,
                "reads": 1000 + index,
                "invalid_reads": 0,
            }
        ],
    }


def test_promotes_three_independent_reports_with_one_controlled_benchmark() -> None:
    reports = [_report(0), _report(1), _report(2)]
    decision = promote_generated_migration_campaign(reports)

    assert decision.promoted is True
    assert decision.independent_reports == 3
    assert decision.benchmark_source_sha256 == H["benchmark"]
    assert len(decision.report_sha256) == 3
    assert len(decision.decision_sha256) == 64


def test_rejects_benchmark_source_drift_between_reports() -> None:
    reports = [_report(0), _report(1), _report(2)]
    reports[2]["benchmark_source_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="one controlled benchmark source identity"):
        promote_generated_migration_campaign(reports)


def test_rejects_reused_manifest_pair() -> None:
    reports = [_report(0), _report(1), _report(2)]
    reports[2]["source_manifest_sha256"] = reports[1]["source_manifest_sha256"]
    reports[2]["target_manifest_sha256"] = reports[1]["target_manifest_sha256"]

    with pytest.raises(ValueError, match="manifest pair reused"):
        promote_generated_migration_campaign(reports)


def test_report_order_does_not_change_campaign_decision_hash() -> None:
    reports = [_report(0), _report(1), _report(2)]
    forward = promote_generated_migration_campaign(reports)
    reverse = promote_generated_migration_campaign(list(reversed(deepcopy(reports))))

    assert forward.decision_sha256 == reverse.decision_sha256


def test_boolean_minimum_report_count_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        promote_generated_migration_campaign([_report(0), _report(1), _report(2)], minimum_independent_reports=True)
