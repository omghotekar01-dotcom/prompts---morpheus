"""Bind raw-sample search-policy semantics to the P32 ablation plan.

P54 proves that exact raw-sample bytes match the P32 measurement context, workload
cardinality, and condition family. P55 closes the remaining search-policy seam by
requiring the same result declaration to bind the candidate-universe size and top-k
ranking cutoff to that P32 plan.

This is an internal consistency gate only. It does not prove measurement validity,
execution provenance, sampling validity, causal effects, or performance superiority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from .search_quality_ablation_preregistration import AblationAnalysisPlan
from .search_quality_ablation_result_evidence_manifest import AblationResultEvidenceManifestVerification
from .search_quality_ablation_result_raw_sample_family_plan import AblationRawSampleFamilyPlanConsistency
from .search_quality_ablation_result_raw_sample_family_plan_context import (
    EVIDENCE_STATE as CONTEXT_EVIDENCE_STATE,
    AblationRawSampleFamilyPlanContextConsistency,
    verify_ablation_raw_sample_family_plan_context_consistency,
)
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_family_correction import (
    AblationRawSamplePairwiseFamilyCorrectionConsistency,
)
from .search_quality_ablation_result_raw_sample_pairwise_inference import AblationRawSamplePairwiseInferenceConsistency
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_SEARCH_POLICY_CONSISTENCY"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact result/raw-sample evidence already re-verified through P54 declares "
    "the same positive candidate-universe size and top-k ranking cutoff as the P32 plan bound into that evidence "
    "chain. It does not prove that the declared candidate universe was actually searched, that top-k was applied "
    "correctly during measurement, that measurements are genuine, independent, randomized, representative, unbiased, "
    "or complete, that the bound implementation produced them, or that the plan predates observation. Passing "
    "establishes no causal validity, benchmark/search superiority, publication-grade evidence, novelty, patentability, "
    "production readiness, or automatic-control authorization."
)


def _raw(name: str, value: object) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes or str")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AblationRawSampleSearchPolicyConsistency:
    family_plan_context_sha256: str
    result_artifact_sha256: str
    plan_id: str
    plan_sha256: str
    candidate_count: int
    top_k: int
    search_policy_binding_sha256: str
    search_policy_consistency_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_search_policy_consistency(
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
) -> AblationRawSampleSearchPolicyConsistency:
    """Require raw-sample candidate-count/top-k policy to match the exact P54-bound P32 plan."""

    if context.evidence_state != CONTEXT_EVIDENCE_STATE:
        raise ValueError("P54 family-plan context evidence has an incompatible evidence_state")
    if not context.family_plan_context_consistency_verified:
        raise ValueError("P54 family-plan context consistency must be verified")
    if context.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed_context = verify_ablation_raw_sample_family_plan_context_consistency(
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
    if recomputed_context != context:
        raise ValueError("supplied P54 context evidence does not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    actual_result_sha = hashlib.sha256(result_raw).hexdigest()
    if actual_result_sha != _text("P54 result_artifact_sha256", context.result_artifact_sha256).casefold():
        raise ValueError("P54 context evidence does not bind the supplied result artifact bytes")
    if _text("P54 plan_id", context.plan_id) != _text("plan.plan_id", plan.plan_id):
        raise ValueError("P54 plan_id does not match the supplied P32 plan")
    if _text("P54 plan_sha256", context.plan_sha256).casefold() != plan.sha256().casefold():
        raise ValueError("P54 plan content does not match the supplied P32 plan")

    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    if not isinstance(raw_evidence, dict):
        raise ValueError("raw_sample_evidence must be an object")
    declaration = raw_evidence.get("semantics")
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.semantics must be an object")

    candidate_count = _positive_int("raw-sample candidate_count", declaration.get("candidate_count"))
    top_k = _positive_int("raw-sample top_k", declaration.get("top_k"))
    if candidate_count != plan.candidate_count:
        raise ValueError("raw-sample candidate_count does not match the P32 plan")
    if top_k != plan.top_k:
        raise ValueError("raw-sample top_k does not match the P32 plan")
    if top_k > candidate_count:
        raise ValueError("raw-sample top_k cannot exceed candidate_count")

    payload = {
        "family_plan_context_sha256": _text(
            "P54 family_plan_context_sha256", context.family_plan_context_sha256
        ).casefold(),
        "result_artifact_sha256": actual_result_sha,
        "plan_id": _text("plan.plan_id", plan.plan_id),
        "plan_sha256": plan.sha256().casefold(),
        "candidate_count": candidate_count,
        "top_k": top_k,
    }
    return AblationRawSampleSearchPolicyConsistency(
        family_plan_context_sha256=payload["family_plan_context_sha256"],
        result_artifact_sha256=actual_result_sha,
        plan_id=payload["plan_id"],
        plan_sha256=payload["plan_sha256"],
        candidate_count=candidate_count,
        top_k=top_k,
        search_policy_binding_sha256=_sha(payload),
        search_policy_consistency_verified=True,
    )
