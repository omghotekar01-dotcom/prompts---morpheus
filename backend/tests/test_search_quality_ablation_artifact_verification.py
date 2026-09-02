from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.search_quality_ablation_artifact_verification import (
    EVIDENCE_STATE,
    verify_ablation_provenance_artifacts,
)
from app.search_quality_ablation_reproducibility import AblationExecutionProvenance

ANALYSIS = b"analysis-code-v1\n"
TESTS = b"test-code-v1\n"
LOCK = b"dependency-lock-v1\n"
WORKFLOW = b"ci-workflow-v1\n"
COMMIT = "a1" * 20
RUNTIME = "python-3.14-linux-x86_64"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _provenance() -> AblationExecutionProvenance:
    return AblationExecutionProvenance(
        evidence_manifest_sha256="b2" * 32,
        implementation_commit_sha=COMMIT,
        analysis_code_sha256=_digest(ANALYSIS),
        test_code_sha256=_digest(TESTS),
        dependency_lock_sha256=_digest(LOCK),
        ci_workflow_sha256=_digest(WORKFLOW),
        runtime_id=RUNTIME,
        execution_provenance_sha256="c3" * 32,
        provenance_complete=True,
    )


def _verify(provenance: AblationExecutionProvenance | None = None, **overrides: object):
    values: dict[str, object] = {
        "implementation_commit_sha": COMMIT,
        "analysis_code": ANALYSIS,
        "test_code": TESTS,
        "dependency_lock": LOCK,
        "ci_workflow": WORKFLOW,
        "runtime_id": RUNTIME,
    }
    values.update(overrides)
    return verify_ablation_provenance_artifacts(provenance or _provenance(), **values)  # type: ignore[arg-type]


def test_verification_hashes_presented_bytes_without_promoting_research_claims() -> None:
    report = _verify()
    assert report.artifact_bytes_verified is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    assert report.analysis_code_sha256 == _digest(ANALYSIS)
    assert len(report.artifact_verification_sha256) == 64
    payload = report.as_dict()
    assert "does not prove that an experiment process executed these exact bytes" in payload["truth_boundary"]
    assert "independent reproduction" in payload["truth_boundary"]


def test_verification_is_deterministic_and_accepts_equivalent_utf8_text() -> None:
    first = _verify()
    second = _verify(
        analysis_code=ANALYSIS.decode(),
        test_code=TESTS.decode(),
        dependency_lock=LOCK.decode(),
        ci_workflow=WORKFLOW.decode(),
    )
    assert first.artifact_verification_sha256 == second.artifact_verification_sha256


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("analysis_code", b"changed-analysis", "analysis_code_sha256"),
        ("test_code", b"changed-tests", "test_code_sha256"),
        ("dependency_lock", b"changed-lock", "dependency_lock_sha256"),
        ("ci_workflow", b"changed-workflow", "ci_workflow_sha256"),
    ],
)
def test_verification_rejects_any_artifact_content_drift(field: str, replacement: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _verify(**{field: replacement})


def test_verification_rejects_commit_or_runtime_drift() -> None:
    with pytest.raises(ValueError, match="implementation_commit_sha does not match"):
        _verify(implementation_commit_sha="d4" * 20)
    with pytest.raises(ValueError, match="runtime_id does not match"):
        _verify(runtime_id="python-3.14-windows-amd64")


def test_verification_rejects_malformed_bound_digests_and_wrong_input_type() -> None:
    with pytest.raises(ValueError, match="execution_provenance_sha256"):
        _verify(replace(_provenance(), execution_provenance_sha256="bad"))
    with pytest.raises(ValueError, match="provenance analysis_code_sha256"):
        _verify(replace(_provenance(), analysis_code_sha256="bad"))
    with pytest.raises(TypeError, match="analysis_code must be bytes or str"):
        _verify(analysis_code=123)


def test_verification_rejects_incompatible_incomplete_or_control_authorizing_provenance() -> None:
    with pytest.raises(ValueError, match="evidence_state"):
        _verify(replace(_provenance(), evidence_state="OTHER"))
    with pytest.raises(ValueError, match="complete"):
        _verify(replace(_provenance(), provenance_complete=False))
    with pytest.raises(ValueError, match="automatic control"):
        _verify(replace(_provenance(), automatic_control_allowed=True))


def test_verification_normalizes_hex_identity_case_and_outer_whitespace() -> None:
    provenance = replace(
        _provenance(),
        implementation_commit_sha="  " + COMMIT.upper() + "  ",
        execution_provenance_sha256="  " + ("C3" * 32) + "  ",
    )
    report = _verify(provenance, implementation_commit_sha="  " + COMMIT.upper() + "  ")
    assert report.implementation_commit_sha == COMMIT
    assert report.execution_provenance_sha256 == "c3" * 32
