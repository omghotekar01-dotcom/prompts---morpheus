"""Deterministic provenance manifest for the MORPHEUS ablation research-evidence chain.

This module checks internal identity and provenance consistency only. It never promotes caller-supplied
research artifacts into a performance, novelty, publication, or production-control claim.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .search_quality_ablation_disclosure import (
    EVIDENCE_STATE as DISCLOSURE_EVIDENCE_STATE,
    AblationDisclosureReport,
)
from .search_quality_ablation_family import EVIDENCE_STATE as FAMILY_EVIDENCE_STATE
from .search_quality_ablation_preregistration import (
    EVIDENCE_STATE as PREREGISTRATION_EVIDENCE_STATE,
    PredeclaredAblationFamilyReport,
)
from .search_quality_ablation_validity import (
    EVIDENCE_STATE as VALIDITY_EVIDENCE_STATE,
    AblationValidityThreatsReport,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_BOUND_ABLATION_RESEARCH_EVIDENCE_MANIFEST"
TRUTH_BOUNDARY = (
    "This gate proves only deterministic internal binding and mutual consistency among one supplied preregistration "
    "report, its multiplicity-aware ablation-family result, complete supplied-family outcome disclosure, and the bound "
    "four-category threats-to-validity register. The manifest hash is a content/provenance identity, not an external "
    "timestamp or independent attestation. It does not prove that the plan was registered before results were observed, "
    "that every attempted analysis exists inside the supplied family, that disclosure notes are unbiased, that listed "
    "threat mitigations worked, or that the sample is representative or independent. Passing this integrity gate does "
    "not establish causal validity, publication-grade evidence, benchmark or search superiority, novelty, patentability, "
    "production readiness, or automatic-control authorization."
)


def _validated_sha256(name: str, value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a 64-character hexadecimal SHA-256 digest")
    return normalized


def _normalized_nonempty(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


@dataclass(frozen=True)
class AblationResearchEvidenceManifest:
    plan_id: str
    plan_sha256: str
    disclosure_sha256: str
    threats_sha256: str
    family_size: int
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    reference_label: str
    workload_count: int
    candidate_count: int
    top_k: int
    family_wise_alpha: float
    correction_method: str
    family_acceptance_passed: bool
    disclosed_accepted_count: int
    disclosed_not_accepted_count: int
    evidence_manifest_sha256: str
    integrity_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "disclosure_sha256": self.disclosure_sha256,
            "threats_sha256": self.threats_sha256,
            "family_size": self.family_size,
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "reference_label": self.reference_label,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "family_wise_alpha": self.family_wise_alpha,
            "correction_method": self.correction_method,
            "family_acceptance_passed": self.family_acceptance_passed,
            "disclosed_accepted_count": self.disclosed_accepted_count,
            "disclosed_not_accepted_count": self.disclosed_not_accepted_count,
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
            "integrity_passed": self.integrity_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def build_ablation_research_evidence_manifest(
    preregistered_report: PredeclaredAblationFamilyReport,
    disclosure_report: AblationDisclosureReport,
    validity_report: AblationValidityThreatsReport,
) -> AblationResearchEvidenceManifest:
    """Fail closed unless all supplied ablation-research artifacts form one internally consistent chain."""

    if preregistered_report.evidence_state != PREREGISTRATION_EVIDENCE_STATE:
        raise ValueError("preregistered_report has an incompatible evidence_state")
    if disclosure_report.evidence_state != DISCLOSURE_EVIDENCE_STATE:
        raise ValueError("disclosure_report has an incompatible evidence_state")
    if validity_report.evidence_state != VALIDITY_EVIDENCE_STATE:
        raise ValueError("validity_report has an incompatible evidence_state")

    family = preregistered_report.family_report
    if family.evidence_state != FAMILY_EVIDENCE_STATE:
        raise ValueError("family_report has an incompatible evidence_state")
    if (
        preregistered_report.automatic_control_allowed
        or disclosure_report.automatic_control_allowed
        or validity_report.automatic_control_allowed
        or family.automatic_control_allowed
    ):
        raise ValueError("research evidence cannot authorize automatic control")

    if not preregistered_report.family_membership_exact or not preregistered_report.thresholds_bound:
        raise ValueError("preregistered_report must have exact family and threshold binding")
    if not disclosure_report.acceptance_passed or not disclosure_report.membership_complete:
        raise ValueError("disclosure_report must prove complete supplied-family disclosure")
    if not disclosure_report.outcome_classification_exact:
        raise ValueError("disclosure_report must bind exact outcome classification")
    if not validity_report.acceptance_passed or not validity_report.category_coverage_complete:
        raise ValueError("validity_report must prove complete required-category coverage")

    plan_id = _normalized_nonempty("plan_id", preregistered_report.plan_id)
    if disclosure_report.plan_id.strip() != plan_id or validity_report.plan_id.strip() != plan_id:
        raise ValueError("plan_id mismatch across the research evidence chain")

    plan_sha256 = _validated_sha256("plan_sha256", preregistered_report.plan_sha256)
    if _validated_sha256("disclosure plan_sha256", disclosure_report.plan_sha256) != plan_sha256:
        raise ValueError("plan_sha256 mismatch between preregistration and disclosure")
    if _validated_sha256("validity plan_sha256", validity_report.plan_sha256) != plan_sha256:
        raise ValueError("plan_sha256 mismatch between preregistration and validity evidence")

    disclosure_sha256 = _validated_sha256("disclosure_sha256", disclosure_report.disclosure_sha256)
    if _validated_sha256("validity disclosure_sha256", validity_report.disclosure_sha256) != disclosure_sha256:
        raise ValueError("disclosure_sha256 mismatch between disclosure and validity evidence")
    threats_sha256 = _validated_sha256("threats_sha256", validity_report.threats_sha256)

    family_size = preregistered_report.expected_family_size
    if family_size < 2:
        raise ValueError("research evidence family must contain at least 2 ablations")
    if preregistered_report.observed_family_size != family_size:
        raise ValueError("preregistered observed family size is inconsistent")
    if family.family_size != family_size or len(family.members) != family_size:
        raise ValueError("multiplicity-aware family size is inconsistent")
    if disclosure_report.family_size != family_size or disclosure_report.disclosed_count != family_size:
        raise ValueError("disclosure family size is inconsistent")
    if validity_report.family_size != family_size:
        raise ValueError("validity family size is inconsistent")
    if disclosure_report.accepted_count + disclosure_report.not_accepted_count != family_size:
        raise ValueError("disclosure outcome counts are inconsistent")

    source = _normalized_nonempty("measurement_source_id", family.measurement_source_id)
    protocol = _normalized_nonempty("protocol", family.protocol)
    machine = _normalized_nonempty("machine_fingerprint", family.machine_fingerprint)
    reference = _normalized_nonempty("reference_label", family.reference_label)
    if family.workload_count < 1 or family.candidate_count < 1 or family.top_k < 1:
        raise ValueError("family workload_count, candidate_count, and top_k must be positive")
    if not 0.0 < family.family_wise_alpha <= 1.0:
        raise ValueError("family_wise_alpha must be in (0, 1]")
    correction_method = _normalized_nonempty("correction_method", family.correction_method)

    seen_labels: set[str] = set()
    members: list[dict[str, object]] = []
    for member in family.members:
        label = _normalized_nonempty("ablated_label", member.ablated_label)
        key = label.casefold()
        if key in seen_labels:
            raise ValueError("family members must have distinct normalized ablated_label values")
        seen_labels.add(key)
        members.append(
            {
                "ablated_label": key,
                "raw_one_sided_p_value": member.raw_one_sided_p_value,
                "holm_adjusted_p_value": member.holm_adjusted_p_value,
                "effect_acceptance_passed": member.effect_acceptance_passed,
                "multiplicity_acceptance_passed": member.multiplicity_acceptance_passed,
            }
        )
    members.sort(key=lambda item: str(item["ablated_label"]))

    payload = {
        "plan_id": plan_id,
        "plan_sha256": plan_sha256,
        "disclosure_sha256": disclosure_sha256,
        "threats_sha256": threats_sha256,
        "family_size": family_size,
        "measurement_source_id": source,
        "protocol": protocol,
        "machine_fingerprint": machine,
        "reference_label": reference,
        "workload_count": family.workload_count,
        "candidate_count": family.candidate_count,
        "top_k": family.top_k,
        "family_wise_alpha": family.family_wise_alpha,
        "correction_method": correction_method,
        "members": members,
        "family_acceptance_passed": family.acceptance_passed,
        "disclosed_accepted_count": disclosure_report.accepted_count,
        "disclosed_not_accepted_count": disclosure_report.not_accepted_count,
        "validity_threat_count": validity_report.threat_count,
        "covered_categories": list(validity_report.covered_categories),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    manifest_sha256 = hashlib.sha256(encoded).hexdigest()

    return AblationResearchEvidenceManifest(
        plan_id=plan_id,
        plan_sha256=plan_sha256,
        disclosure_sha256=disclosure_sha256,
        threats_sha256=threats_sha256,
        family_size=family_size,
        measurement_source_id=source,
        protocol=protocol,
        machine_fingerprint=machine,
        reference_label=reference,
        workload_count=family.workload_count,
        candidate_count=family.candidate_count,
        top_k=family.top_k,
        family_wise_alpha=family.family_wise_alpha,
        correction_method=correction_method,
        family_acceptance_passed=family.acceptance_passed,
        disclosed_accepted_count=disclosure_report.accepted_count,
        disclosed_not_accepted_count=disclosure_report.not_accepted_count,
        evidence_manifest_sha256=manifest_sha256,
        integrity_passed=True,
    )
