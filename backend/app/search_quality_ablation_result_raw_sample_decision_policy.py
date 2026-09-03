"""Bind raw-sample decision-policy declarations to the P32 ablation plan.

P55 binds candidate-universe size and top-k. P56 closes the remaining P32 policy
seam by requiring the same exact result declaration to carry the predeclared
minimum effect threshold and maximum one-sided p-value threshold.

These declarations are only bound as policy metadata. In particular, this gate does
not compare P32's one-sided aggregate threshold with P51's two-sided raw-sample sign
test, because those are different statistical quantities.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping

from .search_quality_ablation_preregistration import AblationAnalysisPlan
from .search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from .search_quality_ablation_result_raw_sample_family_plan import AblationRawSampleFamilyPlanConsistency
from .search_quality_ablation_result_raw_sample_family_plan_context import AblationRawSampleFamilyPlanContextConsistency
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_family_correction import AblationRawSamplePairwiseFamilyCorrectionConsistency
from .search_quality_ablation_result_raw_sample_pairwise_inference import AblationRawSamplePairwiseInferenceConsistency
from .search_quality_ablation_result_raw_sample_search_policy import (
    EVIDENCE_STATE as SEARCH_POLICY_EVIDENCE_STATE,
    AblationRawSampleSearchPolicyConsistency,
    verify_ablation_raw_sample_search_policy_consistency,
)
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_DECISION_POLICY_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that exact result/raw-sample evidence re-verified through P55 declares the same finite "
    "minimum mean-regret-ratio improvement threshold and maximum one-sided p-value threshold as the bound P32 plan. "
    "It does not apply those thresholds to P51 raw-sample inference, prove that either decision rule was actually used, "
    "or prove measurement validity, sampling validity, preregistration chronology, causal effects, superiority, "
    "publication-grade evidence, novelty, patentability, production readiness, or automatic-control authorization."
)


def _raw(value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes) or not value:
        raise ValueError("result_artifact must be non-empty bytes or str")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be a finite number")
    return numeric


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class AblationRawSampleDecisionPolicyConsistency:
    search_policy_binding_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    minimum_required_mean_regret_ratio_improvement: float
    maximum_allowed_one_sided_p_value: float
    decision_policy_binding_sha256: str
    decision_policy_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_decision_policy_consistency(
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
) -> AblationRawSampleDecisionPolicyConsistency:
    """Require raw-sample decision thresholds to match the exact P55-bound P32 plan."""
    if search_policy.evidence_state != SEARCH_POLICY_EVIDENCE_STATE:
        raise ValueError("P55 search-policy evidence has an incompatible evidence_state")
    if not search_policy.search_policy_consistency_verified:
        raise ValueError("P55 search-policy consistency must be verified")
    if search_policy.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed = verify_ablation_raw_sample_search_policy_consistency(
        context, family_plan, family_correction, inference, delta_inventory, descriptives,
        pairing, semantics, binding, manifest_verification, plan,
        result_artifact=result_artifact, raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != search_policy:
        raise ValueError("supplied P55 search-policy evidence does not match the exact result/raw-sample bytes")

    result_raw = _raw(result_artifact)
    result_sha = hashlib.sha256(result_raw).hexdigest()
    if result_sha != search_policy.result_artifact_sha256.casefold():
        raise ValueError("P55 search-policy evidence does not bind the supplied result artifact bytes")
    if search_policy.plan_id != plan.plan_id.strip() or search_policy.plan_sha256.casefold() != plan.sha256().casefold():
        raise ValueError("P55 search-policy evidence does not bind the supplied P32 plan")

    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    declaration = raw_evidence.get("semantics") if isinstance(raw_evidence, dict) else None
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.semantics must be an object")

    minimum = _finite("minimum_required_mean_regret_ratio_improvement", declaration.get("minimum_required_mean_regret_ratio_improvement"))
    maximum_p = _finite("maximum_allowed_one_sided_p_value", declaration.get("maximum_allowed_one_sided_p_value"))
    if minimum < 0.0:
        raise ValueError("minimum_required_mean_regret_ratio_improvement must be non-negative")
    if not 0.0 < maximum_p <= 1.0:
        raise ValueError("maximum_allowed_one_sided_p_value must be in (0, 1]")
    if minimum != plan.minimum_required_mean_regret_ratio_improvement:
        raise ValueError("minimum_required_mean_regret_ratio_improvement does not match the P32 plan")
    if maximum_p != plan.maximum_allowed_one_sided_p_value:
        raise ValueError("maximum_allowed_one_sided_p_value does not match the P32 plan")

    payload = {
        "search_policy_binding_sha256": search_policy.search_policy_binding_sha256.casefold(),
        "result_artifact_sha256": result_sha,
        "plan_id": plan.plan_id.strip(),
        "plan_sha256": plan.sha256().casefold(),
        "minimum_required_mean_regret_ratio_improvement": minimum,
        "maximum_allowed_one_sided_p_value": maximum_p,
    }
    return AblationRawSampleDecisionPolicyConsistency(
        search_policy_binding_sha256=payload["search_policy_binding_sha256"],
        result_artifact_sha256=result_sha,
        plan_id=payload["plan_id"],
        plan_sha256=payload["plan_sha256"],
        minimum_required_mean_regret_ratio_improvement=minimum,
        maximum_allowed_one_sided_p_value=maximum_p,
        decision_policy_binding_sha256=_sha(payload),
        decision_policy_consistency_verified=True,
    )
