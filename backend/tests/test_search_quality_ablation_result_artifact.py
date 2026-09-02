from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.search_quality_ablation_artifact_verification import AblationArtifactVerification
from app.search_quality_ablation_result_artifact import (
    EVIDENCE_STATE,
    bind_ablation_result_artifact,
)

RESULT = b'{"accepted":false,"mean_regret":0.031}\n'
COMMIT = "a1" * 20
RUNTIME = "python-3.14-linux-x86_64"


def _verification() -> AblationArtifactVerification:
    return AblationArtifactVerification(
        execution_provenance_sha256="b2" * 32,
        implementation_commit_sha=COMMIT,
        analysis_code_sha256="c3" * 32,
        test_code_sha256="d4" * 32,
        dependency_lock_sha256="e5" * 32,
        ci_workflow_sha256="f6" * 32,
        runtime_id=RUNTIME,
        artifact_verification_sha256="07" * 32,
        artifact_bytes_verified=True,
    )


def _bind(verification: AblationArtifactVerification | None = None, **overrides: object):
    values: dict[str, object] = {
        "result_artifact": RESULT,
        "result_kind": "paired-ablation-family-result",
        "media_type": "application/json",
    }
    values.update(overrides)
    return bind_ablation_result_artifact(verification or _verification(), **values)  # type: ignore[arg-type]


def test_result_binding_hashes_exact_bytes_without_promoting_research_claims() -> None:
    report = _bind()
    assert report.result_bytes_bound is True
    assert report.result_artifact_sha256 == hashlib.sha256(RESULT).hexdigest()
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    assert len(report.result_binding_sha256) == 64
    payload = report.as_dict()
    assert "does not prove that the verified code produced the result" in payload["truth_boundary"]
    assert "independently reproduced" in payload["truth_boundary"]


def test_result_binding_is_deterministic_and_accepts_equivalent_utf8_text() -> None:
    first = _bind()
    second = _bind(result_artifact=RESULT.decode())
    assert first.result_artifact_sha256 == second.result_artifact_sha256
    assert first.result_binding_sha256 == second.result_binding_sha256


def test_result_content_or_declared_context_changes_binding_identity() -> None:
    baseline = _bind()
    changed_result = _bind(result_artifact=b'{"accepted":true}\n')
    changed_kind = _bind(result_kind="single-ablation-result")
    changed_media = _bind(media_type="text/plain")
    assert changed_result.result_binding_sha256 != baseline.result_binding_sha256
    assert changed_kind.result_binding_sha256 != baseline.result_binding_sha256
    assert changed_media.result_binding_sha256 != baseline.result_binding_sha256


def test_result_binding_normalizes_hex_identity_and_media_type_case() -> None:
    verification = replace(
        _verification(),
        artifact_verification_sha256="  " + ("07" * 32).upper() + "  ",
        execution_provenance_sha256="  " + ("B2" * 32) + "  ",
        implementation_commit_sha="  " + COMMIT.upper() + "  ",
    )
    report = _bind(verification, media_type="  Application/JSON  ")
    assert report.artifact_verification_sha256 == "07" * 32
    assert report.execution_provenance_sha256 == "b2" * 32
    assert report.implementation_commit_sha == COMMIT
    assert report.media_type == "application/json"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("artifact_verification_sha256", "bad", "artifact_verification_sha256"),
        ("execution_provenance_sha256", "bad", "execution_provenance_sha256"),
        ("implementation_commit_sha", "bad", "implementation_commit_sha"),
        ("runtime_id", "   ", "runtime_id"),
    ],
)
def test_result_binding_rejects_malformed_bound_identity(field: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _bind(replace(_verification(), **{field: value}))


def test_result_binding_rejects_empty_or_invalid_result_inputs() -> None:
    with pytest.raises(ValueError, match="result_artifact cannot be empty"):
        _bind(result_artifact=b"")
    with pytest.raises(TypeError, match="result_artifact must be bytes or str"):
        _bind(result_artifact=123)
    with pytest.raises(ValueError, match="result_kind"):
        _bind(result_kind="  ")
    with pytest.raises(ValueError, match="media_type"):
        _bind(media_type="  ")


def test_result_binding_rejects_incompatible_unverified_or_control_authorizing_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_state"):
        _bind(replace(_verification(), evidence_state="OTHER"))
    with pytest.raises(ValueError, match="artifact bytes must be verified"):
        _bind(replace(_verification(), artifact_bytes_verified=False))
    with pytest.raises(ValueError, match="automatic control"):
        _bind(replace(_verification(), automatic_control_allowed=True))
