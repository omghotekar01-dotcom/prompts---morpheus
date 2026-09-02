"""Outcome-consistency verification for MORPHEUS ablation result artifacts.

P39 proves byte-bound JSON/provenance semantic consistency. This P40 gate additionally requires the
result artifact's declared multiplicity-aware family outcome to agree exactly with the supplied P31
family report. It verifies reporting consistency only; it does not independently validate measurements
or prove that the verified implementation produced the result bytes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .search_quality_ablation_family import (
    EVIDENCE_STATE as FAMILY_EVIDENCE_STATE,
    SearchQualityAblationFamilyReport,
)
from .search_quality_ablation_result_semantics import (
    EVIDENCE_STATE as SEMANTIC_EVIDENCE_STATE,
    AblationResultSemanticVerification,
    RESULT_SCHEMA,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RESULT_OUTCOME_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that one P39-verified result artifact reports the same multiplicity-aware family acceptance, "
    "family metadata, and per-member statistical/effect outcomes as one supplied P31 family report. It does not prove "
    "that measurements are valid, independent, representative, or causal; that the family was externally preregistered; "
    "that verified code produced the result bytes; or that an external party reproduced the experiment. Passing establishes "
    "no benchmark/search superiority, publication-grade evidence, novelty, patentability, production readiness, or "
    "automatic-control authorization."
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
class AblationResultOutcomeVerification:
    semantic_verification_sha256: str
    result_artifact_sha256: str
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    reference_label: str
    family_size: int
    family_wise_alpha: float
    correction_method: str
    acceptance_passed: bool
    member_count: int
    outcome_verification_sha256: str
    outcome_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "semantic_verification_sha256": self.semantic_verification_sha256,
            "result_artifact_sha256": self.result_artifact_sha256,
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "reference_label": self.reference_label,
            "family_size": self.family_size,
            "family_wise_alpha": self.family_wise_alpha,
            "correction_method": self.correction_method,
            "acceptance_passed": self.acceptance_passed,
            "member_count": self.member_count,
            "outcome_verification_sha256": self.outcome_verification_sha256,
            "outcome_consistency_verified": self.outcome_consistency_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_result_outcome_consistency(
    semantics: AblationResultSemanticVerification,
    family: SearchQualityAblationFamilyReport,
    *,
    result_artifact: bytes | str,
) -> AblationResultOutcomeVerification:
    """Require a P39-bound result's reported family outcome to equal the supplied P31 family report."""

    if semantics.evidence_state != SEMANTIC_EVIDENCE_STATE:
        raise ValueError("semantic verification has an incompatible evidence_state")
    if semantics.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not semantics.semantic_consistency_verified:
        raise ValueError("result semantics must be verified before outcome verification")
    if semantics.schema != RESULT_SCHEMA:
        raise ValueError("semantic verification schema is incompatible")

    if family.evidence_state != FAMILY_EVIDENCE_STATE:
        raise ValueError("ablation family has an incompatible evidence_state")
    if family.automatic_control_allowed:
        raise ValueError("ablation evidence cannot authorize automatic control")
    if family.family_size < 1 or family.family_size != len(family.members):
        raise ValueError("ablation family size is inconsistent with members")

    semantic_sha = _validated_hex("semantic_verification_sha256", semantics.semantic_verification_sha256, 64)
    expected_result_sha = _validated_hex("result_artifact_sha256", semantics.result_artifact_sha256, 64)
    raw, document = _json_object(result_artifact)
    actual_result_sha = hashlib.sha256(raw).hexdigest()
    if actual_result_sha != expected_result_sha:
        raise ValueError("result_artifact bytes do not match the P39 result_artifact_sha256")

    if _normalized_nonempty("schema", document.get("schema")) != RESULT_SCHEMA:
        raise ValueError(f"schema must equal {RESULT_SCHEMA}")
    accepted = _strict_bool("accepted", document.get("accepted"))
    if accepted != family.acceptance_passed:
        raise ValueError("result artifact accepted does not match P31 family acceptance_passed")

    family_doc = document.get("family")
    if not isinstance(family_doc, dict):
        raise ValueError("result artifact family must be an object")

    expected_text = {
        "measurement_source_id": _normalized_nonempty("measurement_source_id", family.measurement_source_id),
        "protocol": _normalized_nonempty("protocol", family.protocol),
        "machine_fingerprint": _normalized_nonempty("machine_fingerprint", family.machine_fingerprint),
        "reference_label": _normalized_nonempty("reference_label", family.reference_label),
        "correction_method": _normalized_nonempty("correction_method", family.correction_method),
    }
    for field, expected in expected_text.items():
        actual = _normalized_nonempty(f"family.{field}", family_doc.get(field))
        if actual != expected:
            raise ValueError(f"result artifact family.{field} does not match P31 family report")

    if family_doc.get("family_size") != family.family_size:
        raise ValueError("result artifact family.family_size does not match P31 family report")
    if family_doc.get("family_wise_alpha") != family.family_wise_alpha:
        raise ValueError("result artifact family.family_wise_alpha does not match P31 family report")

    declared_members = family_doc.get("members")
    if not isinstance(declared_members, list):
        raise ValueError("result artifact family.members must be an array")
    if len(declared_members) != family.family_size:
        raise ValueError("result artifact family.members must cover every P31 family member")

    expected_members: dict[str, object] = {}
    for member in family.members:
        key = _normalized_nonempty("ablated_label", member.ablated_label).casefold()
        if key in expected_members:
            raise ValueError("P31 family contains duplicate normalized ablated_label values")
        expected_members[key] = member

    seen: set[str] = set()
    canonical_members: list[dict[str, object]] = []
    for index, declared in enumerate(declared_members):
        if not isinstance(declared, dict):
            raise ValueError(f"result artifact family.members[{index}] must be an object")
        label = _normalized_nonempty(f"family.members[{index}].ablated_label", declared.get("ablated_label"))
        key = label.casefold()
        if key in seen:
            raise ValueError("result artifact family.members contains duplicate normalized ablated_label values")
        seen.add(key)
        member = expected_members.get(key)
        if member is None:
            raise ValueError("result artifact family.members contains an unknown ablated_label")

        comparisons = {
            "raw_one_sided_p_value": member.raw_one_sided_p_value,
            "holm_adjusted_p_value": member.holm_adjusted_p_value,
            "effect_acceptance_passed": member.effect_acceptance_passed,
            "multiplicity_acceptance_passed": member.multiplicity_acceptance_passed,
        }
        for field, expected in comparisons.items():
            actual = declared.get(field)
            if isinstance(expected, bool):
                actual = _strict_bool(f"family.members[{index}].{field}", actual)
            if actual != expected:
                raise ValueError(f"result artifact member {label} {field} does not match P31 family report")

        canonical_members.append(
            {
                "ablated_label": key,
                "raw_one_sided_p_value": member.raw_one_sided_p_value,
                "holm_adjusted_p_value": member.holm_adjusted_p_value,
                "effect_acceptance_passed": member.effect_acceptance_passed,
                "multiplicity_acceptance_passed": member.multiplicity_acceptance_passed,
            }
        )

    if seen != set(expected_members):
        raise ValueError("result artifact family.members does not exactly cover the P31 family")
    if document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must explicitly set automatic_control_allowed to false")

    canonical_members.sort(key=lambda item: str(item["ablated_label"]))
    payload = {
        "semantic_verification_sha256": semantic_sha,
        "result_artifact_sha256": actual_result_sha,
        **expected_text,
        "family_size": family.family_size,
        "family_wise_alpha": family.family_wise_alpha,
        "acceptance_passed": family.acceptance_passed,
        "members": canonical_members,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    outcome_sha = hashlib.sha256(encoded).hexdigest()

    return AblationResultOutcomeVerification(
        semantic_verification_sha256=semantic_sha,
        result_artifact_sha256=actual_result_sha,
        measurement_source_id=expected_text["measurement_source_id"],
        protocol=expected_text["protocol"],
        machine_fingerprint=expected_text["machine_fingerprint"],
        reference_label=expected_text["reference_label"],
        family_size=family.family_size,
        family_wise_alpha=family.family_wise_alpha,
        correction_method=expected_text["correction_method"],
        acceptance_passed=family.acceptance_passed,
        member_count=len(canonical_members),
        outcome_verification_sha256=outcome_sha,
        outcome_consistency_verified=True,
    )
