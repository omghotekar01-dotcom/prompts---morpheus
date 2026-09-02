from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass
from typing import Iterable

from .heldout_evaluation import HeldoutCandidateMeasurement, evaluate_heldout_candidate_groups
from .search_quality_holdout import SearchQualityHoldoutEvidence

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_PAIRED_SEARCH_ABLATION"
TRUTH_BOUNDARY = (
    "This gate performs a paired workload-level ablation comparison on caller-supplied held-out search-quality "
    "measurements. It requires the reference and ablated conditions to share the same measurement source, protocol, "
    "machine fingerprint, workload/candidate universe, and measured costs, so only their supplied predictions differ. "
    "It reports regret deltas and a deterministic one-sided sign-flip randomization p-value, then applies only caller-"
    "declared minimum-effect and maximum-p-value limits. A passing report is conditional on the supplied paired sample "
    "and test procedure; it does not prove causal attribution, representative sampling, independent collection, valid "
    "instrumentation, publication-grade statistical evidence, superiority, novelty, patentability, or production-"
    "control authorization."
)


@dataclass(frozen=True)
class SearchQualityAblationReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    reference_label: str
    ablated_label: str
    workload_count: int
    candidate_count: int
    top_k: int
    reference_mean_top1_regret_ratio: float
    ablated_mean_top1_regret_ratio: float
    mean_regret_ratio_improvement: float
    median_regret_ratio_improvement: float
    improved_workload_count: int
    tied_workload_count: int
    worsened_workload_count: int
    randomization_method: str
    randomization_rounds: int
    randomization_seed: int
    one_sided_p_value: float
    minimum_required_mean_regret_ratio_improvement: float
    maximum_allowed_one_sided_p_value: float
    effect_acceptance_passed: bool
    statistical_acceptance_passed: bool
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "reference_label": self.reference_label,
            "ablated_label": self.ablated_label,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "reference_mean_top1_regret_ratio": self.reference_mean_top1_regret_ratio,
            "ablated_mean_top1_regret_ratio": self.ablated_mean_top1_regret_ratio,
            "mean_regret_ratio_improvement": self.mean_regret_ratio_improvement,
            "median_regret_ratio_improvement": self.median_regret_ratio_improvement,
            "improved_workload_count": self.improved_workload_count,
            "tied_workload_count": self.tied_workload_count,
            "worsened_workload_count": self.worsened_workload_count,
            "randomization_method": self.randomization_method,
            "randomization_rounds": self.randomization_rounds,
            "randomization_seed": self.randomization_seed,
            "one_sided_p_value": self.one_sided_p_value,
            "minimum_required_mean_regret_ratio_improvement": self.minimum_required_mean_regret_ratio_improvement,
            "maximum_allowed_one_sided_p_value": self.maximum_allowed_one_sided_p_value,
            "effect_acceptance_passed": self.effect_acceptance_passed,
            "statistical_acceptance_passed": self.statistical_acceptance_passed,
            "acceptance_passed": self.acceptance_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _validate_thresholds(minimum_effect: float, maximum_p: float) -> None:
    if not math.isfinite(minimum_effect) or minimum_effect < 0.0:
        raise ValueError("minimum_required_mean_regret_ratio_improvement must be finite and non-negative")
    if not math.isfinite(maximum_p) or not 0.0 < maximum_p <= 1.0:
        raise ValueError("maximum_allowed_one_sided_p_value must be finite and in (0, 1]")


def _measurement_map(evidence: SearchQualityHoldoutEvidence) -> dict[tuple[str, str], HeldoutCandidateMeasurement]:
    result: dict[tuple[str, str], HeldoutCandidateMeasurement] = {}
    for item in evidence.measurements:
        key = (item.workload_id, item.candidate_id)
        if key in result:
            raise ValueError("paired ablation evidence contains duplicate workload/candidate identities")
        result[key] = item
    return result


def _paired_randomization_p_value(
    improvements: tuple[float, ...], *, rounds: int, seed: int
) -> tuple[float, str, int]:
    if not improvements:
        raise ValueError("paired randomization requires at least one workload")
    observed = sum(improvements) / len(improvements)
    tolerance = 1e-15
    count = len(improvements)

    if count <= 20:
        total = 1 << count
        extreme = 0
        for signs in itertools.product((-1.0, 1.0), repeat=count):
            statistic = sum(sign * value for sign, value in zip(signs, improvements)) / count
            if statistic >= observed - tolerance:
                extreme += 1
        return extreme / total, "exact_sign_flip", total

    if rounds < 1000:
        raise ValueError("randomization_rounds must be at least 1000 when more than 20 workloads are supplied")
    rng = random.Random(seed)
    extreme = 0
    for _ in range(rounds):
        statistic = sum((1.0 if rng.getrandbits(1) else -1.0) * value for value in improvements) / count
        if statistic >= observed - tolerance:
            extreme += 1
    # Plus-one correction avoids a zero Monte Carlo p-value.
    return (extreme + 1) / (rounds + 1), "monte_carlo_sign_flip", rounds


