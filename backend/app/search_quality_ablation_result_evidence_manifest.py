"""Research-evidence manifest consistency verification for MORPHEUS ablation result artifacts.

P42 proves that a byte-bound result artifact reports one supplied P34 threats-to-validity register.
This P43 gate additionally requires that artifact to declare the canonical P35 research-evidence
manifest identity and its bound plan/disclosure/threat/family summary.

This is provenance/reporting-integrity evidence only. It does not prove chronology, execution,
measurement validity, independent reproduction, or scientific/production superiority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_evidence_manifest import (
    EVIDENCE_STATE as MANIFEST_EVIDENCE_STATE,
    AblationResearchEvidenceManifest,
)
from .search_quality_ablation_result_validity import (
    EVIDENCE_STATE as RESULT_VALIDITY_EVIDENCE_STATE,
    AblationResultValidityVerification,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_EVIDENCE_MANIFEST_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P42-verified result artifact declares the same canonical P35 research-evidence "
    "manifest identity and bound plan/disclosure/threat/family summary as one supplied integrity-passed manifest. "
    "It does not prove that preregistration preceded observation, that hidden analyses do not exist, that the bound "
    "implementation executed, that measurements are valid or independent, or that an independent party reproduced "
    "the experiment. Passing establishes no benchmark/search superiority, causal validity, publication-grade evidence, "
    "novelty, patentability, production readiness, or automatic-control authorization."
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


def _strict_positive_int(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _strict_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


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
class AblationResultEvidenceManifestVerification:
    validity_verification_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    disclosure_sha256: str
    threats_sha256: str
    family_size: int
    evidence_manifest_sha256: str
    manifest_verification_sha256: str
    evidence_manifest_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "validity_verification_sha256": self.validity_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "disclosure_sha256": self.disclosure_sha256,
            "threats_sha256": self.threats_sha256,
            "family_size": self.family_size,
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
            "manifest_verification_sha256": self.manifest_verification_sha256,
            "evidence_manifest_consistency_verified": self.evidence_manifest_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_evidence_manifest_consistency(
    validity_verification: AblationResultValidityVerification,
    evidence_manifest: AblationResearchEvidenceManifest,
    *,
    result_artifact: bytes | str,
) -> AblationResultEvidenceManifestVerification:
    """Require a P42-bound result to report one supplied P35 research-evidence manifest exactly."""

    if validity_verification.evidence_state != RESULT_VALIDITY_EVIDENCE_STATE:
        raise ValueError("validity verification has an incompatible evidence_state")
    if validity_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not validity_verification.validity_consistency_verified:
        raise ValueError("result validity must be verified before evidence-manifest verification")

    if evidence_manifest.evidence_state != MANIFEST_EVIDENCE_STATE:
        raise ValueError("evidence manifest has an incompatible evidence_state")
    if evidence_manifest.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not evidence_manifest.integrity_passed:
        raise ValueError("evidence manifest must have integrity_passed=true")

    validity_sha = _validated_hex(
        "validity_verification_sha256", validity_verification.validity_verification_sha256
    )
    expected_result_sha = _validated_hex("result_artifact_sha256", validity_verification.result_artifact_sha256)
    manifest_sha = _validated_hex("evidence_manifest_sha256", evidence_manifest.evidence_manifest_sha256)
    plan_id = _normalized_nonempty("plan_id", evidence_manifest.plan_id)
    plan_sha = _validated_hex("plan_sha256", evidence_manifest.plan_sha256)
    disclosure_sha = _validated_hex("disclosure_sha256", evidence_manifest.disclosure_sha256)
    threats_sha = _validated_hex("threats_sha256", evidence_manifest.threats_sha256)

    if evidence_manifest.family_size < 1:
        raise ValueError("evidence manifest family_size must be positive")
    if plan_id != validity_verification.plan_id:
        raise ValueError("P35 evidence manifest plan_id must match the P42 verified validity result")
    if plan_sha != _validated_hex("P42 plan_sha256", validity_verification.plan_sha256):
        raise ValueError("P35 evidence manifest plan_sha256 must match the P42 verified validity result")
    if disclosure_sha != _validated_hex("P42 disclosure_sha256", validity_verification.disclosure_sha256):
        raise ValueError("P35 evidence manifest disclosure_sha256 must match the P42 verified validity result")
    if threats_sha != _validated_hex("P42 threats_sha256", validity_verification.threats_sha256):
        raise ValueError("P35 evidence manifest threats_sha256 must match the P42 verified validity result")
    if evidence_manifest.family_size != validity_verification.family_size:
        raise ValueError("P35 evidence manifest family_size must match the P42 verified validity result")

    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P42 result_artifact_sha256")

    declared = document.get("evidence_manifest")
    if not isinstance(declared, dict):
        raise ValueError("result artifact evidence_manifest must be an object")
    if _normalized_nonempty("evidence_manifest.plan_id", declared.get("plan_id")) != plan_id:
        raise ValueError("result artifact evidence_manifest.plan_id does not match P35 evidence manifest")
    if _validated_hex("evidence_manifest.plan_sha256", declared.get("plan_sha256")) != plan_sha:
        raise ValueError("result artifact evidence_manifest.plan_sha256 does not match P35 evidence manifest")
    if _validated_hex("evidence_manifest.disclosure_sha256", declared.get("disclosure_sha256")) != disclosure_sha:
        raise ValueError("result artifact evidence_manifest.disclosure_sha256 does not match P35 evidence manifest")
    if _validated_hex("evidence_manifest.threats_sha256", declared.get("threats_sha256")) != threats_sha:
        raise ValueError("result artifact evidence_manifest.threats_sha256 does not match P35 evidence manifest")
    if _validated_hex(
        "evidence_manifest.evidence_manifest_sha256", declared.get("evidence_manifest_sha256")
    ) != manifest_sha:
        raise ValueError(
            "result artifact evidence_manifest.evidence_manifest_sha256 does not match P35 evidence manifest"
        )
    if _strict_positive_int("evidence_manifest.family_size", declared.get("family_size")) != evidence_manifest.family_size:
        raise ValueError("result artifact evidence_manifest.family_size does not match P35 evidence manifest")
    if _strict_bool("evidence_manifest.integrity_passed", declared.get("integrity_passed")) is not True:
        raise ValueError("result artifact evidence_manifest.integrity_passed must be true")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "validity_verification_sha256": validity_sha,
        "result_artifact_sha256": actual_result_sha,
        "plan_id": plan_id,
        "plan_sha256": plan_sha,
        "disclosure_sha256": disclosure_sha,
        "threats_sha256": threats_sha,
        "family_size": evidence_manifest.family_size,
        "evidence_manifest_sha256": manifest_sha,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    verification_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultEvidenceManifestVerification(
        validity_verification_sha256=validity_sha,
        result_artifact_sha256=actual_result_sha,
        plan_id=plan_id,
        plan_sha256=plan_sha,
        disclosure_sha256=disclosure_sha,
        threats_sha256=threats_sha,
        family_size=evidence_manifest.family_size,
        evidence_manifest_sha256=manifest_sha,
        manifest_verification_sha256=verification_sha,
        evidence_manifest_consistency_verified=True,
    )
