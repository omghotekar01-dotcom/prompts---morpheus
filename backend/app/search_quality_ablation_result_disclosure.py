"""Disclosure-consistency verification for MORPHEUS ablation result artifacts.

P40 proves that a byte-bound result artifact reports the supplied P31 multiplicity-aware family
outcome exactly. This P41 gate additionally requires the same artifact to declare the identity and
completeness counts of one supplied P33 complete outcome/negative-result disclosure report.

This is reporting-integrity evidence only. It does not establish that the predeclared family was
externally preregistered, that undisclosed experiments do not exist outside that family, that
interpretation notes are unbiased, or that the bound implementation actually produced the bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_disclosure import (
    EVIDENCE_STATE as DISCLOSURE_EVIDENCE_STATE,
    AblationDisclosureReport,
)
from .search_quality_ablation_result_outcome import (
    EVIDENCE_STATE as OUTCOME_EVIDENCE_STATE,
    AblationResultOutcomeVerification,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_DISCLOSURE_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P40-verified result artifact declares the same P33 disclosure identity, plan binding, "
    "family size, and complete accepted/not-accepted counts as one supplied complete disclosure report. It does not prove "
    "external preregistration, completeness beyond the supplied predeclared family, absence of hidden analyses, unbiased "
    "interpretation, valid or independent measurements, genuine execution of the bound implementation, or independent "
    "reproduction. Passing establishes no benchmark/search superiority, causal validity, publication-grade evidence, "
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


def _strict_nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
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
class AblationResultDisclosureVerification:
    outcome_verification_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    disclosure_sha256: str
    family_size: int
    disclosed_count: int
    accepted_count: int
    not_accepted_count: int
    disclosure_verification_sha256: str
    disclosure_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "outcome_verification_sha256": self.outcome_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "disclosure_sha256": self.disclosure_sha256,
            "family_size": self.family_size,
            "disclosed_count": self.disclosed_count,
            "accepted_count": self.accepted_count,
            "not_accepted_count": self.not_accepted_count,
            "disclosure_verification_sha256": self.disclosure_verification_sha256,
            "disclosure_consistency_verified": self.disclosure_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_disclosure_consistency(
    outcome: AblationResultOutcomeVerification,
    disclosure: AblationDisclosureReport,
    *,
    result_artifact: bytes | str,
) -> AblationResultDisclosureVerification:
    """Require a P40-bound result to report one supplied P33 complete disclosure exactly."""

    if outcome.evidence_state != OUTCOME_EVIDENCE_STATE:
        raise ValueError("outcome verification has an incompatible evidence_state")
    if outcome.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not outcome.outcome_consistency_verified:
        raise ValueError("result outcome must be verified before disclosure verification")

    if disclosure.evidence_state != DISCLOSURE_EVIDENCE_STATE:
        raise ValueError("disclosure report has an incompatible evidence_state")
    if disclosure.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not disclosure.membership_complete or not disclosure.outcome_classification_exact:
        raise ValueError("disclosure report must prove complete membership and exact outcome classification")
    if not disclosure.acceptance_passed:
        raise ValueError("disclosure completeness gate must have passed")
    if disclosure.family_size < 1 or disclosure.disclosed_count != disclosure.family_size:
        raise ValueError("disclosure family size and disclosed count are inconsistent")
    if disclosure.accepted_count < 0 or disclosure.not_accepted_count < 0:
        raise ValueError("disclosure outcome counts cannot be negative")
    if disclosure.accepted_count + disclosure.not_accepted_count != disclosure.family_size:
        raise ValueError("disclosure accepted/not-accepted counts must sum to family size")
    if disclosure.family_size != outcome.family_size or disclosure.disclosed_count != outcome.member_count:
        raise ValueError("P33 disclosure family size must match the P40 verified family")

    outcome_sha = _validated_hex("outcome_verification_sha256", outcome.outcome_verification_sha256)
    expected_result_sha = _validated_hex("result_artifact_sha256", outcome.result_artifact_sha256)
    plan_sha = _validated_hex("plan_sha256", disclosure.plan_sha256)
    disclosure_sha = _validated_hex("disclosure_sha256", disclosure.disclosure_sha256)
    plan_id = _normalized_nonempty("plan_id", disclosure.plan_id)

    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P40 result_artifact_sha256")

    declared = document.get("disclosure")
    if not isinstance(declared, dict):
        raise ValueError("result artifact disclosure must be an object")

    declared_plan_id = _normalized_nonempty("disclosure.plan_id", declared.get("plan_id"))
    if declared_plan_id != plan_id:
        raise ValueError("result artifact disclosure.plan_id does not match P33 disclosure report")
    if _validated_hex("disclosure.plan_sha256", declared.get("plan_sha256")) != plan_sha:
        raise ValueError("result artifact disclosure.plan_sha256 does not match P33 disclosure report")
    if _validated_hex("disclosure.disclosure_sha256", declared.get("disclosure_sha256")) != disclosure_sha:
        raise ValueError("result artifact disclosure.disclosure_sha256 does not match P33 disclosure report")

    expected_counts = {
        "family_size": disclosure.family_size,
        "disclosed_count": disclosure.disclosed_count,
        "accepted_count": disclosure.accepted_count,
        "not_accepted_count": disclosure.not_accepted_count,
    }
    for field, expected in expected_counts.items():
        actual = _strict_nonnegative_int(f"disclosure.{field}", declared.get(field))
        if actual != expected:
            raise ValueError(f"result artifact disclosure.{field} does not match P33 disclosure report")

    if _strict_bool("disclosure.membership_complete", declared.get("membership_complete")) is not True:
        raise ValueError("result artifact disclosure.membership_complete must be true")
    if _strict_bool("disclosure.outcome_classification_exact", declared.get("outcome_classification_exact")) is not True:
        raise ValueError("result artifact disclosure.outcome_classification_exact must be true")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    payload = {
        "outcome_verification_sha256": outcome_sha,
        "result_artifact_sha256": actual_result_sha,
        "plan_id": plan_id,
        "plan_sha256": plan_sha,
        "disclosure_sha256": disclosure_sha,
        **expected_counts,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    verification_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultDisclosureVerification(
        outcome_verification_sha256=outcome_sha,
        result_artifact_sha256=actual_result_sha,
        plan_id=plan_id,
        plan_sha256=plan_sha,
        disclosure_sha256=disclosure_sha,
        family_size=disclosure.family_size,
        disclosed_count=disclosure.disclosed_count,
        accepted_count=disclosure.accepted_count,
        not_accepted_count=disclosure.not_accepted_count,
        disclosure_verification_sha256=verification_sha,
        disclosure_consistency_verified=True,
    )
