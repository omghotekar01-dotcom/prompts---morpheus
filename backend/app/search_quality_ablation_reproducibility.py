"""Deterministic execution-provenance binding for MORPHEUS ablation research evidence.

This module binds one already-validated ablation evidence manifest to caller-supplied immutable
implementation/research-environment identities. It checks internal content identity only; it does
not claim that an independent party has reproduced the experiment or that the supplied digests
correspond to externally archived artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .search_quality_ablation_evidence_manifest import (
    EVIDENCE_STATE as MANIFEST_EVIDENCE_STATE,
    AblationResearchEvidenceManifest,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_BOUND_ABLATION_EXECUTION_PROVENANCE"
TRUTH_BOUNDARY = (
    "This gate proves only deterministic internal binding between one integrity-passed MORPHEUS ablation evidence "
    "manifest and caller-supplied implementation commit, analysis-code, test-code, dependency-lock, CI-workflow, and "
    "runtime identities. It does not fetch, archive, timestamp, sign, or independently attest those artifacts; it does "
    "not prove that the supplied hashes describe the files actually executed, that another machine can reproduce the "
    "result, or that all transitive system/compiler/hardware influences are captured. Passing this provenance gate does "
    "not establish independent reproduction, publication-grade evidence, causal validity, benchmark/search superiority, "
    "novelty, patentability, production readiness, or automatic-control authorization."
)


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _validated_hex(name: str, value: str, length: int) -> str:
    normalized = value.strip().casefold()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    return normalized


@dataclass(frozen=True)
class AblationExecutionProvenance:
    evidence_manifest_sha256: str
    implementation_commit_sha: str
    analysis_code_sha256: str
    test_code_sha256: str
    dependency_lock_sha256: str
    ci_workflow_sha256: str
    runtime_id: str
    execution_provenance_sha256: str
    provenance_complete: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
            "implementation_commit_sha": self.implementation_commit_sha,
            "analysis_code_sha256": self.analysis_code_sha256,
            "test_code_sha256": self.test_code_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "ci_workflow_sha256": self.ci_workflow_sha256,
            "runtime_id": self.runtime_id,
            "execution_provenance_sha256": self.execution_provenance_sha256,
            "provenance_complete": self.provenance_complete,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def bind_ablation_execution_provenance(
    manifest: AblationResearchEvidenceManifest,
    *,
    implementation_commit_sha: str,
    analysis_code_sha256: str,
    test_code_sha256: str,
    dependency_lock_sha256: str,
    ci_workflow_sha256: str,
    runtime_id: str,
) -> AblationExecutionProvenance:
    """Fail closed unless one complete evidence manifest is bound to a complete provenance identity set."""

    if manifest.evidence_state != MANIFEST_EVIDENCE_STATE:
        raise ValueError("manifest has an incompatible evidence_state")
    if manifest.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not manifest.integrity_passed:
        raise ValueError("manifest must pass integrity validation before provenance can be bound")

    evidence_manifest_sha256 = _validated_hex(
        "evidence_manifest_sha256", manifest.evidence_manifest_sha256, 64
    )
    implementation_commit_sha = _validated_hex("implementation_commit_sha", implementation_commit_sha, 40)
    analysis_code_sha256 = _validated_hex("analysis_code_sha256", analysis_code_sha256, 64)
    test_code_sha256 = _validated_hex("test_code_sha256", test_code_sha256, 64)
    dependency_lock_sha256 = _validated_hex("dependency_lock_sha256", dependency_lock_sha256, 64)
    ci_workflow_sha256 = _validated_hex("ci_workflow_sha256", ci_workflow_sha256, 64)
    runtime_id = _normalized_nonempty("runtime_id", runtime_id)

    payload = {
        "evidence_manifest_sha256": evidence_manifest_sha256,
        "implementation_commit_sha": implementation_commit_sha,
        "analysis_code_sha256": analysis_code_sha256,
        "test_code_sha256": test_code_sha256,
        "dependency_lock_sha256": dependency_lock_sha256,
        "ci_workflow_sha256": ci_workflow_sha256,
        "runtime_id": runtime_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    provenance_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationExecutionProvenance(
        evidence_manifest_sha256=evidence_manifest_sha256,
        implementation_commit_sha=implementation_commit_sha,
        analysis_code_sha256=analysis_code_sha256,
        test_code_sha256=test_code_sha256,
        dependency_lock_sha256=dependency_lock_sha256,
        ci_workflow_sha256=ci_workflow_sha256,
        runtime_id=runtime_id,
        execution_provenance_sha256=provenance_sha256,
        provenance_complete=True,
    )
