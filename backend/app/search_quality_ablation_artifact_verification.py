"""Byte-level verification for MORPHEUS ablation execution-provenance artifacts.

This gate closes one narrow provenance gap: caller-supplied digests are checked against the
actual artifact bytes presented to this verifier. It does not establish that those bytes were
what an experiment process executed, nor does it provide external archival or attestation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .search_quality_ablation_reproducibility import (
    EVIDENCE_STATE as PROVENANCE_EVIDENCE_STATE,
    AblationExecutionProvenance,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_PROVENANCE_ARTIFACT_BYTES"
TRUTH_BOUNDARY = (
    "This gate proves only that artifact bytes supplied to this verifier hash to the identities already bound in one "
    "complete MORPHEUS ablation execution-provenance report, and that the supplied implementation commit/runtime "
    "identities match that report. It does not prove that an experiment process executed these exact bytes, that the "
    "repository or environment was clean, that transitive tools/hardware are fully captured, or that the artifacts were "
    "externally archived, timestamped, signed, or independently attested. Passing does not establish independent "
    "reproduction, publication-grade evidence, causal validity, benchmark/search superiority, novelty, patentability, "
    "production readiness, or automatic-control authorization."
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


def _artifact_bytes(name: str, value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"{name} must be bytes or str")


def _sha256(name: str, value: bytes | str) -> str:
    return hashlib.sha256(_artifact_bytes(name, value)).hexdigest()


@dataclass(frozen=True)
class AblationArtifactVerification:
    execution_provenance_sha256: str
    implementation_commit_sha: str
    analysis_code_sha256: str
    test_code_sha256: str
    dependency_lock_sha256: str
    ci_workflow_sha256: str
    runtime_id: str
    artifact_verification_sha256: str
    artifact_bytes_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "analysis_code_sha256": self.analysis_code_sha256,
            "test_code_sha256": self.test_code_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "ci_workflow_sha256": self.ci_workflow_sha256,
            "runtime_id": self.runtime_id,
            "artifact_verification_sha256": self.artifact_verification_sha256,
            "artifact_bytes_verified": self.artifact_bytes_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_provenance_artifacts(
    provenance: AblationExecutionProvenance,
    *,
    implementation_commit_sha: str,
    analysis_code: bytes | str,
    test_code: bytes | str,
    dependency_lock: bytes | str,
    ci_workflow: bytes | str,
    runtime_id: str,
) -> AblationArtifactVerification:
    """Fail closed unless supplied artifact bytes exactly satisfy a complete provenance report."""

    if provenance.evidence_state != PROVENANCE_EVIDENCE_STATE:
        raise ValueError("provenance has an incompatible evidence_state")
    if provenance.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not provenance.provenance_complete:
        raise ValueError("provenance must be complete before artifact bytes can be verified")

    execution_provenance_sha256 = _validated_hex(
        "execution_provenance_sha256", provenance.execution_provenance_sha256, 64
    )
    actual_commit = _validated_hex("implementation_commit_sha", implementation_commit_sha, 40)
    expected_commit = _validated_hex("provenance implementation_commit_sha", provenance.implementation_commit_sha, 40)
    if actual_commit != expected_commit:
        raise ValueError("implementation_commit_sha does not match bound provenance")

    actual_runtime = _normalized_nonempty("runtime_id", runtime_id)
    expected_runtime = _normalized_nonempty("provenance runtime_id", provenance.runtime_id)
    if actual_runtime != expected_runtime:
        raise ValueError("runtime_id does not match bound provenance")

    actual_hashes = {
        "analysis_code_sha256": _sha256("analysis_code", analysis_code),
        "test_code_sha256": _sha256("test_code", test_code),
        "dependency_lock_sha256": _sha256("dependency_lock", dependency_lock),
        "ci_workflow_sha256": _sha256("ci_workflow", ci_workflow),
    }
    for field, actual in actual_hashes.items():
        expected = _validated_hex(f"provenance {field}", getattr(provenance, field), 64)
        if actual != expected:
            raise ValueError(f"{field} does not match supplied artifact bytes")

    payload = {
        "execution_provenance_sha256": execution_provenance_sha256,
        "implementation_commit_sha": actual_commit,
        **actual_hashes,
        "runtime_id": actual_runtime,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    verification_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationArtifactVerification(
        execution_provenance_sha256=execution_provenance_sha256,
        implementation_commit_sha=actual_commit,
        analysis_code_sha256=actual_hashes["analysis_code_sha256"],
        test_code_sha256=actual_hashes["test_code_sha256"],
        dependency_lock_sha256=actual_hashes["dependency_lock_sha256"],
        ci_workflow_sha256=actual_hashes["ci_workflow_sha256"],
        runtime_id=actual_runtime,
        artifact_verification_sha256=verification_sha256,
        artifact_bytes_verified=True,
    )
