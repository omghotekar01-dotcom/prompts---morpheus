from __future__ import annotations

import hashlib
import json

import pytest

from app.generated_migration_resume import validate_rq7_resume_checkpoint
from app.research_suite import FrozenExperiment


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _experiment() -> FrozenExperiment:
    return FrozenExperiment(
        experiment_id="rq7-cell-001",
        factors={"readers": 2, "transitions": 8, "record_count": 64},
        repetitions=3,
        factor_sha256=_canonical({"readers": 2, "transitions": 8, "record_count": 64}),
    )


def _report(source_manifest: str, target_manifest: str) -> dict:
    rows = [
        {
            "repetition": i,
            "readers": 2,
            "transitions": 8,
            "record_count": 64,
            "migrate_validate_activate_ns_per": 100 + i,
            "rollback_ns_per": 50 + i,
            "reads": 1000,
            "invalid_reads": 0,
        }
        for i in range(3)
    ]
    return {
        "success": True,
        "evidence_state": "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
        "source_candidate_id": "source-a",
        "target_candidate_id": "target-b",
        "workload_ir_hash": _sha("workload"),
        "source_configuration_ir_hash": _sha("source-ir"),
        "target_configuration_ir_hash": _sha("target-ir"),
        "source_manifest_sha256": source_manifest,
        "target_manifest_sha256": target_manifest,
        "source_header_sha256": _sha("source-header"),
        "target_header_sha256": _sha("target-header"),
        "benchmark_source_sha256": _sha("benchmark"),
        "compiler": "cc",
        "compiler_kind": "clang",
        "compiler_version": "18.1.0",
        "config": {"readers": 2, "transitions": 8, "repetitions": 3, "record_count": 64},
        "rows": rows,
        "compile_returncode": 0,
        "run_returncode": 0,
        "compile_stdout": "",
        "compile_stderr": "",
        "run_stdout": "",
        "run_stderr": "",
    }


def _payload() -> tuple[dict, dict]:
    experiment = _experiment()
    source_manifest = _sha("source-manifest")
    target_manifest = _sha("target-manifest")
    report = _report(source_manifest, target_manifest)
    payload = {
        "schema": "morpheus-generated-migration-campaign-v1",
        "study_id": "rq7-generated-migration-v1",
        "manifest_sha256": _sha("matrix"),
        "machine_fingerprint_sha256": _sha("machine"),
        "source_candidate_id": "source-a",
        "target_candidate_id": "target-b",
        "source_manifest_sha256": source_manifest,
        "target_manifest_sha256": target_manifest,
        "campaign_sha256": _sha("campaign"),
        "entries": [{
            "experiment_id": experiment.experiment_id,
            "factor_sha256": experiment.factor_sha256,
            "factors": experiment.factors,
            "report": report,
            "report_sha256": _canonical(report),
            "verified_total_reads": 3000,
        }],
    }
    kwargs = {
        "manifest_sha256": payload["manifest_sha256"],
        "machine_fingerprint_sha256": payload["machine_fingerprint_sha256"],
        "source_candidate_id": "source-a",
        "target_candidate_id": "target-b",
        "source_manifest_sha256": source_manifest,
        "target_manifest_sha256": target_manifest,
        "experiments": [experiment],
        "machine_profile": {"toolchain": {"compiler": "cc", "compiler_kind": "clang", "compiler_version": "18.1.0"}},
    }
    return payload, kwargs


def test_resume_rejects_report_tampering_after_hash_binding() -> None:
    payload, kwargs = _payload()
    payload["entries"][0]["report"]["rows"][0]["invalid_reads"] = 1
    with pytest.raises(ValueError, match="report hash mismatch"):
        validate_rq7_resume_checkpoint(payload, **kwargs)


def test_resume_rejects_machine_substitution() -> None:
    payload, kwargs = _payload()
    kwargs["machine_fingerprint_sha256"] = _sha("different-machine")
    with pytest.raises(ValueError, match="machine fingerprint"):
        validate_rq7_resume_checkpoint(payload, **kwargs)


def test_resume_rejects_duplicate_experiment_identity() -> None:
    payload, kwargs = _payload()
    payload["entries"].append(dict(payload["entries"][0]))
    with pytest.raises(ValueError, match="duplicate experiment ids"):
        validate_rq7_resume_checkpoint(payload, **kwargs)


def test_resume_rejects_failed_prior_cell_even_when_hash_is_valid() -> None:
    payload, kwargs = _payload()
    entry = payload["entries"][0]
    entry["report"]["success"] = False
    entry["report_sha256"] = _canonical(entry["report"])
    with pytest.raises(ValueError, match="failed experiment"):
        validate_rq7_resume_checkpoint(payload, **kwargs)
