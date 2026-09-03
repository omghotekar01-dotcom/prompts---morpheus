from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_artifact_verification import AblationArtifactVerification
from app.search_quality_ablation_result_artifact_verification import (
    EVIDENCE_STATE,
    verify_ablation_result_artifact_byte_consistency,
)
from app.search_quality_ablation_result_reproducibility import (
    AblationResultExecutionProvenanceVerification,
)

COMMIT = "a1" * 20
EXECUTION = "b2" * 32
ANALYSIS = "c3" * 32
TESTS = "d4" * 32
LOCK = "e5" * 32
WORKFLOW = "f6" * 32
ARTIFACT_VERIFICATION = "17" * 32
P44_VERIFICATION = "28" * 32
MANIFEST = "39" * 32
RUNTIME = "python-3.14-linux-x86_64"


def _artifact(*, artifact_sha: str = ARTIFACT_VERIFICATION, bytes_verified: object = True) -> bytes:
    return json.dumps(
        {
            "schema": "morpheus.ablation-result/v1",
            "artifact_verification": {
                "artifact_verification_sha256": artifact_sha,
                "artifact_bytes_verified": bytes_verified,
            },
            "automatic_control_allowed": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _p44(raw: bytes) -> AblationResultExecutionProvenanceVerification:
    return AblationResultExecutionProvenanceVerification(
        manifest_verification_sha256="4a" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        evidence_manifest_sha256=MANIFEST,
        execution_provenance_sha256=EXECUTION,
        implementation_commit_sha=COMMIT,
        analysis_code_sha256=ANALYSIS,
        test_code_sha256=TESTS,
        dependency_lock_sha256=LOCK,
        ci_workflow_sha256=WORKFLOW,
        runtime_id=RUNTIME,
        provenance_verification_sha256=P44_VERIFICATION,
        execution_provenance_consistency_verified=True,
    )


def _p37() -> AblationArtifactVerification:
    return AblationArtifactVerification(
        execution_provenance_sha256=EXECUTION,
        implementation_commit_sha=COMMIT,
        analysis_code_sha256=ANALYSIS,
        test_code_sha256=TESTS,
        dependency_lock_sha256=LOCK,
        ci_workflow_sha256=WORKFLOW,
        runtime_id=RUNTIME,
        artifact_verification_sha256=ARTIFACT_VERIFICATION,
        artifact_bytes_verified=True,
    )


def test_p45_binds_verified_artifact_bytes_deterministically() -> None:
    raw = _artifact()
    first = verify_ablation_result_artifact_byte_consistency(_p44(raw), _p37(), result_artifact=raw)
    second = verify_ablation_result_artifact_byte_consistency(_p44(raw), _p37(), result_artifact=raw.decode())

    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.artifact_byte_consistency_verified is True
    assert first.automatic_control_allowed is False
    assert first.artifact_verification_sha256 == ARTIFACT_VERIFICATION
    assert len(first.result_artifact_verification_sha256) == 64


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("execution_provenance_sha256", "01" * 32),
        ("implementation_commit_sha", "02" * 20),
        ("analysis_code_sha256", "03" * 32),
        ("test_code_sha256", "04" * 32),
        ("dependency_lock_sha256", "05" * 32),
        ("ci_workflow_sha256", "06" * 32),
        ("runtime_id", "different-runtime"),
    ],
)
def test_p45_rejects_p37_p44_identity_drift(field: str, replacement: str) -> None:
    raw = _artifact()
    with pytest.raises(ValueError, match=field):
        verify_ablation_result_artifact_byte_consistency(
            _p44(raw), replace(_p37(), **{field: replacement}), result_artifact=raw
        )


def test_p45_rejects_declared_artifact_verification_drift() -> None:
    raw = _artifact(artifact_sha="07" * 32)
    with pytest.raises(ValueError, match="artifact_verification_sha256"):
        verify_ablation_result_artifact_byte_consistency(_p44(raw), _p37(), result_artifact=raw)


def test_p45_rejects_false_byte_verification_declaration() -> None:
    raw = _artifact(bytes_verified=False)
    with pytest.raises(ValueError, match="artifact_bytes_verified=true"):
        verify_ablation_result_artifact_byte_consistency(_p44(raw), _p37(), result_artifact=raw)


def test_p45_rejects_result_byte_drift() -> None:
    raw = _artifact()
    with pytest.raises(ValueError, match="result_artifact bytes"):
        verify_ablation_result_artifact_byte_consistency(_p44(raw), _p37(), result_artifact=raw + b" ")


def test_p45_rejects_incompatible_incomplete_or_control_authorizing_evidence() -> None:
    raw = _artifact()
    with pytest.raises(ValueError, match="incompatible evidence_state"):
        verify_ablation_result_artifact_byte_consistency(
            replace(_p44(raw), evidence_state="OTHER"), _p37(), result_artifact=raw
        )
    with pytest.raises(ValueError, match="P44 execution-provenance consistency"):
        verify_ablation_result_artifact_byte_consistency(
            replace(_p44(raw), execution_provenance_consistency_verified=False), _p37(), result_artifact=raw
        )
    with pytest.raises(ValueError, match="P37 artifact bytes"):
        verify_ablation_result_artifact_byte_consistency(
            _p44(raw), replace(_p37(), artifact_bytes_verified=False), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_artifact_byte_consistency(
            _p44(raw), replace(_p37(), automatic_control_allowed=True), result_artifact=raw
        )


def test_p45_normalizes_hex_case_and_outer_whitespace() -> None:
    raw = _artifact(artifact_sha=ARTIFACT_VERIFICATION.upper())
    report = verify_ablation_result_artifact_byte_consistency(
        replace(
            _p44(raw),
            implementation_commit_sha="  " + COMMIT.upper() + "  ",
            execution_provenance_sha256="  " + EXECUTION.upper() + "  ",
        ),
        replace(
            _p37(),
            implementation_commit_sha="  " + COMMIT.upper() + "  ",
            execution_provenance_sha256="  " + EXECUTION.upper() + "  ",
            artifact_verification_sha256="  " + ARTIFACT_VERIFICATION.upper() + "  ",
        ),
        result_artifact=raw,
    )
    assert report.implementation_commit_sha == COMMIT
    assert report.execution_provenance_sha256 == EXECUTION
    assert report.artifact_verification_sha256 == ARTIFACT_VERIFICATION
