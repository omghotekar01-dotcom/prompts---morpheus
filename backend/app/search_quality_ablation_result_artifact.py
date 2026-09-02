"""Deterministic result-artifact binding for MORPHEUS ablation research evidence.

This gate binds the exact bytes of one caller-supplied ablation result artifact to an already
byte-verified MORPHEUS execution-provenance identity. It creates a stable content identity only;
it does not prove that the bound result was produced by executing the verified artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .search_quality_ablation_artifact_verification import (
    EVIDENCE_STATE as ARTIFACT_EVIDENCE_STATE,
    AblationArtifactVerification,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_BOUND_ABLATION_RESULT_ARTIFACT"
TRUTH_BOUNDARY = (
    "This gate proves only deterministic content binding between one supplied result artifact and one already "
    "byte-verified MORPHEUS ablation provenance identity. It does not prove that the verified code produced the result, "
    "that the result was captured directly from an experiment process, that timestamps/run labels are externally "
    "trusted, that the execution environment was clean, or that another party independently reproduced the result. "
    "Passing does not establish publication-grade evidence, causal validity, benchmark/search superiority, novelty, "
    "patentability, production readiness, or automatic-control authorization."
)


def _validated_hex(name: str, value: str, length: int) -> str:
    normalized = value.strip().casefold()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    return normalized


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _result_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        result = value
    elif isinstance(value, str):
        result = value.encode("utf-8")
    else:
        raise TypeError("result_artifact must be bytes or str")
    if not result:
        raise ValueError("result_artifact cannot be empty")
    return result


@dataclass(frozen=True)
class AblationResultArtifactBinding:
    artifact_verification_sha256: str
    execution_provenance_sha256: str
    implementation_commit_sha: str
    runtime_id: str
    result_kind: str
    media_type: str
    result_artifact_sha256: str
    result_binding_sha256: str
    result_bytes_bound: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_verification_sha256": self.artifact_verification_sha256,
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "runtime_id": self.runtime_id,
            "result_kind": self.result_kind,
            "media_type": self.media_type,
            "result_artifact_sha256": self.result_artifact_sha256,
            "result_binding_sha256": self.result_binding_sha256,
            "result_bytes_bound": self.result_bytes_bound,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def bind_ablation_result_artifact(
    verification: AblationArtifactVerification,
    *,
    result_artifact: bytes | str,
    result_kind: str,
    media_type: str,
) -> AblationResultArtifactBinding:
    """Bind exact supplied result bytes to one complete byte-verified provenance report."""

    if verification.evidence_state != ARTIFACT_EVIDENCE_STATE:
        raise ValueError("artifact verification has an incompatible evidence_state")
    if verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not verification.artifact_bytes_verified:
        raise ValueError("artifact bytes must be verified before a result artifact can be bound")

    artifact_verification_sha256 = _validated_hex(
        "artifact_verification_sha256", verification.artifact_verification_sha256, 64
    )
    execution_provenance_sha256 = _validated_hex(
        "execution_provenance_sha256", verification.execution_provenance_sha256, 64
    )
    implementation_commit_sha = _validated_hex(
        "implementation_commit_sha", verification.implementation_commit_sha, 40
    )
    runtime_id = _normalized_nonempty("runtime_id", verification.runtime_id)
    result_kind = _normalized_nonempty("result_kind", result_kind)
    media_type = _normalized_nonempty("media_type", media_type).casefold()
    raw_result = _result_bytes(result_artifact)
    result_artifact_sha256 = hashlib.sha256(raw_result).hexdigest()

    payload = {
        "artifact_verification_sha256": artifact_verification_sha256,
        "execution_provenance_sha256": execution_provenance_sha256,
        "implementation_commit_sha": implementation_commit_sha,
        "runtime_id": runtime_id,
        "result_kind": result_kind,
        "media_type": media_type,
        "result_artifact_sha256": result_artifact_sha256,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    result_binding_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationResultArtifactBinding(
        artifact_verification_sha256=artifact_verification_sha256,
        execution_provenance_sha256=execution_provenance_sha256,
        implementation_commit_sha=implementation_commit_sha,
        runtime_id=runtime_id,
        result_kind=result_kind,
        media_type=media_type,
        result_artifact_sha256=result_artifact_sha256,
        result_binding_sha256=result_binding_sha256,
        result_bytes_bound=True,
    )
