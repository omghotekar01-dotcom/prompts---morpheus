from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable

from .search_quality_ablation import EVIDENCE_STATE as ABLATION_EVIDENCE_STATE
from .search_quality_ablation import SearchQualityAblationReport
from .search_quality_ablation_family import (
    SearchQualityAblationFamilyReport,
    evaluate_search_quality_ablation_family,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_PREDECLARED_ABLATION_PLAN_BINDING"
TRUTH_BOUNDARY = (
    "This gate binds a caller-supplied ablation family to a deterministic caller-declared analysis plan before family "
    "acceptance is evaluated. It requires exact normalized family membership, common evidence context, fixed top-k, "
    "fixed constituent effect/statistical thresholds, and fixed family-wise alpha, then delegates multiplicity control "
    "to the existing Holm family gate. The plan hash proves only that the supplied plan content is deterministic and "
    "unchanged within this evaluation; it does not prove when the plan was authored, that it was registered externally "
    "before results were observed, that every attempted analysis was disclosed, or that selective reporting and other "
    "researcher degrees of freedom are absent. A passing report does not establish causal attribution, representative "
    "or independent sampling, instrumentation validity, publication-grade evidence, superiority, novelty, patentability, "
    "or production-control authorization."
)


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _normalized_label(value: str) -> str:
    return _normalized_nonempty("expected_ablated_label", value).casefold()


@dataclass(frozen=True)
class AblationAnalysisPlan:
    plan_id: str
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    reference_label: str
    workload_count: int
    candidate_count: int
    top_k: int
    expected_ablated_labels: tuple[str, ...]
    minimum_required_mean_regret_ratio_improvement: float
    maximum_allowed_one_sided_p_value: float
    family_wise_alpha: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "plan_id": _normalized_nonempty("plan_id", self.plan_id),
            "measurement_source_id": _normalized_nonempty("measurement_source_id", self.measurement_source_id),
            "protocol": _normalized_nonempty("protocol", self.protocol),
            "machine_fingerprint": _normalized_nonempty("machine_fingerprint", self.machine_fingerprint),
            "reference_label": _normalized_nonempty("reference_label", self.reference_label),
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "expected_ablated_labels": sorted(_normalized_label(label) for label in self.expected_ablated_labels),
            "minimum_required_mean_regret_ratio_improvement": self.minimum_required_mean_regret_ratio_improvement,
            "maximum_allowed_one_sided_p_value": self.maximum_allowed_one_sided_p_value,
            "family_wise_alpha": self.family_wise_alpha,
        }

    def sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PredeclaredAblationFamilyReport:
    plan_id: str
    plan_sha256: str
    expected_family_size: int
    observed_family_size: int
    family_membership_exact: bool
    thresholds_bound: bool
    family_report: SearchQualityAblationFamilyReport
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "expected_family_size": self.expected_family_size,
            "observed_family_size": self.observed_family_size,
            "family_membership_exact": self.family_membership_exact,
            "thresholds_bound": self.thresholds_bound,
            "family_report": self.family_report.as_dict(),
            "acceptance_passed": self.acceptance_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def _validate_plan(plan: AblationAnalysisPlan) -> tuple[str, ...]:
    _normalized_nonempty("plan_id", plan.plan_id)
    _normalized_nonempty("measurement_source_id", plan.measurement_source_id)
    _normalized_nonempty("protocol", plan.protocol)
    _normalized_nonempty("machine_fingerprint", plan.machine_fingerprint)
    _normalized_nonempty("reference_label", plan.reference_label)
    if plan.workload_count < 1 or plan.candidate_count < 1 or plan.top_k < 1:
        raise ValueError("plan workload_count, candidate_count, and top_k must be positive")
    if len(plan.expected_ablated_labels) < 2:
        raise ValueError("plan must predeclare at least 2 ablations")
    labels = tuple(_normalized_label(label) for label in plan.expected_ablated_labels)
    if len(set(labels)) != len(labels):
        raise ValueError("plan expected_ablated_labels must be distinct after normalization")
    if (
        not math.isfinite(plan.minimum_required_mean_regret_ratio_improvement)
        or plan.minimum_required_mean_regret_ratio_improvement < 0.0
    ):
        raise ValueError("minimum_required_mean_regret_ratio_improvement must be finite and non-negative")
    if (
        not math.isfinite(plan.maximum_allowed_one_sided_p_value)
        or not 0.0 < plan.maximum_allowed_one_sided_p_value <= 1.0
    ):
        raise ValueError("maximum_allowed_one_sided_p_value must be finite and in (0, 1]")
    if not math.isfinite(plan.family_wise_alpha) or not 0.0 < plan.family_wise_alpha <= 1.0:
        raise ValueError("family_wise_alpha must be finite and in (0, 1]")
    return labels


def evaluate_predeclared_ablation_family(
    plan: AblationAnalysisPlan,
    reports: Iterable[SearchQualityAblationReport],
) -> PredeclaredAblationFamilyReport:
    """Bind a paired-ablation family to a deterministic caller-declared analysis plan."""

    expected_labels = _validate_plan(plan)
    items = tuple(reports)
    if len(items) != len(expected_labels):
        raise ValueError("observed ablation family size must exactly match the predeclared plan")

    observed_labels: list[str] = []
    for report in items:
        if report.evidence_state != ABLATION_EVIDENCE_STATE:
            raise ValueError("constituent report has an incompatible evidence_state")
        if report.automatic_control_allowed:
            raise ValueError("ablation evidence cannot authorize automatic control")
        if _normalized_nonempty("measurement_source_id", report.measurement_source_id) != plan.measurement_source_id.strip():
            raise ValueError("measurement_source_id does not match the predeclared plan")
        if _normalized_nonempty("protocol", report.protocol) != plan.protocol.strip():
            raise ValueError("protocol does not match the predeclared plan")
        if _normalized_nonempty("machine_fingerprint", report.machine_fingerprint) != plan.machine_fingerprint.strip():
            raise ValueError("machine_fingerprint does not match the predeclared plan")
        if _normalized_nonempty("reference_label", report.reference_label) != plan.reference_label.strip():
            raise ValueError("reference_label does not match the predeclared plan")
        if report.workload_count != plan.workload_count or report.candidate_count != plan.candidate_count:
            raise ValueError("workload/candidate universe does not match the predeclared plan")
        if report.top_k != plan.top_k:
            raise ValueError("top_k does not match the predeclared plan")
        if report.minimum_required_mean_regret_ratio_improvement != plan.minimum_required_mean_regret_ratio_improvement:
            raise ValueError("effect-size threshold does not match the predeclared plan")
        if report.maximum_allowed_one_sided_p_value != plan.maximum_allowed_one_sided_p_value:
            raise ValueError("statistical threshold does not match the predeclared plan")
        observed_labels.append(_normalized_label(report.ablated_label))

    if len(set(observed_labels)) != len(observed_labels):
        raise ValueError("observed ablation labels must be distinct after normalization")
    if set(observed_labels) != set(expected_labels):
        raise ValueError("observed ablation membership must exactly match the predeclared plan")

    family_report = evaluate_search_quality_ablation_family(
        items,
        family_wise_alpha=plan.family_wise_alpha,
        minimum_required_ablations=len(expected_labels),
    )
    return PredeclaredAblationFamilyReport(
        plan_id=plan.plan_id.strip(),
        plan_sha256=plan.sha256(),
        expected_family_size=len(expected_labels),
        observed_family_size=len(items),
        family_membership_exact=True,
        thresholds_bound=True,
        family_report=family_report,
        acceptance_passed=family_report.acceptance_passed,
    )