def evaluate_paired_search_quality_ablation(
    reference: SearchQualityHoldoutEvidence,
    ablated: SearchQualityHoldoutEvidence,
    *,
    reference_label: str,
    ablated_label: str,
    model_development_source_ids: Iterable[str],
    minimum_required_workloads: int = 4,
    top_k: int = 3,
    minimum_required_mean_regret_ratio_improvement: float,
    maximum_allowed_one_sided_p_value: float,
    randomization_rounds: int = 10000,
    randomization_seed: int = 1337,
) -> SearchQualityAblationReport:
    """Evaluate a paired search-quality ablation without turning it into a superiority claim."""

    reference.validate()
    ablated.validate()
    if minimum_required_workloads < 2:
        raise ValueError("minimum_required_workloads must be at least 2")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    _validate_thresholds(
        minimum_required_mean_regret_ratio_improvement,
        maximum_allowed_one_sided_p_value,
    )
    reference_label = _normalized_nonempty("reference_label", reference_label)
    ablated_label = _normalized_nonempty("ablated_label", ablated_label)
    if reference_label == ablated_label:
        raise ValueError("reference_label and ablated_label must differ")

    source = _normalized_nonempty("measurement_source_id", reference.measurement_source_id)
    protocol = _normalized_nonempty("protocol", reference.protocol)
    machine = _normalized_nonempty("machine_fingerprint", reference.machine_fingerprint)
    if source != ablated.measurement_source_id.strip():
        raise ValueError("paired ablation conditions must share measurement_source_id")
    if protocol != ablated.protocol.strip():
        raise ValueError("paired ablation conditions must share protocol")
    if machine != ablated.machine_fingerprint.strip():
        raise ValueError("paired ablation conditions must share machine_fingerprint")

    development_sources = {item.strip() for item in model_development_source_ids if item.strip()}
    if source in development_sources:
        raise ValueError("held-out measurement_source_id overlaps model development/calibration sources")

    reference_items = _measurement_map(reference)
    ablated_items = _measurement_map(ablated)
    if set(reference_items) != set(ablated_items):
        raise ValueError("paired ablation conditions must share the exact workload/candidate universe")
    for key in reference_items:
        if reference_items[key].measured != ablated_items[key].measured:
            raise ValueError("paired ablation conditions must share identical measured costs")

    reference_metrics = evaluate_heldout_candidate_groups(reference.measurements, top_k=top_k)
    ablated_metrics = evaluate_heldout_candidate_groups(ablated.measurements, top_k=top_k)
    if reference_metrics.workload_count < minimum_required_workloads:
        raise ValueError(
            f"paired ablation evidence must contain at least {minimum_required_workloads} distinct workloads"
        )

    reference_by_workload = {item.workload_id: item for item in reference_metrics.workloads}
    ablated_by_workload = {item.workload_id: item for item in ablated_metrics.workloads}
    improvements: list[float] = []
    reference_regrets: list[float] = []
    ablated_regrets: list[float] = []
    for workload_id in sorted(reference_by_workload):
        reference_regret = reference_by_workload[workload_id].top1_regret_ratio
        ablated_regret = ablated_by_workload[workload_id].top1_regret_ratio
        if reference_regret is None or ablated_regret is None:
            raise ValueError("relative top-1 regret must be defined for every paired workload")
        reference_regrets.append(reference_regret)
        ablated_regrets.append(ablated_regret)
        improvements.append(ablated_regret - reference_regret)

    ordered = sorted(improvements)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
    mean_improvement = sum(improvements) / len(improvements)
    p_value, method, effective_rounds = _paired_randomization_p_value(
        tuple(improvements), rounds=randomization_rounds, seed=randomization_seed
    )
    effect_passed = mean_improvement >= minimum_required_mean_regret_ratio_improvement
    statistical_passed = p_value <= maximum_allowed_one_sided_p_value

    return SearchQualityAblationReport(
        measurement_source_id=source,
        protocol=protocol,
        machine_fingerprint=machine,
        reference_label=reference_label,
        ablated_label=ablated_label,
        workload_count=reference_metrics.workload_count,
        candidate_count=reference_metrics.candidate_count,
        top_k=top_k,
        reference_mean_top1_regret_ratio=sum(reference_regrets) / len(reference_regrets),
        ablated_mean_top1_regret_ratio=sum(ablated_regrets) / len(ablated_regrets),
        mean_regret_ratio_improvement=mean_improvement,
        median_regret_ratio_improvement=median,
        improved_workload_count=sum(value > 0.0 for value in improvements),
        tied_workload_count=sum(value == 0.0 for value in improvements),
        worsened_workload_count=sum(value < 0.0 for value in improvements),
        randomization_method=method,
        randomization_rounds=effective_rounds,
        randomization_seed=randomization_seed,
        one_sided_p_value=p_value,
        minimum_required_mean_regret_ratio_improvement=minimum_required_mean_regret_ratio_improvement,
        maximum_allowed_one_sided_p_value=maximum_allowed_one_sided_p_value,
        effect_acceptance_passed=effect_passed,
        statistical_acceptance_passed=statistical_passed,
        acceptance_passed=effect_passed and statistical_passed,
    )
