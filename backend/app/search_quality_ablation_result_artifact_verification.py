"""Artifact-byte verification consistency for bound MORPHEUS ablation results.

P44 verifies that a byte-bound result reports one supplied P36 execution-provenance identity set.
This P45 gate additionally requires the result to declare the P37 artifact-verification identity and
checks that one supplied P37 report verifies the same artifact identities already accepted by P44.

This is internal provenance/reporting-consistency evidence only. It does not prove that an experiment
process executed the verified bytes, that the environment was complete or clean, or that another
party independently reproduced the result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_artifact_verification import (
    EVIDENCE_STATE as ARTIFACT_EVIDENCE_STATE,
    AblationArtifactVerification,
)
from .search_quality_ablation_result_reproducibility import (
    EVIDENCE_STATE as RESULT_PROVENANCE_EVIDENCE_STATE,
    AblationResultExecutionProvenanceVerification,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_ARTIFACT_BYTE_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P44-verified result artifact declares one supplied P37 artifact-verification identity, "
    "and that the P37 report agrees with P44 on the execution-provenance, implementation, analysis-code, test-code, "
    "dependency-lock, CI-workflow, and runtime identities. It does not prove that an experiment process actually executed "
    "those verified bytes, that the repository/runtime was clean or complete, that transitive compiler/OS/hardware effects "
    "were captured, or that another party reproduced the result. Passing establishes no measurement validity, causal "
    "validity, benchmark/search superiority, publication-grade evidence, novelty, patentability, production readiness, "
    "or automatic-control authorization."
)


def _validated_hex(name: str, value: object, length: int = 64) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a hexadecimal string")
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
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("result_artifact JSON must be an object")
    return raw, value


@dataclass(frozen=True)
class AblationResultArtifactVerificationConsistency:
    provenance_verification_sha256: str
    result_artifact_sha256: str
    artifact_verification_sha256: str
    execution_provenance_sha256: str
    implementation_commit_sha: str
    analysis_code_sha256: str
    test_code_sha256: str
    dependency_lock_sha256: str
    ci_workflow_sha256: str
    runtime_id: str
    result_artifact_verification_sha256: str
    artifact_byte_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "provenance_verification_sha256": self.provenance_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "artifact_verification_sha256": self.artifact_verification_sha256,
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "analysis_code_sha256": self.analysis_code_sha256,
            "test_code_sha256": self.test_code_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "ci_workflow_sha256": self.ci_workflow_sha256,
            "runtime_id": self.runtime_id,
            "result_artifact_verification_sha256": self.result_artifact_verification_sha256,
            "artifact_byte_consistency_verified": self.artifact_byte_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_artifact_byte_consistency(
    provenance_verification: AblationResultExecutionProvenanceVerification,
    artifact_verification: AblationArtifactVerification,
    *,
    result_artifact: bytes | str,
) -> AblationResultArtifactVerificationConsistency:
    """Fail closed unless a P44-bound result and one P37 report bind exactly the same artifacts."""

    if provenance_verification.evidence_state != RESULT_PROVENANCE_EVIDENCE_STATE:
        raise ValueError("result provenance verification has an incompatible evidence_state")
    if provenance_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not provenance_verification.execution_provenance_consistency_verified:
        raise ValueError("P44 execution-provenance consistency must be verified before P37 consistency")

    if artifact_verification.evidence_state != ARTIFACT_EVIDENCE_STATE:
        raise ValueError("artifact verification has an incompatible evidence_state")
    if artifact_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not artifact_verification.artifact_bytes_verified:
        raise ValueError("P37 artifact bytes must be verified")

    expected_result_sha = _validated_hex("result_artifact_sha256", provenance_verification.result_artifact_sha256)
    provenance_verification_sha = _validated_hex(
        "provenance_verification_sha256", provenance_verification.provenance_verification_sha256
    )
    artifact_verification_sha = _validated_hex(
        "artifact_verification_sha256", artifact_verification.artifact_verification_sha256
    )

    fields: tuple[tuple[str, int], ...] = (
        ("execution_provenance_sha256", 64),
        ("implementation_commit_sha", 40),
        ("analysis_code_sha256", 64),
        ("test_code_sha256", 64),
        ("dependency_lock_sha256", 64),
        ("ci_workflow_sha256", 64),
    )
    verified: dict[str, str] = {}
    for field, length in fields:
        p44_value = _validated_hex(f"P44 {field}", getattr(provenance_verification, field), length)
        p37_value = _validated_hex(f"P37 {field}", getattr(artifact_verification, field), length)
        if p44_value != p37_value:
            raise ValueError(f"P37 {field} does not match P44 result provenance verification")
        verified[field] = p44_value

    p44_runtime = _normalized_nonempty("P44 runtime_id", provenance_verification.runtime_id)
    p37_runtime = _normalized_nonempty("P37 runtime_id", artifact_verification.runtime_id)
    if p44_runtime != p37_runtime:
        raise ValueError("P37 runtime_id does not match P44 result provenance verification")

    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P44 result_artifact_sha256")

    declared = document.get("artifact_verification")
    if not isinstance(declared, dict):
        raise ValueError("result artifact artifact_verification must be an object")
    declared_sha = _validated_hex(
        "artifact_verification.artifact_verification_sha256", declared.get("artifact_verification_sha256")
    )
    if declared_sha != artifact_verification_sha:
        raise ValueError("result artifact artifact_verification_sha256 does not match P37 artifact verification")
    if declared.get("artifact_bytes_verified") is not True:
        raise ValueError("result artifact must explicitly declare artifact_bytes_verified=true")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "provenance_verification_sha256": provenance_verification_sha,
        "result_artifact_sha256": actual_result_sha,
        "artifact_verification_sha256": artifact_verification_sha,
        **verified,
        "runtime_id": p44_runtime,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    result_verification_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultArtifactVerificationConsistency(
        provenance_verification_sha256=provenance_verification_sha,
        result_artifact_sha256=actual_result_sha,
        artifact_verification_sha256=artifact_verification_sha,
        execution_provenance_sha256=verified["execution_provenance_sha256"],
        implementation_commit_sha=verified["implementation_commit_sha"],
        analysis_code_sha256=verified["analysis_code_sha256"],
        test_code_sha256=verified["test_code_sha256"],
        dependency_lock_sha256=verified["dependency_lock_sha256"],
        ci_workflow_sha256=verified["ci_workflow_sha256"],
        runtime_id=p44_runtime,
        result_artifact_verification_sha256=result_verification_sha,
        artifact_byte_consistency_verified=True,
    )
