"""Bind P52 raw-sample multiplicity evidence to the already-bound P32 analysis plan.

P52 proves that a supplied result/raw-sample family reproduces Holm-Bonferroni correction, but it
intentionally does not prove that the family is the same family bound by MORPHEUS's internal P32
analysis-plan artifact. P53 closes only that identity/consistency seam. It does not establish external
preregistration or chronology.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .search_quality_ablation_preregistration import AblationAnalysisPlan
from .search_quality_ablation_result_evidence_manifest import (
    EVIDENCE_STATE as MANIFEST_VERIFICATION_EVIDENCE_STATE,
    AblationResultEvidenceManifestVerification,
)
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    EVIDENCE_STATE as FAMILY_CORRECTION_EVIDENCE_STATE,
    AblationRawSamplePairwiseFamilyCorrectionConsistency,
    verify_ablation_raw_sample_pairwise_family_correction,
)
from .search_quality_ablation_result_raw_sample_pairwise_inference import AblationRawSamplePairwiseInferenceConsistency
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_FAMILY_PLAN_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P52-verified raw-sample comparison family is identical, after explicit "
    "normalization, to the family content of one supplied P32 analysis plan whose deterministic plan identity is "
    "already bound into the same P43-verified result artifact. It binds family membership, reference identity, "
    "family size, and family-wise alpha. It does not prove when the P32 plan was authored, that it was externally "
    "registered before results were observed, that every attempted analysis was disclosed, or that selective "
    "reporting is absent. It does not establish measurement genuineness, independence, randomization, "
    "representativeness, causal attribution, benchmark/search superiority, publication-grade evidence, novelty, "
    "patentability, production readiness, or automatic-control authorization."
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _label(name: str, value: object) -> str:
    return _text(name, value).casefold()


def _hex(name: str, value: object) -> str:
    normalized = _text(name, value).casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _raw(name: str, value: object) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes or str")
    return value


def _canonical_number(name: str, value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not decimal.is_finite():
        raise ValueError(f"{name} must be finite")
    numeric = float(decimal)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    if decimal == 0:
        return "0"
    text = format(decimal.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AblationRawSampleFamilyPlanConsistency:
    family_correction_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    reference_condition_id: str
    family_size: int
    family_wise_alpha: str
    normalized_family_members: tuple[str, ...]
    family_plan_binding_sha256: str
    family_plan_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "normalized_family_members": list(self.normalized_family_members),
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_raw_sample_family_plan_consistency(
    family_correction: AblationRawSamplePairwiseFamilyCorrectionConsistency,
    inference: AblationRawSamplePairwiseInferenceConsistency,
    delta_inventory: AblationRawSamplePairwiseDeltaInventory,
    descriptives: AblationRawSamplePairwiseDescriptives,
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    manifest_verification: AblationResultEvidenceManifestVerification,
    plan: AblationAnalysisPlan,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSampleFamilyPlanConsistency:
    """Require the P52 raw-sample family to match the P32 plan already bound by P43."""

    if family_correction.evidence_state != FAMILY_CORRECTION_EVIDENCE_STATE:
        raise ValueError("P52 family-correction evidence has an incompatible evidence_state")
    if not family_correction.family_correction_verified:
        raise ValueError("P52 family correction must be verified")
    if family_correction.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed = verify_ablation_raw_sample_pairwise_family_correction(
        inference,
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != family_correction:
        raise ValueError("supplied P52 family correction does not match the exact result/raw-sample bytes")

    if manifest_verification.evidence_state != MANIFEST_VERIFICATION_EVIDENCE_STATE:
        raise ValueError("P43 evidence-manifest verification has an incompatible evidence_state")
    if not manifest_verification.evidence_manifest_consistency_verified:
        raise ValueError("P43 evidence-manifest consistency must be verified")
    if manifest_verification.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    result_raw = _raw("result_artifact", result_artifact)
    actual_result_sha = hashlib.sha256(result_raw).hexdigest()
    if actual_result_sha != _hex("P43 result_artifact_sha256", manifest_verification.result_artifact_sha256):
        raise ValueError("P43 evidence manifest and P52 family correction must bind the same result artifact bytes")

    plan_id = _text("plan.plan_id", plan.plan_id)
    plan_sha = plan.sha256().casefold()
    if plan_id != _text("P43 plan_id", manifest_verification.plan_id):
        raise ValueError("supplied P32 plan_id does not match the P43-bound plan_id")
    if plan_sha != _hex("P43 plan_sha256", manifest_verification.plan_sha256):
        raise ValueError("supplied P32 plan content does not match the P43-bound plan_sha256")

    expected_members = tuple(sorted(_label("expected_ablated_label", item) for item in plan.expected_ablated_labels))
    if len(expected_members) < 2:
        raise ValueError("P32 plan must contain at least two ablation-family members")
    if len(set(expected_members)) != len(expected_members):
        raise ValueError("P32 expected_ablated_labels must be distinct after normalization")
    if manifest_verification.family_size != len(expected_members):
        raise ValueError("P43-bound family_size does not match the supplied P32 plan")
    if family_correction.family_size != len(expected_members):
        raise ValueError("P52 family_size does not match the supplied P32 plan")

    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    if not isinstance(raw_evidence, dict):
        raise ValueError("raw_sample_evidence must be an object")
    declaration = raw_evidence.get("pairwise_family_correction")
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_family_correction must be an object")
    comparisons = declaration.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) != len(expected_members):
        raise ValueError("pairwise family declaration must contain the complete P32 family")

    observed_members_list: list[str] = []
    for item in comparisons:
        if not isinstance(item, dict):
            raise ValueError("each pairwise family comparison must be an object")
        observed_members_list.append(_label("condition_id", item.get("condition_id")))
    if len(set(observed_members_list)) != len(observed_members_list):
        raise ValueError("pairwise family condition_id values must be distinct after normalization")
    observed_members = tuple(sorted(observed_members_list))
    if observed_members != expected_members:
        raise ValueError("P52 raw-sample family membership does not match the P32 plan")

    expected_reference = _label("plan.reference_label", plan.reference_label)
    observed_reference = _label("P52 reference_condition_id", family_correction.reference_condition_id)
    if observed_reference != expected_reference:
        raise ValueError("P52 reference condition does not match the P32 reference_label")

    plan_alpha = _canonical_number("plan.family_wise_alpha", plan.family_wise_alpha)
    p52_alpha = _canonical_number("P52 family_wise_alpha", family_correction.family_wise_alpha)
    declared_alpha = _canonical_number("declared family_wise_alpha", declaration.get("family_wise_alpha"))
    if p52_alpha != plan_alpha or declared_alpha != plan_alpha:
        raise ValueError("P52 family-wise alpha does not match the P32 plan")

    payload = {
        "family_correction_sha256": _hex(
            "P52 family_correction_sha256", family_correction.family_correction_sha256
        ),
        "result_artifact_sha256": actual_result_sha,
        "plan_id": plan_id,
        "plan_sha256": plan_sha,
        "reference_condition_id": observed_reference,
        "family_size": len(expected_members),
        "family_wise_alpha": plan_alpha,
        "normalized_family_members": list(expected_members),
    }
    return AblationRawSampleFamilyPlanConsistency(
        family_correction_sha256=payload["family_correction_sha256"],
        result_artifact_sha256=actual_result_sha,
        plan_id=plan_id,
        plan_sha256=plan_sha,
        reference_condition_id=observed_reference,
        family_size=len(expected_members),
        family_wise_alpha=plan_alpha,
        normalized_family_members=expected_members,
        family_plan_binding_sha256=_sha(payload),
        family_plan_consistency_verified=True,
    )
