from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation_evidence_manifest import AblationResearchEvidenceManifest
from app.search_quality_ablation_reproducibility import (
    EVIDENCE_STATE,
    bind_ablation_execution_provenance,
)


def _manifest() -> AblationResearchEvidenceManifest:
    return AblationResearchEvidenceManifest(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="a" * 64,
        disclosure_sha256="b" * 64,
        threats_sha256="c" * 64,
        family_size=3,
        measurement_source_id="heldout-family-a",
        protocol="rq-ablation-family-v2",
        machine_fingerprint="machine-a",
        reference_label="full-model",
        workload_count=8,
        candidate_count=24,
        top_k=3,
        family_wise_alpha=0.05,
        correction_method="holm_step_down_family_wise_error_control",
        family_acceptance_passed=False,
        disclosed_accepted_count=2,
        disclosed_not_accepted_count=1,
        evidence_manifest_sha256="d" * 64,
        integrity_passed=True,
    )


def _bind(manifest: AblationResearchEvidenceManifest | None = None, **overrides: str):
    values = {
        "implementation_commit_sha": "1" * 40,
        "analysis_code_sha256": "2" * 64,
        "test_code_sha256": "3" * 64,
        "dependency_lock_sha256": "4" * 64,
        "ci_workflow_sha256": "5" * 64,
        "runtime_id": "python-3.14-linux-x86_64",
    }
    values.update(overrides)
    return bind_ablation_execution_provenance(manifest or _manifest(), **values)


def test_provenance_binds_complete_identity_set_without_promoting_negative_result() -> None:
    report = _bind()
    assert report.evidence_manifest_sha256 == "d" * 64
    assert report.implementation_commit_sha == "1" * 40
    assert report.provenance_complete is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    assert len(report.execution_provenance_sha256) == 64
    payload = report.as_dict()
    assert "does not prove that the supplied hashes describe the files actually executed" in payload["truth_boundary"]
    assert "independent reproduction" in payload["truth_boundary"]


def test_provenance_is_deterministic_and_normalizes_hex_case_and_whitespace() -> None:
    first = _bind()
    second = _bind(
        implementation_commit_sha="  " + ("A1" * 20) + "  ",
        analysis_code_sha256="B2" * 32,
        test_code_sha256="C3" * 32,
        dependency_lock_sha256="D4" * 32,
        ci_workflow_sha256="E5" * 32,
        runtime_id=" python-3.14-linux-x86_64 ",
    )
    third = _bind(
        implementation_commit_sha="a1" * 20,
        analysis_code_sha256="b2" * 32,
        test_code_sha256="c3" * 32,
        dependency_lock_sha256="d4" * 32,
        ci_workflow_sha256="e5" * 32,
    )
    assert second.execution_provenance_sha256 == third.execution_provenance_sha256
    assert first.execution_provenance_sha256 != second.execution_provenance_sha256


def test_provenance_hash_changes_when_any_bound_identity_changes() -> None:
    baseline = _bind().execution_provenance_sha256
    assert _bind(runtime_id="python-3.14-windows-amd64").execution_provenance_sha256 != baseline
    assert _bind(analysis_code_sha256="6" * 64).execution_provenance_sha256 != baseline
    assert _bind(test_code_sha256="7" * 64).execution_provenance_sha256 != baseline
    assert _bind(dependency_lock_sha256="8" * 64).execution_provenance_sha256 != baseline
    assert _bind(ci_workflow_sha256="9" * 64).execution_provenance_sha256 != baseline


def test_provenance_rejects_malformed_or_missing_identities() -> None:
    with pytest.raises(ValueError, match="40-character hexadecimal"):
        _bind(implementation_commit_sha="not-a-commit")
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        _bind(analysis_code_sha256="bad")
    with pytest.raises(ValueError, match="runtime_id cannot be empty"):
        _bind(runtime_id="   ")
    with pytest.raises(ValueError, match="evidence_manifest_sha256"):
        _bind(replace(_manifest(), evidence_manifest_sha256="bad"))


def test_provenance_rejects_incompatible_incomplete_or_control_authorizing_manifest() -> None:
    with pytest.raises(ValueError, match="evidence_state"):
        _bind(replace(_manifest(), evidence_state="OTHER"))
    with pytest.raises(ValueError, match="integrity validation"):
        _bind(replace(_manifest(), integrity_passed=False))
    with pytest.raises(ValueError, match="automatic control"):
        _bind(replace(_manifest(), automatic_control_allowed=True))
