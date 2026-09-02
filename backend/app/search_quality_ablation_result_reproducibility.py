"""Execution-provenance consistency verification for bound MORPHEUS ablation results.

P43 proves that a byte-bound result artifact reports one supplied P35 research-evidence manifest.
This P44 gate additionally requires the same result bytes to declare the complete P36 execution-
provenance identity set and verifies that set against one supplied P36 provenance report.

This is internal provenance/reporting-consistency evidence only. It does not prove that the bound
artifacts were actually executed, that the environment was clean, or that another party reproduced
the experiment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_reproducibility import (
    EVIDENCE_STATE as PROVENANCE_EVIDENCE_STATE,
    AblationExecutionProvenance,
)
from .search_quality_ablation_result_evidence_manifest import (
    EVIDENCE_STATE as RESULT_MANIFEST_EVIDENCE_STATE,
    AblationResultEvidenceManifestVerification,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_EXECUTION_PROVENANCE_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P43-verified result artifact declares the same complete P36 execution-provenance "
    "identity set as one supplied P36 provenance report, and that both bind the same P35 evidence manifest. It does not "
    "prove that those artifact identities were the files actually executed, that the workspace or runtime was clean, "
    "that all transitive system/compiler/hardware influences were captured, or that another party reproduced the result. "
    "Passing establishes no measurement validity, causal validity, benchmark/search superiority, publication-grade "
    "evidence, novelty, patentability, production readiness, or automatic-control authorization."
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
class AblationResultExecutionProvenanceVerification:
    manifest_verification_sha256: str
    result_artifact_sha256: str
    evidence_manifest_sha256: str
    execution_provenance_sha256: str
    implementation_commit_sha: str
    analysis_code_sha256: str
    test_code_sha256: str
    dependency_lock_sha256: str
    ci_workflow_sha256: str
    runtime_id: str
    provenance_verification_sha256: str
    execution_provenance_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_verification_sha256": self.manifest_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "analysis_code_sha256": self.analysis_code_sha256,
            "test_code_sha256": self.test_code_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "ci_workflow_sha256": self.ci_workflow_sha256,
            "runtime_id": self.runtime_id,
            "provenance_verification_sha256": self.provenance_verification_sha256,
            "execution_provenance_consistency_verified": self.execution_provenance_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_execution_provenance_consistency(
    manifest_verification: AblationResultEvidenceManifestVerification,
    execution_provenance: AblationExecutionProvenance,
    *,
    result_artifact: bytes | str,
) -> AblationResultExecutionProvenanceVerification:
    """Require a P43-bound result to report one complete supplied P36 provenance identity set exactly."""

    if manifest_verification.evidence_state != RESULT_MANIFEST_EVIDENCE_STATE:
        raise ValueError("manifest verification has an incompatible evidence_state")
    if manifest_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not manifest_verification.evidence_manifest_consistency_verified:
        raise ValueError("result evidence-manifest consistency must be verified before provenance verification")

    if execution_provenance.evidence_state != PROVENANCE_EVIDENCE_STATE:
        raise ValueError("execution provenance has an incompatible evidence_state")
    if execution_provenance.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not execution_provenance.provenance_complete:
        raise ValueError("execution provenance must have provenance_complete=true")

    manifest_verification_sha = _validated_hex(
        "manifest_verification_sha256", manifest_verification.manifest_verification_sha256
    )
    expected_result_sha = _validated_hex("result_artifact_sha256", manifest_verification.result_artifact_sha256)
    manifest_sha = _validated_hex("evidence_manifest_sha256", manifest_verification.evidence_manifest_sha256)
    provenance_manifest_sha = _validated_hex(
        "execution provenance evidence_manifest_sha256", execution_provenance.evidence_manifest_sha256
    )
    if provenance_manifest_sha != manifest_sha:
        raise ValueError("P36 evidence_manifest_sha256 must match the P43 verified evidence manifest")

    expected = {
        "execution_provenance_sha256": _validated_hex(
            "execution_provenance_sha256", execution_provenance.execution_provenance_sha256
        ),
        "implementation_commit_sha": _validated_hex(
            "implementation_commit_sha", execution_provenance.implementation_commit_sha, 40
        ),
        "analysis_code_sha256": _validated_hex("analysis_code_sha256", execution_provenance.analysis_code_sha256),
        "test_code_sha256": _validated_hex("test_code_sha256", execution_provenance.test_code_sha256),
        "dependency_lock_sha256": _validated_hex(
            "dependency_lock_sha256", execution_provenance.dependency_lock_sha256
        ),
        "ci_workflow_sha256": _validated_hex("ci_workflow_sha256", execution_provenance.ci_workflow_sha256),
        "runtime_id": _normalized_nonempty("runtime_id", execution_provenance.runtime_id),
    }

    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P43 result_artifact_sha256")

    declared = document.get("execution_provenance")
    if not isinstance(declared, dict):
        raise ValueError("result artifact execution_provenance must be an object")

    declared_values = {
        "execution_provenance_sha256": _validated_hex(
            "execution_provenance.execution_provenance_sha256", declared.get("execution_provenance_sha256")
        ),
        "implementation_commit_sha": _validated_hex(
            "execution_provenance.implementation_commit_sha", declared.get("implementation_commit_sha"), 40
        ),
        "analysis_code_sha256": _validated_hex(
            "execution_provenance.analysis_code_sha256", declared.get("analysis_code_sha256")
        ),
        "test_code_sha256": _validated_hex("execution_provenance.test_code_sha256", declared.get("test_code_sha256")),
        "dependency_lock_sha256": _validated_hex(
            "execution_provenance.dependency_lock_sha256", declared.get("dependency_lock_sha256")
        ),
        "ci_workflow_sha256": _validated_hex(
            "execution_provenance.ci_workflow_sha256", declared.get("ci_workflow_sha256")
        ),
        "runtime_id": _normalized_nonempty("execution_provenance.runtime_id", declared.get("runtime_id")),
    }
    for field, expected_value in expected.items():
        if declared_values[field] != expected_value:
            raise ValueError(f"result artifact execution_provenance.{field} does not match P36 execution provenance")

    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "manifest_verification_sha256": manifest_verification_sha,
        "result_artifact_sha256": actual_result_sha,
        "evidence_manifest_sha256": manifest_sha,
        **expected,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    verification_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultExecutionProvenanceVerification(
        manifest_verification_sha256=manifest_verification_sha,
        result_artifact_sha256=actual_result_sha,
        evidence_manifest_sha256=manifest_sha,
        execution_provenance_sha256=expected["execution_provenance_sha256"],
        implementation_commit_sha=expected["implementation_commit_sha"],
        analysis_code_sha256=expected["analysis_code_sha256"],
        test_code_sha256=expected["test_code_sha256"],
        dependency_lock_sha256=expected["dependency_lock_sha256"],
        ci_workflow_sha256=expected["ci_workflow_sha256"],
        runtime_id=expected["runtime_id"],
        provenance_verification_sha256=verification_sha,
        execution_provenance_consistency_verified=True,
    )
