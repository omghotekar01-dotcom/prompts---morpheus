from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .search_quality_ablation_disclosure import (
    EVIDENCE_STATE as DISCLOSURE_EVIDENCE_STATE,
    AblationDisclosureReport,
)
from .search_quality_ablation_preregistration import (
    EVIDENCE_STATE as PREREGISTRATION_EVIDENCE_STATE,
    PredeclaredAblationFamilyReport,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_BOUND_ABLATION_THREATS_TO_VALIDITY_REGISTER"
REQUIRED_CATEGORIES = (
    "construct_validity",
    "internal_validity",
    "external_validity",
    "statistical_conclusion_validity",
)
ALLOWED_RESIDUAL_RISK = {"low", "medium", "high", "unknown"}
TRUTH_BOUNDARY = (
    "This gate requires an explicit caller-supplied threats-to-validity register bound to one predeclared ablation plan "
    "and its complete supplied-family outcome disclosure. It proves deterministic coverage and identity binding for the "
    "four required validity categories only. It does not prove that the listed threats are exhaustive, that mitigations "
    "were effective, that residual-risk labels are independently justified, that the experiment family was externally "
    "preregistered, or that unreported analyses do not exist. Passing this methodology gate does not establish causal "
    "validity, representative sampling, publication-grade evidence, benchmark superiority, novelty, patentability, or "
    "production-control authorization."
)


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _normalized_category(value: str) -> str:
    return _normalized_nonempty("category", value).casefold().replace("-", "_").replace(" ", "_")


@dataclass(frozen=True)
class ValidityThreatEntry:
    category: str
    threat: str
    mitigation_or_control: str
    residual_risk: str

    def canonical_payload(self) -> dict[str, str]:
        category = _normalized_category(self.category)
        residual_risk = _normalized_nonempty("residual_risk", self.residual_risk).casefold()
        if residual_risk not in ALLOWED_RESIDUAL_RISK:
            raise ValueError("residual_risk must be one of: high, low, medium, unknown")
        return {
            "category": category,
            "threat": _normalized_nonempty("threat", self.threat),
            "mitigation_or_control": _normalized_nonempty("mitigation_or_control", self.mitigation_or_control),
            "residual_risk": residual_risk,
        }


@dataclass(frozen=True)
class AblationValidityThreatsReport:
    plan_id: str
    plan_sha256: str
    disclosure_sha256: str
    family_size: int
    threat_count: int
    covered_categories: tuple[str, ...]
    category_coverage_complete: bool
    threats_sha256: str
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "disclosure_sha256": self.disclosure_sha256,
            "family_size": self.family_size,
            "threat_count": self.threat_count,
            "covered_categories": list(self.covered_categories),
            "category_coverage_complete": self.category_coverage_complete,
            "threats_sha256": self.threats_sha256,
            "acceptance_passed": self.acceptance_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def evaluate_ablation_validity_threats(
    preregistered_report: PredeclaredAblationFamilyReport,
    disclosure_report: AblationDisclosureReport,
    threats: Iterable[ValidityThreatEntry],
) -> AblationValidityThreatsReport:
    """Bind an explicit four-category validity-threat register to one disclosed ablation family."""

    if preregistered_report.evidence_state != PREREGISTRATION_EVIDENCE_STATE:
        raise ValueError("preregistered_report has an incompatible evidence_state")
    if disclosure_report.evidence_state != DISCLOSURE_EVIDENCE_STATE:
        raise ValueError("disclosure_report has an incompatible evidence_state")
    if preregistered_report.automatic_control_allowed or disclosure_report.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not preregistered_report.family_membership_exact or not preregistered_report.thresholds_bound:
        raise ValueError("preregistered_report must have exact family and threshold binding")
    if not disclosure_report.acceptance_passed or not disclosure_report.membership_complete:
        raise ValueError("disclosure_report must prove complete supplied-family disclosure")
    if not disclosure_report.outcome_classification_exact:
        raise ValueError("disclosure_report must bind exact outcome classification")
    if disclosure_report.plan_id != preregistered_report.plan_id:
        raise ValueError("plan_id mismatch between preregistration and disclosure")
    if disclosure_report.plan_sha256 != preregistered_report.plan_sha256:
        raise ValueError("plan_sha256 mismatch between preregistration and disclosure")
    if disclosure_report.family_size != preregistered_report.expected_family_size:
        raise ValueError("family_size mismatch between preregistration and disclosure")

    items = tuple(threats)
    if len(items) < len(REQUIRED_CATEGORIES):
        raise ValueError("threats register must include at least one entry for every required validity category")

    canonical_entries: list[dict[str, str]] = []
    covered: set[str] = set()
    seen_entries: set[tuple[str, str]] = set()
    for entry in items:
        payload = entry.canonical_payload()
        category = payload["category"]
        if category not in REQUIRED_CATEGORIES:
            raise ValueError("category must be one of the required validity categories")
        identity = (category, payload["threat"].casefold())
        if identity in seen_entries:
            raise ValueError("duplicate normalized threat entry")
        seen_entries.add(identity)
        covered.add(category)
        canonical_entries.append(payload)

    if covered != set(REQUIRED_CATEGORIES):
        raise ValueError("threats register must cover all required validity categories")

    canonical_entries.sort(key=lambda item: (item["category"], item["threat"].casefold(), item["mitigation_or_control"], item["residual_risk"]))
    encoded = json.dumps(canonical_entries, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    threats_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationValidityThreatsReport(
        plan_id=preregistered_report.plan_id,
        plan_sha256=preregistered_report.plan_sha256,
        disclosure_sha256=disclosure_report.disclosure_sha256,
        family_size=disclosure_report.family_size,
        threat_count=len(canonical_entries),
        covered_categories=tuple(sorted(covered)),
        category_coverage_complete=True,
        threats_sha256=threats_sha256,
        acceptance_passed=True,
    )
