import copy

import pytest

from app.generated_migration_benchmark import BENCHMARK_PROTOCOL, BENCHMARK_SCHEMA
from app.generated_migration_benchmark_evidence import verify_generated_migration_benchmark_evidence


def _hash(char: str) -> str:
    return char * 64


def _valid_report() -> dict:
    return {
        "schema": BENCHMARK_SCHEMA,
        "protocol": BENCHMARK_PROTOCOL,
        "success": True,
        "evidence_state": "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
        "source_candidate_id": "candidate.source.v1",
        "target_candidate_id": "candidate.target.v2",
        "workload_ir_hash": _hash("1"),
        "source_configuration_ir_hash": _hash("2"),
        "target_configuration_ir_hash": _hash("3"),
        "source_manifest_sha256": _hash("4"),
        "target_manifest_sha256": _hash("5"),
        "source_header_sha256": _hash("6"),
        "target_header_sha256": _hash("7"),
        "benchmark_source_sha256": _hash("8"),
        "config": {"readers": 2, "transitions": 3, "repetitions": 2, "record_count": 32},
        "compile_returncode": 0,
        "run_returncode": 0,
        "rows": [
            {
                "repetition": 0,
                "readers": 2,
                "transitions": 3,
                "record_count": 32,
                "migrate_validate_activate_ns_per": 100,
                "rollback_ns_per": 80,
                "reads": 12,
                "invalid_reads": 0,
            },
            {
                "repetition": 1,
                "readers": 2,
                "transitions": 3,
                "record_count": 32,
                "migrate_validate_activate_ns_per": 110,
                "rollback_ns_per": 85,
                "reads": 14,
                "invalid_reads": 0,
            },
        ],
    }


def test_accepts_well_formed_independent_migration_evidence() -> None:
    verified = verify_generated_migration_benchmark_evidence(_valid_report())
    assert verified.rows == 2
    assert verified.total_reads == 26
    assert verified.manifest_hashes == (_hash("4"), _hash("5"))


@pytest.mark.parametrize("field", ["compile_returncode", "run_returncode"])
def test_rejects_boolean_return_code_aliases(field: str) -> None:
    report = _valid_report()
    report[field] = False
    with pytest.raises(ValueError, match="must be an integer"):
        verify_generated_migration_benchmark_evidence(report)


def test_rejects_same_source_and_target_manifest_identity() -> None:
    report = _valid_report()
    report["target_manifest_sha256"] = report["source_manifest_sha256"]
    with pytest.raises(ValueError, match="manifest identities must differ"):
        verify_generated_migration_benchmark_evidence(report)


def test_rejects_boolean_row_configuration_alias() -> None:
    report = _valid_report()
    report["rows"][0]["readers"] = True
    with pytest.raises(ValueError, match="rows\[0\]\.readers must be an integer"):
        verify_generated_migration_benchmark_evidence(report)


def test_rejects_non_contiguous_repetition_indexes() -> None:
    report = _valid_report()
    report["rows"][1]["repetition"] = 2
    with pytest.raises(ValueError, match="contiguous from zero"):
        verify_generated_migration_benchmark_evidence(report)


def test_rejects_noncanonical_candidate_identity() -> None:
    report = copy.deepcopy(_valid_report())
    report["target_candidate_id"] = " target candidate "
    with pytest.raises(ValueError, match="canonical 1-128 character identifier"):
        verify_generated_migration_benchmark_evidence(report)
