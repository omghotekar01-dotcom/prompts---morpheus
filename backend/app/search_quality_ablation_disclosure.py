from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .search_quality_ablation_preregistration import (
    EVIDENCE_STATE as PREREGISTRATION_EVIDENCE_STATE,
    PredeclaredAblationFamilyReport,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_COMPLETE_PREDECLARED_ABLATION_OUTCOME_DISCLOSURE"
TRUTH_BOUNDARY = (
    "This gate requires a caller-supplied disclosure entry for every member of one already-bound predeclared ablation "
    "family, including members whose multiplicity-aware result is not accepted. It deterministically binds disclosure "
    "membership and outcome classification to the supplied preregistration report and rejects omitted, duplicated, "
    "substituted, or misclassified family members. This is a machine-checkable completeness mechanism for the supplied "
    "family, not proof that the family itself was externally preregistered, that every experiment ever attempted was "
    "included, that narrative notes are unbiased or sufficient, or that selective reporting outside the supplied plan "
    "did not occur. A complete disclosure does not establish causal attribution, representative sampling, publication-"
    "grade evidence, superiority, novelty, patentability, or production-control authorization."
)


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _normalized_label(value: str) -> str:
    return _normalized_nonempty("ablated_label", value).casefold()


@dataclass(frozen=True)
class AblationOutcomeDisclosure:
    ablated_label: str
    outcome: str
    interpretation_note: str

    def canonical_payload(self) -> dict[str, str]:
        outcome = _normalized_nonempty("outcome", self.outcome).casefold()
        if outcome not in {"accepted", "not_accepted"}:
            raise ValueError("outcome must be 'accepted' or 'not_accepted'")
        return {
            "ablated_label": _normalized_label(self.ablated_label),
            "outcome": outcome,
            "interpretation_note": _normalized_nonempty("interpretation_note", self.interpretation_note),
        }


@dataclass(frozen=True)
class AblationDisclosureReport:
    plan_id: str
    plan_sha256: str
    family_size: int
    disclosed_count: int
    accepted_count: int
    not_accepted_count: int
    membership_complete: bool
    outcome_classification_exact: bool
    disclosure_sha256: str
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "family_size": self.family_size,
            "disclosed_count": self.disclosed_count,
            "accepted_count": self.accepted_count,
            "not_accepted_count": self.not_accepted_count,
            "membership_complete": self.membership_complete,
            "outcome_classification_exact": self.outcome_classification_exact,
            "disclosure_sha256": self.disclosure_sha256,
            "acceptance_passed": self.acceptance_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def evaluate_ablation_outcome_disclosure(
    preregistered_report: PredeclaredAblationFamilyReport,
    disclosures: Iterable[AblationOutcomeDisclosure],
) -> AblationDisclosureReport:
    """Require complete outcome disclosure for one supplied predeclared ablation family."""

    if preregistered_report.evidence_state != PREREGISTRATION_EVIDENCE_STATE:
        raise ValueError("preregistered_report has an incompatible evidence_state")
    if preregistered_report.automatic_control_allowed:
        raise ValueError("research evidence cannot authorize automatic control")
    if not preregistered_report.family_membership_exact or not preregistered_report.thresholds_bound:
        raise ValueError("preregistered_report must have exact family and threshold binding")

    family = preregistered_report.family_report
    if family.automatic_control_allowed:
        raise ValueError("family evidence cannot authorize automatic control")
    if family.family_size != preregistered_report.expected_family_size:
        raise ValueError("family size is inconsistent with the predeclared report")

    expected: dict[str, str] = {}
    for member in family.members:
        key = _normalized_label(member.ablated_label)
        if key in expected:
            raise ValueError("family contains duplicate normalized ablation labels")
        expected[key] = "accepted" if (
            member.effect_acceptance_passed and member.multiplicity_acceptance_passed
        ) else "not_accepted"

    items = tuple(disclosures)
    if len(items) != len(expected):
        raise ValueError("disclosure count must exactly match the predeclared family size")

    canonical_entries: list[dict[str, str]] = []
    observed: dict[str, str] = {}
    for disclosure in items:
        payload = disclosure.canonical_payload()
        label = payload["ablated_label"]
        if label in observed:
            raise ValueError("disclosures must use distinct normalized ablation labels")
        if label not in expected:
            raise ValueError("disclosure membership must exactly match the predeclared family")
        if payload["outcome"] != expected[label]:
            raise ValueError("disclosed outcome does not match the multiplicity-aware family result")
        observed[label] = payload["outcome"]
        canonical_entries.append(payload)

    if set(observed) != set(expected):
        raise ValueError("disclosure membership must exactly match the predeclared family")

    canonical_entries.sort(key=lambda item: item["ablated_label"])
    encoded = json.dumps(canonical_entries, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    disclosure_sha256 = hashlib.sha256(encoded).hexdigest()
    accepted_count = sum(outcome == "accepted" for outcome in observed.values())
    not_accepted_count = len(observed) - accepted_count

    return AblationDisclosureReport(
        plan_id=preregistered_report.plan_id,
        plan_sha256=preregistered_report.plan_sha256,
        family_size=len(expected),
        disclosed_count=len(observed),
        accepted_count=accepted_count,
        not_accepted_count=not_accepted_count,
        membership_complete=True,
        outcome_classification_exact=True,
        disclosure_sha256=disclosure_sha256,
        acceptance_passed=True,
    )
