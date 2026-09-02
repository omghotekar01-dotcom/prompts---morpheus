"""Threats-to-validity consistency verification for MORPHEUS ablation result artifacts.

P41 proves that a byte-bound result artifact reports one supplied P33 complete disclosure exactly.
This P42 gate additionally requires the same artifact to declare the identity and coverage summary
of one supplied P34 threats-to-validity report.

This is reporting-integrity evidence only. It does not establish that the supplied threats are
exhaustive, that mitigations worked, that residual-risk labels are justified, or that the bound
implementation actually produced the bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_result_disclosure import (
    EVIDENCE_STATE as RESULT_DISCLOSURE_EVIDENCE_STATE,
    AblationResultDisclosureVerification,
)
from .search_quality_ablation_validity import (
    EVIDENCE_STATE as VALIDITY_EVIDENCE_STATE,
    REQUIRED_CATEGORIES,
    AblationValidityThreatsReport,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_VALIDITY_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P41-verified result artifact declares the same P34 threats-to-validity identity, "
    "plan/disclosure binding, family size, threat count, and required-category coverage as one supplied accepted validity "
    "report. It does not prove that the listed threats are exhaustive, that mitigations were effective, that residual-risk "
    "labels are independently justified, that measurements are valid or independent, that hidden analyses do not exist, "
    "that the bound implementation genuinely executed, or that independent reproduction occurred. Passing establishes no "
    "benchmark/search superiority, causal validity, publication-grade evidence, novelty, patentability, production "
    "readiness, or automatic-control authorization."
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


def _strict_nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _strict_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _normalized_categories(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("validity.covered_categories must be an array")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("validity.covered_categories entries must be strings")
        category = item.strip().casefold().replace("-", "_").replace(" ", "_")
        if not category:
            raise ValueError("validity.covered_categories entries cannot be empty")
        normalized.append(category)
    if len(normalized) != len(set(normalized)):
        raise ValueError("validity.covered_categories cannot contain duplicates")
    return tuple(sorted(normalized))


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
class AblationResultValidityVerification:
    disclosure_verification_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    disclosure_sha256: str
    family_size: int
    threat_count: int
    covered_categories: tuple[str, ...]
    threats_sha256: str
    validity_verification_sha256: str
    validity_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "disclosure_verification_sha256": self.disclosure_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "disclosure_sha256": self.disclosure_sha256,
            "family_size": self.family_size,
            "threat_count": self.threat_count,
            "covered_categories": list(self.covered_categories),
            "threats_sha256": self.threats_sha256,
            "validity_verification_sha256": self.validity_verification_sha256,
            "validity_consistency_verified": self.validity_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_validity_consistency(
    disclosure_verification: AblationResultDisclosureVerification,
    validity_report: AblationValidityThreatsReport,
    *,
    result_artifact: bytes | str,
) -> AblationResultValidityVerification:
    """Require a P41-bound result to report one supplied P34 validity register exactly."""

    if disclosure_verification.evidence_state != RESULT_DISCLOSURE_EVIDENCE_STATE:
        raise ValueError("disclosure verification has an incompatible evidence_state")
    if disclosure_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not disclosure_verification.disclosure_consistency_verified:
        raise ValueError("result disclosure must be verified before validity verification")

    if validity_report.evidence_state != VALIDITY_EVIDENCE_STATE:
        raise ValueError("validity report has an incompatible evidence_state")
    if validity_report.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not validity_report.acceptance_passed or not validity_report.category_coverage_complete:
        raise ValueError("validity report must prove accepted complete required-category coverage")

    disclosure_verification_sha = _validated_hex(
        "disclosure_verification_sha256", disclosure_verification.disclosure_verification_sha256
    )
    expected_result_sha = _validated_hex("result_artifact_sha256", disclosure_verification.result_artifact_sha256)
    plan_sha = _validated_hex("plan_sha256", validity_report.plan_sha256)
    disclosure_sha = _validated_hex("disclosure_sha256", validity_report.disclosure_sha256)
    threats_sha = _validated_hex("threats_sha256", validity_report.threats_sha256)
    plan_id = _normalized_nonempty("plan_id", validity_report.plan_id)

    if validity_report.family_size < 1:
        raise ValueError("validity report family_size must be positive")
    if validity_report.threat_count < len(REQUIRED_CATEGORIES):
        raise ValueError("validity report threat_count cannot cover all required validity categories")
    expected_categories = tuple(sorted(REQUIRED_CATEGORIES))
    if tuple(sorted(validity_report.covered_categories)) != expected_categories:
        raise ValueError("validity report covered_categories must equal the required validity categories")

    if plan_id != disclosure_verification.plan_id:
        raise ValueError("P34 validity plan_id must match the P41 verified disclosure")
    if plan_sha != _validated_hex("P41 plan_sha256", disclosure_verification.plan_sha256):
        raise ValueError("P34 validity plan_sha256 must match the P41 verified disclosure")
    if disclosure_sha != _validated_hex("P41 disclosure_sha256", disclosure_verification.disclosure_sha256):
        raise ValueError("P34 validity disclosure_sha256 must match the P41 verified disclosure")
    if validity_report.family_size != disclosure_verification.family_size:
        raise ValueError("P34 validity family_size must match the P41 verified disclosure")

    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P41 result_artifact_sha256")

    declared = document.get("validity")
    if not isinstance(declared, dict):
        raise ValueError("result artifact validity must be an object")

    declared_plan_id = _normalized_nonempty("validity.plan_id", declared.get("plan_id"))
    if declared_plan_id != plan_id:
        raise ValueError("result artifact validity.plan_id does not match P34 validity report")
    if _validated_hex("validity.plan_sha256", declared.get("plan_sha256")) != plan_sha:
        raise ValueError("result artifact validity.plan_sha256 does not match P34 validity report")
    if _validated_hex("validity.disclosure_sha256", declared.get("disclosure_sha256")) != disclosure_sha:
        raise ValueError("result artifact validity.disclosure_sha256 does not match P34 validity report")
    if _validated_hex("validity.threats_sha256", declared.get("threats_sha256")) != threats_sha:
        raise ValueError("result artifact validity.threats_sha256 does not match P34 validity report")

    declared_family_size = _strict_nonnegative_int("validity.family_size", declared.get("family_size"))
    if declared_family_size != validity_report.family_size:
        raise ValueError("result artifact validity.family_size does not match P34 validity report")
    declared_threat_count = _strict_nonnegative_int("validity.threat_count", declared.get("threat_count"))
    if declared_threat_count != validity_report.threat_count:
        raise ValueError("result artifact validity.threat_count does not match P34 validity report")

    declared_categories = _normalized_categories(declared.get("covered_categories"))
    if declared_categories != expected_categories:
        raise ValueError("result artifact validity.covered_categories does not match P34 validity report")
    if _strict_bool("validity.category_coverage_complete", declared.get("category_coverage_complete")) is not True:
        raise ValueError("result artifact validity.category_coverage_complete must be true")
    if _strict_bool("validity.acceptance_passed", declared.get("acceptance_passed")) is not True:
        raise ValueError("result artifact validity.acceptance_passed must be true")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "disclosure_verification_sha256": disclosure_verification_sha,
        "result_artifact_sha256": actual_result_sha,
        "plan_id": plan_id,
        "plan_sha256": plan_sha,
        "disclosure_sha256": disclosure_sha,
        "family_size": validity_report.family_size,
        "threat_count": validity_report.threat_count,
        "covered_categories": list(expected_categories),
        "threats_sha256": threats_sha,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    verification_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultValidityVerification(
        disclosure_verification_sha256=disclosure_verification_sha,
        result_artifact_sha256=actual_result_sha,
        plan_id=plan_id,
        plan_sha256=plan_sha,
        disclosure_sha256=disclosure_sha,
        family_size=validity_report.family_size,
        threat_count=validity_report.threat_count,
        covered_categories=expected_categories,
        threats_sha256=threats_sha,
        validity_verification_sha256=verification_sha,
        validity_consistency_verified=True,
    )
