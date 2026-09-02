from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .search_quality_ablation import EVIDENCE_STATE as ABLATION_EVIDENCE_STATE
from .search_quality_ablation import SearchQualityAblationReport

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_MULTIPLICITY_AWARE_ABLATION_FAMILY"
TRUTH_BOUNDARY = (
    "This gate evaluates a caller-supplied family of already-computed paired search-quality ablation reports and "
    "controls family-wise false-positive risk with the deterministic Holm step-down procedure. It requires a common "
    "measurement source, protocol, machine fingerprint, reference condition, workload/candidate universe size, and "
    "top-k setting; distinct normalized ablation labels; constituent effect acceptance; and no automatic-control "
    "authority. Family acceptance uses only the caller-declared family-wise alpha. A passing family report is "
    "conditional on the supplied ablation family and its predeclared inclusion; it does not prove that the family was "
    "specified before observing results, eliminate selective reporting or researcher degrees of freedom, establish "
    "causal attribution, representative or independent sampling, valid instrumentation, publication-grade evidence, "
    "superiority, novelty, patentability, or production-control authorization."
)


@dataclass(frozen=True)
class AblationFamilyMemberResult:
    ablated_label: str
    raw_one_sided_p_value: float
    holm_adjusted_p_value: float
    effect_acceptance_passed: bool
    multiplicity_acceptance_passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "ablated_label": self.ablated_label,
            "raw_one_sided_p_value": self.raw_one_sided_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "effect_acceptance_passed": self.effect_acceptance_passed,
            "multiplicity_acceptance_passed": self.multiplicity_acceptance_passed,
        }


@dataclass(frozen=True)
class SearchQualityAblationFamilyReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    reference_label: str
    workload_count: int
    candidate_count: int
    top_k: int
    family_size: int
    family_wise_alpha: float
    correction_method: str
    members: tuple[AblationFamilyMemberResult, ...]
    all_effects_accepted: bool
    all_multiplicity_tests_accepted: bool
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "reference_label": self.reference_label,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "family_size": self.family_size,
            "family_wise_alpha": self.family_wise_alpha,
            "correction_method": self.correction_method,
            "members": [member.as_dict() for member in self.members],
            "all_effects_accepted": self.all_effects_accepted,
            "all_multiplicity_tests_accepted": self.all_multiplicity_tests_accepted,
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


def _holm_adjusted_p_values(raw_p_values: tuple[float, ...]) -> tuple[float, ...]:
    count = len(raw_p_values)
    ordered = sorted(enumerate(raw_p_values), key=lambda item: (item[1], item[0]))
    adjusted = [0.0] * count
    running_max = 0.0
    for rank, (original_index, p_value) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * p_value)
        running_max = max(running_max, candidate)
        adjusted[original_index] = running_max
    return tuple(adjusted)


def evaluate_search_quality_ablation_family(
    reports: Iterable[SearchQualityAblationReport],
    *,
    family_wise_alpha: float,
    minimum_required_ablations: int = 2,
) -> SearchQualityAblationFamilyReport:
    """Apply a multiplicity-aware family gate to paired MORPHEUS search-quality ablations."""

    items = tuple(reports)
    if minimum_required_ablations < 2:
        raise ValueError("minimum_required_ablations must be at least 2")
    if len(items) < minimum_required_ablations:
        raise ValueError(f"ablation family must contain at least {minimum_required_ablations} reports")
    if not math.isfinite(family_wise_alpha) or not 0.0 < family_wise_alpha <= 1.0:
        raise ValueError("family_wise_alpha must be finite and in (0, 1]")

    first = items[0]
    source = _normalized_nonempty("measurement_source_id", first.measurement_source_id)
    protocol = _normalized_nonempty("protocol", first.protocol)
    machine = _normalized_nonempty("machine_fingerprint", first.machine_fingerprint)
    reference_label = _normalized_nonempty("reference_label", first.reference_label)
    workload_count = first.workload_count
    candidate_count = first.candidate_count
    top_k = first.top_k

    if workload_count < 1 or candidate_count < 1 or top_k < 1:
        raise ValueError("constituent ablation reports must contain positive workload/candidate/top_k values")

    normalized_labels: set[str] = set()
    labels: list[str] = []
    raw_p_values: list[float] = []
    effect_passes: list[bool] = []

    for report in items:
        if report.evidence_state != ABLATION_EVIDENCE_STATE:
            raise ValueError("constituent report has an incompatible evidence_state")
        if report.automatic_control_allowed:
            raise ValueError("ablation evidence cannot authorize automatic control")
        if _normalized_nonempty("measurement_source_id", report.measurement_source_id) != source:
            raise ValueError("ablation family must share measurement_source_id")
        if _normalized_nonempty("protocol", report.protocol) != protocol:
            raise ValueError("ablation family must share protocol")
        if _normalized_nonempty("machine_fingerprint", report.machine_fingerprint) != machine:
            raise ValueError("ablation family must share machine_fingerprint")
        if _normalized_nonempty("reference_label", report.reference_label) != reference_label:
            raise ValueError("ablation family must share reference_label")
        if report.workload_count != workload_count or report.candidate_count != candidate_count:
            raise ValueError("ablation family must share workload/candidate universe size")
        if report.top_k != top_k:
            raise ValueError("ablation family must share top_k")
        if not math.isfinite(report.one_sided_p_value) or not 0.0 <= report.one_sided_p_value <= 1.0:
            raise ValueError("constituent one_sided_p_value must be finite and in [0, 1]")

        label = _normalized_nonempty("ablated_label", report.ablated_label)
        normalized_key = label.casefold()
        if normalized_key in normalized_labels:
            raise ValueError("ablation family must use distinct normalized ablated_label values")
        normalized_labels.add(normalized_key)
        labels.append(label)
        raw_p_values.append(report.one_sided_p_value)
        effect_passes.append(report.effect_acceptance_passed)

    adjusted = _holm_adjusted_p_values(tuple(raw_p_values))
    members = tuple(
        AblationFamilyMemberResult(
            ablated_label=label,
            raw_one_sided_p_value=raw_p,
            holm_adjusted_p_value=adjusted_p,
            effect_acceptance_passed=effect_passed,
            multiplicity_acceptance_passed=adjusted_p <= family_wise_alpha,
        )
        for label, raw_p, adjusted_p, effect_passed in zip(labels, raw_p_values, adjusted, effect_passes)
    )
    all_effects = all(member.effect_acceptance_passed for member in members)
    all_multiplicity = all(member.multiplicity_acceptance_passed for member in members)

    return SearchQualityAblationFamilyReport(
        measurement_source_id=source,
        protocol=protocol,
        machine_fingerprint=machine,
        reference_label=reference_label,
        workload_count=workload_count,
        candidate_count=candidate_count,
        top_k=top_k,
        family_size=len(members),
        family_wise_alpha=family_wise_alpha,
        correction_method="holm_step_down_family_wise_error_control",
        members=members,
        all_effects_accepted=all_effects,
        all_multiplicity_tests_accepted=all_multiplicity,
        acceptance_passed=all_effects and all_multiplicity,
    )
