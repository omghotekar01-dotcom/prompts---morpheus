from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_reproducibility import AblationExecutionProvenance
from app.search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from app.search_quality_ablation_result_reproducibility import (
    EVIDENCE_STATE,
    verify_ablation_result_execution_provenance_consistency,
)

MANIFEST_SHA = "aa" * 32
PROVENANCE_SHA = "bb" * 32
COMMIT_SHA = "cc" * 20
ANALYSIS_SHA = "dd" * 32
TEST_SHA = "ee" * 32
LOCK_SHA = "12" * 32
WORKFLOW_SHA = "34" * 32
MANIFEST_VERIFICATION_SHA = "56" * 32
RUNTIME_ID = "python-3.14-linux-x86_64"


def _provenance() -> AblationExecutionProvenance:
    return AblationExecutionProvenance(
        evidence_manifest_sha256=MANIFEST_SHA,
        implementation_commit_sha=COMMIT_SHA,
        analysis_code_sha256=ANALYSIS_SHA,
        test_code_sha256=TEST_SHA,
        dependency_lock_sha256=LOCK_SHA,
        ci_workflow_sha256=WORKFLOW_SHA,
        runtime_id=RUNTIME_ID,
        execution_provenance_sha256=PROVENANCE_SHA,
        provenance_complete=True,
    )


def _document(provenance: AblationExecutionProvenance | None = None, **overrides: object) -> bytes:
    report = provenance or _provenance()
    value: dict[str, object] = {
        "schema": "morpheus.ablation-result/v1",
        "execution_provenance": {
            "execution_provenance_sha256": report.execution_provenance_sha256,
            "implementation_commit_sha": report.implementation_commit_sha,
            "analysis_code_sha256": report.analysis_code_sha256,
            "test_code_sha256": report.test_code_sha256,
            "dependency_lock_sha256": report.dependency_lock_sha256,
            "ci_workflow_sha256": report.ci_workflow_sha256,
            "runtime_id": report.runtime_id,
        },
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _manifest_verification(raw: bytes) -> AblationResultEvidenceManifestVerification:
    return AblationResultEvidenceManifestVerification(
        validity_verification_sha256="67" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="78" * 32,
        disclosure_sha256="89" * 32,
        threats_sha256="9a" * 32,
        family_size=3,
        evidence_manifest_sha256=MANIFEST_SHA,
        manifest_verification_sha256=MANIFEST_VERIFICATION_SHA,
        evidence_manifest_consistency_verified=True,
    )


def test_result_provenance_consistency_binds_full_p36_identity_set() -> None:
    provenance = _provenance()
    raw = _document(provenance)
    report = verify_ablation_result_execution_provenance_consistency(
        _manifest_verification(raw), provenance, result_artifact=raw
    )
    assert report.execution_provenance_consistency_verified is True
    assert report.execution_provenance_sha256 == PROVENANCE_SHA
    assert report.analysis_code_sha256 == ANALYSIS_SHA
    assert report.test_code_sha256 == TEST_SHA
    assert report.dependency_lock_sha256 == LOCK_SHA
    assert report.ci_workflow_sha256 == WORKFLOW_SHA
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    truth = report.as_dict()["truth_boundary"]
    assert "files actually executed" in truth
    assert "no measurement validity" in truth


def test_result_provenance_identity_is_deterministic() -> None:
    provenance = _provenance()
    raw = _document(provenance)
    bound = _manifest_verification(raw)
    first = verify_ablation_result_execution_provenance_consistency(bound, provenance, result_artifact=raw)
    second = verify_ablation_result_execution_provenance_consistency(bound, provenance, result_artifact=raw)
    assert first.provenance_verification_sha256 == second.provenance_verification_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_provenance_sha256", "01" * 32),
        ("implementation_commit_sha", "02" * 20),
        ("analysis_code_sha256", "03" * 32),
        ("test_code_sha256", "04" * 32),
        ("dependency_lock_sha256", "05" * 32),
        ("ci_workflow_sha256", "06" * 32),
        ("runtime_id", "other-runtime"),
    ],
)
def test_result_provenance_rejects_declared_identity_drift(field: str, value: object) -> None:
    provenance = _provenance()
    document = json.loads(_document(provenance))
    document["execution_provenance"][field] = value
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=f"execution_provenance.{field}"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(raw), provenance, result_artifact=raw
        )


def test_result_provenance_rejects_manifest_chain_drift() -> None:
    provenance = _provenance()
    raw = _document(provenance)
    with pytest.raises(ValueError, match="evidence_manifest_sha256 must match"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(raw),
            replace(provenance, evidence_manifest_sha256="07" * 32),
            result_artifact=raw,
        )


def test_result_provenance_rejects_unverified_or_control_authorizing_inputs() -> None:
    provenance = _provenance()
    raw = _document(provenance)
    bound = _manifest_verification(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_execution_provenance_consistency(
            replace(bound, evidence_state="OTHER"), provenance, result_artifact=raw
        )
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_result_execution_provenance_consistency(
            replace(bound, evidence_manifest_consistency_verified=False), provenance, result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_execution_provenance_consistency(
            replace(bound, automatic_control_allowed=True), provenance, result_artifact=raw
        )
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_execution_provenance_consistency(
            bound, replace(provenance, evidence_state="OTHER"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="provenance_complete"):
        verify_ablation_result_execution_provenance_consistency(
            bound, replace(provenance, provenance_complete=False), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_execution_provenance_consistency(
            bound, replace(provenance, automatic_control_allowed=True), result_artifact=raw
        )


def test_result_provenance_rejects_malformed_declaration() -> None:
    provenance = _provenance()
    document = json.loads(_document(provenance))
    document["execution_provenance"] = "not-an-object"
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="must be an object"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(raw), provenance, result_artifact=raw
        )

    document = json.loads(_document(provenance))
    document["execution_provenance"]["analysis_code_sha256"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="hexadecimal string"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(raw), provenance, result_artifact=raw
        )


def test_result_provenance_rejects_byte_drift_and_control_promotion() -> None:
    provenance = _provenance()
    bound_raw = _document(provenance)
    changed = _document(provenance, note="changed")
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(bound_raw), provenance, result_artifact=changed
        )

    document = json.loads(bound_raw)
    document["automatic_control_allowed"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="explicitly set automatic_control_allowed to false"):
        verify_ablation_result_execution_provenance_consistency(
            _manifest_verification(raw), provenance, result_artifact=raw
        )
