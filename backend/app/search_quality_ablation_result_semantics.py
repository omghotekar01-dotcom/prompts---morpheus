"""Semantic consistency verification for bound MORPHEUS ablation result artifacts.

P38 binds exact result bytes to byte-verified provenance. This gate additionally verifies that a
JSON result artifact explicitly declares provenance identities consistent with that P38 binding.
It does not prove that the verified implementation produced or captured the result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_result_artifact import (
    EVIDENCE_STATE as RESULT_BINDING_EVIDENCE_STATE,
    AblationResultArtifactBinding,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_SEMANTICS"
RESULT_SCHEMA = "morpheus.ablation-result/v1"
TRUTH_BOUNDARY = (
    "This gate proves only that one supplied JSON result artifact is byte-bound by P38 and that its declared provenance "
    "identities are semantically consistent with that binding. It does not prove that the verified implementation ran, "
    "that the process emitted or directly captured these bytes, that measurements are valid or independent, or that an "
    "external party reproduced the result. Passing establishes no causal validity, benchmark/search superiority, novelty, "
    "patentability, publication-grade evidence, production readiness, or automatic-control authorization."
)


def _validated_hex(name: str, value: str, length: int) -> str:
    normalized = value.strip().casefold()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    return normalized


def _normalized_nonempty(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _json_object(result_artifact: bytes | str) -> tuple[bytes, dict[str, Any]]:
    if isinstance(result_artifact, str):
        raw = result_artifact.encode("utf-8")
    elif isinstance(result_artifact, bytes):
        raw = result_artifact
    else:
        raise TypeError("result_artifact must be bytes or str")
    if not raw:
        raise ValueError("result_artifact cannot be empty")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("result_artifact must be valid UTF-8 JSON") from exc
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("result_artifact must contain valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("result_artifact JSON must be an object")
    return raw, value


@dataclass(frozen=True)
class AblationResultSemanticVerification:
    result_binding_sha256: str
    result_artifact_sha256: str
    artifact_verification_sha256: str
    execution_provenance_sha256: str
    implementation_commit_sha: str
    runtime_id: str
    result_kind: str
    schema: str
    semantic_verification_sha256: str
    semantic_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "result_binding_sha256": self.result_binding_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "artifact_verification_sha256": self.artifact_verification_sha256,
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "runtime_id": self.runtime_id,
            "result_kind": self.result_kind,
            "schema": self.schema,
            "semantic_verification_sha256": self.semantic_verification_sha256,
            "semantic_consistency_verified": self.semantic_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_semantics(
    binding: AblationResultArtifactBinding,
    *,
    result_artifact: bytes | str,
) -> AblationResultSemanticVerification:
    """Verify that a bound JSON result declares the same provenance identities as its P38 binding."""

    if binding.evidence_state != RESULT_BINDING_EVIDENCE_STATE:
        raise ValueError("result binding has an incompatible evidence_state")
    if binding.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not binding.result_bytes_bound:
        raise ValueError("result bytes must be bound before semantic verification")
    if binding.media_type.casefold() != "application/json":
        raise ValueError("semantic verification requires application/json result media type")

    result_binding_sha256 = _validated_hex("result_binding_sha256", binding.result_binding_sha256, 64)
    expected_result_sha256 = _validated_hex("result_artifact_sha256", binding.result_artifact_sha256, 64)
    artifact_verification_sha256 = _validated_hex(
        "artifact_verification_sha256", binding.artifact_verification_sha256, 64
    )
    execution_provenance_sha256 = _validated_hex(
        "execution_provenance_sha256", binding.execution_provenance_sha256, 64
    )
    implementation_commit_sha = _validated_hex("implementation_commit_sha", binding.implementation_commit_sha, 40)
    runtime_id = _normalized_nonempty("runtime_id", binding.runtime_id)
    result_kind = _normalized_nonempty("result_kind", binding.result_kind)

    raw, document = _json_object(result_artifact)
    actual_result_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_result_sha256 != expected_result_sha256:
        raise ValueError("result_artifact bytes do not match the P38 result_artifact_sha256")

    schema = _normalized_nonempty("schema", document.get("schema"))
    if schema != RESULT_SCHEMA:
        raise ValueError(f"schema must equal {RESULT_SCHEMA}")

    declared = {
        "artifact_verification_sha256": _validated_hex(
            "declared artifact_verification_sha256",
            _normalized_nonempty("artifact_verification_sha256", document.get("artifact_verification_sha256")),
            64,
        ),
        "execution_provenance_sha256": _validated_hex(
            "declared execution_provenance_sha256",
            _normalized_nonempty("execution_provenance_sha256", document.get("execution_provenance_sha256")),
            64,
        ),
        "implementation_commit_sha": _validated_hex(
            "declared implementation_commit_sha",
            _normalized_nonempty("implementation_commit_sha", document.get("implementation_commit_sha")),
            40,
        ),
        "runtime_id": _normalized_nonempty("runtime_id", document.get("runtime_id")),
        "result_kind": _normalized_nonempty("result_kind", document.get("result_kind")),
    }
    expected = {
        "artifact_verification_sha256": artifact_verification_sha256,
        "execution_provenance_sha256": execution_provenance_sha256,
        "implementation_commit_sha": implementation_commit_sha,
        "runtime_id": runtime_id,
        "result_kind": result_kind,
    }
    for field, expected_value in expected.items():
        if declared[field] != expected_value:
            raise ValueError(f"result artifact {field} does not match the P38 binding")

    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "result_binding_sha256": result_binding_sha256,
        "result_artifact_sha256": actual_result_sha256,
        "artifact_verification_sha256": artifact_verification_sha256,
        "execution_provenance_sha256": execution_provenance_sha256,
        "implementation_commit_sha": implementation_commit_sha,
        "runtime_id": runtime_id,
        "result_kind": result_kind,
        "schema": schema,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    semantic_verification_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationResultSemanticVerification(
        result_binding_sha256=result_binding_sha256,
        result_artifact_sha256=actual_result_sha256,
        artifact_verification_sha256=artifact_verification_sha256,
        execution_provenance_sha256=execution_provenance_sha256,
        implementation_commit_sha=implementation_commit_sha,
        runtime_id=runtime_id,
        result_kind=result_kind,
        schema=schema,
        semantic_verification_sha256=semantic_verification_sha256,
        semantic_consistency_verified=True,
    )
