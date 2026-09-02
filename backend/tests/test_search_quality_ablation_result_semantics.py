from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_result_artifact import AblationResultArtifactBinding
from app.search_quality_ablation_result_semantics import (
    EVIDENCE_STATE,
    RESULT_SCHEMA,
    verify_ablation_result_semantics,
)

COMMIT = "a1" * 20
ARTIFACT_SHA = "07" * 32
PROVENANCE_SHA = "b2" * 32
RUNTIME = "python-3.14-linux-x86_64"
KIND = "paired-ablation-family-result"


def _document(**overrides: object) -> bytes:
    value: dict[str, object] = {
        "schema": RESULT_SCHEMA,
        "artifact_verification_sha256": ARTIFACT_SHA,
        "execution_provenance_sha256": PROVENANCE_SHA,
        "implementation_commit_sha": COMMIT,
        "runtime_id": RUNTIME,
        "result_kind": KIND,
        "accepted": False,
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _binding(raw: bytes | None = None) -> AblationResultArtifactBinding:
    import hashlib

    artifact = raw if raw is not None else _document()
    return AblationResultArtifactBinding(
        artifact_verification_sha256=ARTIFACT_SHA,
        execution_provenance_sha256=PROVENANCE_SHA,
        implementation_commit_sha=COMMIT,
        runtime_id=RUNTIME,
        result_kind=KIND,
        media_type="application/json",
        result_artifact_sha256=hashlib.sha256(artifact).hexdigest(),
        result_binding_sha256="c3" * 32,
        result_bytes_bound=True,
    )


def test_semantics_verify_bound_json_without_promoting_claims() -> None:
    raw = _document()
    report = verify_ablation_result_semantics(_binding(raw), result_artifact=raw)
    assert report.semantic_consistency_verified is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    assert len(report.semantic_verification_sha256) == 64
    truth = report.as_dict()["truth_boundary"]
    assert "does not prove that the verified implementation ran" in truth
    assert "benchmark/search superiority" in truth


def test_semantics_are_deterministic_for_identical_bound_content() -> None:
    raw = _document()
    first = verify_ablation_result_semantics(_binding(raw), result_artifact=raw)
    second = verify_ablation_result_semantics(_binding(raw), result_artifact=raw.decode())
    assert first.semantic_verification_sha256 == second.semantic_verification_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_verification_sha256", "11" * 32),
        ("execution_provenance_sha256", "22" * 32),
        ("implementation_commit_sha", "33" * 20),
        ("runtime_id", "python-other"),
        ("result_kind", "other-result"),
    ],
)
def test_semantics_reject_declared_identity_drift(field: str, value: str) -> None:
    raw = _document(**{field: value})
    with pytest.raises(ValueError, match=f"{field} does not match"):
        verify_ablation_result_semantics(_binding(raw), result_artifact=raw)


def test_semantics_reject_bytes_that_do_not_match_p38_binding() -> None:
    bound = _document()
    changed = _document(accepted=True)
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_semantics(_binding(bound), result_artifact=changed)


def test_semantics_reject_wrong_schema_non_json_and_non_object_json() -> None:
    wrong_schema = _document(schema="morpheus.ablation-result/v2")
    with pytest.raises(ValueError, match="schema must equal"):
        verify_ablation_result_semantics(_binding(wrong_schema), result_artifact=wrong_schema)

    bad = b"not-json"
    with pytest.raises(ValueError, match="valid JSON"):
        verify_ablation_result_semantics(_binding(bad), result_artifact=bad)

    array = b"[]"
    with pytest.raises(ValueError, match="JSON must be an object"):
        verify_ablation_result_semantics(_binding(array), result_artifact=array)


def test_semantics_require_explicit_no_automatic_control() -> None:
    for value in (True, None, "false", 0):
        raw = _document(automatic_control_allowed=value)
        with pytest.raises(ValueError, match="explicitly set automatic_control_allowed to false"):
            verify_ablation_result_semantics(_binding(raw), result_artifact=raw)


def test_semantics_reject_unbound_incompatible_or_non_json_binding() -> None:
    raw = _document()
    binding = _binding(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_semantics(replace(binding, evidence_state="OTHER"), result_artifact=raw)
    with pytest.raises(ValueError, match="must be bound"):
        verify_ablation_result_semantics(replace(binding, result_bytes_bound=False), result_artifact=raw)
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_semantics(replace(binding, automatic_control_allowed=True), result_artifact=raw)
    with pytest.raises(ValueError, match="application/json"):
        verify_ablation_result_semantics(replace(binding, media_type="text/plain"), result_artifact=raw)


def test_semantics_reject_malformed_declared_or_bound_identity() -> None:
    raw = _document(artifact_verification_sha256="bad")
    with pytest.raises(ValueError, match="declared artifact_verification_sha256"):
        verify_ablation_result_semantics(_binding(raw), result_artifact=raw)

    good = _document()
    with pytest.raises(ValueError, match="result_binding_sha256"):
        verify_ablation_result_semantics(replace(_binding(good), result_binding_sha256="bad"), result_artifact=good)
