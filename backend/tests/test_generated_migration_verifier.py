from __future__ import annotations

from pathlib import Path

import pytest

from app.engine import synthesize
from app.generated_migration_bundle import build_generated_migration_bundle, select_distinct_migration_pair
from app.generated_migration_verifier import VERIFICATION_SCHEMA, verify_generated_migration_bundle
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _bundle():
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    synthesis = synthesize(spec)
    source, target = select_distinct_migration_pair(synthesis)
    return build_generated_migration_bundle(spec, source, target, record_count=96)


def test_generated_migration_verifier_executes_and_reports_provenance() -> None:
    result = verify_generated_migration_bundle(_bundle())
    if result.evidence_state == "COMPILER_UNAVAILABLE":
        pytest.skip("C++20 compiler unavailable")

    assert result.success is True, result.as_dict()
    payload = result.as_dict()
    assert payload["schema"] == VERIFICATION_SCHEMA
    assert payload["evidence_state"] == "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION"
    assert payload["source_candidate_id"] != payload["target_candidate_id"]
    assert len(payload["source_manifest_sha256"]) == 64
    assert len(payload["target_manifest_sha256"]) == 64
    assert len(payload["harness_sha256"]) == 64
    assert payload["compile_returncode"] == 0
    assert payload["run_returncode"] == 0
    assert payload["source_reads"] > 0
    assert payload["target_reads"] > 0
    assert payload["invalid_reads"] == 0
    assert payload["final_generation"] >= 1
    assert "MORPHEUS_GENERATED_MIGRATION_OK" in payload["run_stdout"]
    assert "cross-process/distributed" in payload["truth_boundary"]


def test_generated_migration_verifier_fails_closed_when_compiler_is_unavailable(monkeypatch) -> None:
    bundle = _bundle()
    monkeypatch.setattr("app.generated_migration_verifier.discover_toolchain", lambda: None)
    result = verify_generated_migration_bundle(bundle)
    assert result.success is False
    assert result.evidence_state == "COMPILER_UNAVAILABLE"
    assert result.compile_returncode is None
    assert result.run_returncode is None
    assert result.source_manifest_sha256 != result.target_manifest_sha256


def test_generated_migration_verifier_rejects_unbounded_timeouts() -> None:
    bundle = _bundle()
    with pytest.raises(ValueError, match="compile_timeout_seconds"):
        verify_generated_migration_bundle(bundle, compile_timeout_seconds=0)
    with pytest.raises(ValueError, match="run_timeout_seconds"):
        verify_generated_migration_bundle(bundle, run_timeout_seconds=601)
