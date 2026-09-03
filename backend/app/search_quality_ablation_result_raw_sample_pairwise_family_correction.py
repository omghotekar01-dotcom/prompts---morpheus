"""Holm-Bonferroni family-correction consistency for P51-bound MORPHEUS raw samples.

P52 closes the confirmatory multiplicity seam in the frozen experiment protocol. It re-verifies the
exact P51 evidence chain, then requires the result artifact's declared family-wise correction to match
deterministic Holm-Bonferroni correction of the exact two-sided sign-test p-values already recomputed
by P51. This is a reporting/integrity gate, not evidence that the hypothesis family was selected before
results were observed or that any performance claim is true.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .multiple_comparisons import holm_bonferroni
from .search_quality_ablation_result_raw_sample_pairing import AblationRawSamplePairingConsistency
from .search_quality_ablation_result_raw_sample_pairwise_delta_inventory import AblationRawSamplePairwiseDeltaInventory
from .search_quality_ablation_result_raw_sample_pairwise_descriptives import AblationRawSamplePairwiseDescriptives
from .search_quality_ablation_result_raw_sample_pairwise_inference import (
    EVIDENCE_STATE as INFERENCE_EVIDENCE_STATE,
    AblationRawSamplePairwiseInferenceConsistency,
    verify_ablation_raw_sample_pairwise_inference,
)
from .search_quality_ablation_result_raw_sample_semantics import AblationRawSampleSemanticConsistency
from .search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding

EVIDENCE_STATE = "METHODOLOGY_ONLY_VERIFIED_ABLATION_RAW_SAMPLE_PAIRWISE_FAMILY_CORRECTION"
TRUTH_BOUNDARY = (
    "This gate proves only that the exact P51-verified caller-supplied result/raw-sample bytes reproduce the "
    "declared Holm-Bonferroni correction for the complete comparison family declared in that result artifact. "
    "It does not prove that the family was preregistered, selected before results were observed, exhaustive outside "
    "the supplied artifact, or free of selective reporting; nor does it establish measurement genuineness, "
    "independence, randomization, representativeness, causal attribution, benchmark/search superiority, "
    "publication-grade evidence, novelty, patentability, production readiness, or automatic-control authorization."
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _raw(name: str, value: object) -> bytes:
    if isinstance(value, str):
        value = value.encode()
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes or str")
    return value


def _strict_int(name: str, value: object, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _canonical_number(value: float) -> str:
    try:
        decimal = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("correction produced a non-decimal value") from exc
    if not decimal.is_finite():
        raise ValueError("correction produced a non-finite value")
    if decimal == 0:
        return "0"
    text = format(decimal.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _declared_number(name: str, value: object) -> str:
    return _canonical_number(_finite_float(name, value))


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class AblationRawSamplePairwiseFamilyCorrectionConsistency:
    inference_sha256: str
    reference_condition_id: str
    family_size: int
    family_wise_alpha: str
    correction_method: str
    rejected_count: int
    family_correction_sha256: str
    family_correction_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_ablation_raw_sample_pairwise_family_correction(
    inference: AblationRawSamplePairwiseInferenceConsistency,
    delta_inventory: AblationRawSamplePairwiseDeltaInventory,
    descriptives: AblationRawSamplePairwiseDescriptives,
    pairing: AblationRawSamplePairingConsistency,
    semantics: AblationRawSampleSemanticConsistency,
    binding: AblationResultRawSampleBinding,
    *,
    result_artifact: bytes | str,
    raw_sample_artifacts: Mapping[str, bytes | str],
) -> AblationRawSamplePairwiseFamilyCorrectionConsistency:
    if inference.evidence_state != INFERENCE_EVIDENCE_STATE or not inference.inference_verified:
        raise ValueError("P51 inference evidence is incompatible or unverified")
    if inference.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")

    recomputed = verify_ablation_raw_sample_pairwise_inference(
        delta_inventory,
        descriptives,
        pairing,
        semantics,
        binding,
        result_artifact=result_artifact,
        raw_sample_artifacts=raw_sample_artifacts,
    )
    if recomputed != inference:
        raise ValueError("supplied P51 inference does not match the exact result/raw-sample bytes")

    result_raw = _raw("result_artifact", result_artifact)
    try:
        document = json.loads(result_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("result_artifact must contain valid UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("automatic_control_allowed") is not False:
        raise ValueError("result artifact must be an object with automatic_control_allowed=false")
    raw_evidence = document.get("raw_sample_evidence")
    if not isinstance(raw_evidence, dict):
        raise ValueError("raw_sample_evidence must be an object")
    inference_declaration = raw_evidence.get("pairwise_inference")
    declaration = raw_evidence.get("pairwise_family_correction")
    if not isinstance(inference_declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_inference must be an object")
    if not isinstance(declaration, dict):
        raise ValueError("raw_sample_evidence.pairwise_family_correction must be an object")
    if declaration.get("correction_complete") is not True:
        raise ValueError("pairwise_family_correction.correction_complete must be true")
    if declaration.get("method") != "HOLM_BONFERRONI_STEP_DOWN":
        raise ValueError("pairwise_family_correction.method must be HOLM_BONFERRONI_STEP_DOWN")

    alpha = _finite_float("family_wise_alpha", declaration.get("family_wise_alpha"))
    if not 0.0 < alpha < 1.0:
        raise ValueError("family_wise_alpha must be strictly between 0 and 1")
    family_size = _strict_int("family_size", declaration.get("family_size"), minimum=2)

    inference_comparisons = inference_declaration.get("comparisons")
    if not isinstance(inference_comparisons, list) or len(inference_comparisons) < 2:
        raise ValueError("P52 requires at least two P51 comparison hypotheses")
    raw_p_values: dict[str, float] = {}
    for item in inference_comparisons:
        if not isinstance(item, dict):
            raise ValueError("each P51 comparison must be an object")
        condition = _text("condition_id", item.get("condition_id"))
        if condition in raw_p_values:
            raise ValueError("P51 comparison condition_id values must be unique")
        raw_p = item.get("exact_sign_test_p_two_sided")
        if raw_p is None:
            raise ValueError("every family member must have a defined exact two-sided sign-test p-value")
        numeric_p = _finite_float("exact_sign_test_p_two_sided", raw_p)
        if not 0.0 <= numeric_p <= 1.0:
            raise ValueError("exact_sign_test_p_two_sided must be in [0, 1]")
        raw_p_values[condition] = numeric_p
    if family_size != len(raw_p_values):
        raise ValueError("declared family_size does not match the complete P51 comparison family")

    correction = holm_bonferroni(raw_p_values, alpha=alpha)
    declared_comparisons = declaration.get("comparisons")
    if not isinstance(declared_comparisons, list) or len(declared_comparisons) != family_size:
        raise ValueError("pairwise_family_correction.comparisons must contain the complete family")
    declared_by_condition: dict[str, dict[str, object]] = {}
    for item in declared_comparisons:
        if not isinstance(item, dict):
            raise ValueError("each family-correction comparison must be an object")
        condition = _text("condition_id", item.get("condition_id"))
        if condition in declared_by_condition:
            raise ValueError("family-correction condition_id values must be unique")
        declared_by_condition[condition] = item
    if set(declared_by_condition) != set(raw_p_values):
        raise ValueError("declared family-correction conditions do not match the complete P51 comparison family")

    canonical_members: list[dict[str, object]] = []
    for hypothesis in correction.hypotheses:
        item = declared_by_condition[hypothesis.label]
        observed = {
            "condition_id": hypothesis.label,
            "raw_p": _declared_number("raw_p", item.get("raw_p")),
            "adjusted_p": _declared_number("adjusted_p", item.get("adjusted_p")),
            "rejected": item.get("rejected"),
            "rank": _strict_int("rank", item.get("rank"), minimum=1),
            "threshold": _declared_number("threshold", item.get("threshold")),
        }
        if not isinstance(observed["rejected"], bool):
            raise ValueError("rejected must be a boolean")
        expected = {
            "condition_id": hypothesis.label,
            "raw_p": _canonical_number(hypothesis.raw_p),
            "adjusted_p": _canonical_number(hypothesis.adjusted_p),
            "rejected": hypothesis.rejected,
            "rank": hypothesis.rank,
            "threshold": _canonical_number(hypothesis.threshold),
        }
        if observed != expected:
            raise ValueError(f"declared Holm-Bonferroni correction does not match P51 p-values for {hypothesis.label!r}")
        canonical_members.append(expected)

    payload = {
        "inference_sha256": inference.inference_sha256.lower(),
        "reference_condition_id": inference.reference_condition_id,
        "method": correction.method,
        "family_wise_alpha": _canonical_number(alpha),
        "family_size": correction.family_size,
        "members": canonical_members,
    }
    return AblationRawSamplePairwiseFamilyCorrectionConsistency(
        inference_sha256=inference.inference_sha256.lower(),
        reference_condition_id=inference.reference_condition_id,
        family_size=correction.family_size,
        family_wise_alpha=_canonical_number(alpha),
        correction_method=correction.method,
        rejected_count=sum(1 for item in correction.hypotheses if item.rejected),
        family_correction_sha256=_sha(payload),
        family_correction_verified=True,
    )
