"""Fail closed unless the verified raw-sample chain covers every canonical P32 plan field.

P53-P56 bind complementary slices of the P32 analysis plan. P57 is deliberately
not another statistical test: it is a coverage seal that reconstructs the plan-facing
values from those verified gates and refuses to pass if the canonical P32 payload
contains any field that is not explicitly covered here.

This makes later plan-schema growth fail closed instead of silently inheriting a plan
SHA while leaving a new policy field semantically unbound to raw-sample evidence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .search_quality_ablation_preregistration import AblationAnalysisPlan
from .search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from .search_quality_ablation_result_raw_sample_decision_policy import (
    EVIDENCE_STATE as DECISION_POLICY_EVIDENCE_STATE,
    AblationRawSampleDecisionPolicyConsistency,
    verify_ablation_raw_sample_decision_policy_consistency,
)
from .search_quality_ablation_result_raw_sample_family_plan import AblationRawSampleFamilyPlanConsistency
from .search_quality_ablation_result_raw_sample_family_plan_context import AblationRawSampleFamilyPlanContextConsistency
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    AblationRawSamplePairwiseFamilyCorrectionConsistency,
)
from .search_quality_ablation_result_raw_sample_pairwise_inference import AblationRawSamplePairwiseInferenceConsistency
from .search_quality_ablation_result_raw_sample_search_policy import AblationRawSampleSearchPolicyConsistency
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PLAN_COVERAGE_SEAL"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P56-reverified raw-sample evidence chain explicitly covers every field "
    "currently present in the P32 canonical analysis-plan payload, and that the covered values are internally "
    "consistent with that supplied plan. It fails closed if the P32 canonical payload gains an unrecognized field. "
    "The seal does not prove when the plan was authored, external preregistration, absence of undisclosed analyses, "
    "measurement genuineness, instrumentation or sampling validity, independence, randomization, representativeness, "
    "causal effects, benchmark/search superiority, publication-grade evidence, novelty, patentability, production "
    "readiness, or automatic-control authorization."
)

COVERED_PLAN_FIELDS = (
    "plan_id",
    "measurement_source_id",
    "protocol",
    "machine_fingerprint",
    "reference_label",
    "workload_count",
    "candidate_count",
    "top_k",
    "expected_ablated_labels",
    "minimum_required_mean_regret_ratio_improvement",
    "maximum_allowed_one_sided_p_value",
    "family_wise_alpha",
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _hex(name: str, value: object) -> str:
    normalized = _text(name, value).casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal digest")
    return normalized


def _decimal(name: str, value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be finite")
    return number


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AblationRawSamplePlanCoverageSeal:
    decision_policy_binding_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    covered_plan_fields: tuple[str, ...]
    covered_field_count: int
    plan_coverage_sha256: str
    complete_plan_coverage_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "covered_plan_fields": list(self.covered_plan_fields),
            "truth_boundary": TRUTH_BOUNDARY,
        }


def verify_ablation_raw_sample_plan_coverage(
    decision_policy: AblationRawSampleDecisionPolicyConsistency,
    search_policy: AblationRawSampleSearchPolicyConsistency,
    context: AblationRawSampleFamilyPlanContextConsistency,
    family_plan: AblationRawSampleFamilyPlanConsistency,
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
) -> AblationRawSamplePlanCoverageSeal:
    """Require complete, explicit coverage of the canonical P32 plan by P53-P56."""

    if decision_policy.evidence_state != DECISION_POLICY_EVIDENCE_STATE:
        raise ValueError("P56 decision-policy evidence has an incompatible evidence_state")
    if not decision_policy.decision_policy_consistency_verified:
        raise ValueError("P56 decision-policy consistency must be verified")
    if decision_policy.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed = verify_ablation_raw_sample_decision_policy_consistency(
        search_policy,
        context,
        family_plan,
        family_correction,
        inference,
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        manifest_verification,
        plan,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != decision_policy:
        raise ValueError("supplied P56 decision-policy evidence does not match the exact result/raw-sample bytes")

    canonical_plan = plan.canonical_payload()
    actual_fields = set(canonical_plan)
    expected_fields = set(COVERED_PLAN_FIELDS)
    if actual_fields != expected_fields:
        missing = sorted(actual_fields - expected_fields)
        stale = sorted(expected_fields - actual_fields)
        raise ValueError(
            "P32 canonical plan field coverage is incomplete or stale "
            f"(uncovered={missing}, stale={stale})"
        )

    if _text("P56 plan_id", decision_policy.plan_id) != _text("plan.plan_id", plan.plan_id):
        raise ValueError("P56 plan_id does not match the supplied P32 plan")
    plan_sha = plan.sha256().casefold()
    if _hex("P56 plan_sha256", decision_policy.plan_sha256) != plan_sha:
        raise ValueError("P56 plan content does not match the supplied P32 plan")

    if _hex("P56 search_policy_binding_sha256", decision_policy.search_policy_binding_sha256) != _hex(
        "P55 search_policy_binding_sha256", search_policy.search_policy_binding_sha256
    ):
        raise ValueError("P56 does not bind the supplied P55 search-policy evidence")
    if _hex("P55 family_plan_context_sha256", search_policy.family_plan_context_sha256) != _hex(
        "P54 family_plan_context_sha256", context.family_plan_context_sha256
    ):
        raise ValueError("P55 does not bind the supplied P54 context evidence")
    if _hex("P54 family_plan_binding_sha256", context.family_plan_binding_sha256) != _hex(
        "P53 family_plan_binding_sha256", family_plan.family_plan_binding_sha256
    ):
        raise ValueError("P54 does not bind the supplied P53 family-plan evidence")

    if _text("P54 measurement_source_id", context.measurement_source_id) != _text(
        "plan.measurement_source_id", plan.measurement_source_id
    ):
        raise ValueError("covered measurement_source_id does not match the P32 plan")
    if _text("P54 protocol", context.protocol) != _text("plan.protocol", plan.protocol):
        raise ValueError("covered protocol does not match the P32 plan")
    if _text("P54 machine_fingerprint", context.machine_fingerprint) != _text(
        "plan.machine_fingerprint", plan.machine_fingerprint
    ):
        raise ValueError("covered machine_fingerprint does not match the P32 plan")
    if context.workload_count != plan.workload_count:
        raise ValueError("covered workload_count does not match the P32 plan")
    if search_policy.candidate_count != plan.candidate_count or search_policy.top_k != plan.top_k:
        raise ValueError("covered candidate_count/top_k do not match the P32 plan")

    expected_reference = _text("plan.reference_label", plan.reference_label).casefold()
    if _text("P53 reference_condition_id", family_plan.reference_condition_id).casefold() != expected_reference:
        raise ValueError("covered reference_label does not match the P32 plan")
    expected_members = tuple(sorted(_text("plan.expected_ablated_label", x).casefold() for x in plan.expected_ablated_labels))
    observed_members = tuple(sorted(_text("P53 normalized_family_member", x).casefold() for x in family_plan.normalized_family_members))
    if observed_members != expected_members:
        raise ValueError("covered expected_ablated_labels do not match the P32 plan")

    if _decimal("P53 family_wise_alpha", family_plan.family_wise_alpha) != _decimal(
        "plan.family_wise_alpha", plan.family_wise_alpha
    ):
        raise ValueError("covered family_wise_alpha does not match the P32 plan")
    if _decimal(
        "P56 minimum_required_mean_regret_ratio_improvement",
        decision_policy.minimum_required_mean_regret_ratio_improvement,
    ) != _decimal(
        "plan.minimum_required_mean_regret_ratio_improvement",
        plan.minimum_required_mean_regret_ratio_improvement,
    ):
        raise ValueError("covered minimum effect threshold does not match the P32 plan")
    if _decimal(
        "P56 maximum_allowed_one_sided_p_value",
        decision_policy.maximum_allowed_one_sided_p_value,
    ) != _decimal("plan.maximum_allowed_one_sided_p_value", plan.maximum_allowed_one_sided_p_value):
        raise ValueError("covered one-sided p-value threshold does not match the P32 plan")

    result_sha = _hex("P56 result_artifact_sha256", decision_policy.result_artifact_sha256)
    for name, value in (
        ("P55 result_artifact_sha256", search_policy.result_artifact_sha256),
        ("P54 result_artifact_sha256", context.result_artifact_sha256),
        ("P53 result_artifact_sha256", family_plan.result_artifact_sha256),
    ):
        if _hex(name, value) != result_sha:
            raise ValueError("P53-P56 do not bind one exact result artifact")

    coverage_payload = {
        "decision_policy_binding_sha256": _hex(
            "P56 decision_policy_binding_sha256", decision_policy.decision_policy_binding_sha256
        ),
        "result_artifact_sha256": result_sha,
        "plan_id": _text("plan.plan_id", plan.plan_id),
        "plan_sha256": plan_sha,
        "covered_plan_fields": list(COVERED_PLAN_FIELDS),
        "covered_field_count": len(COVERED_PLAN_FIELDS),
    }
    return AblationRawSamplePlanCoverageSeal(
        decision_policy_binding_sha256=coverage_payload["decision_policy_binding_sha256"],
        result_artifact_sha256=result_sha,
        plan_id=coverage_payload["plan_id"],
        plan_sha256=plan_sha,
        covered_plan_fields=COVERED_PLAN_FIELDS,
        covered_field_count=len(COVERED_PLAN_FIELDS),
        plan_coverage_sha256=_sha(coverage_payload),
        complete_plan_coverage_verified=True,
    )
