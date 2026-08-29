from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")


@dataclass(frozen=True)
class ClaimRule:
    claim_type: str
    required_roles: frozenset[str]
    truth_boundary: str


@dataclass(frozen=True)
class ClaimDecision:
    claim_type: str
    allowed: bool
    present_roles: tuple[str, ...]
    missing_roles: tuple[str, ...]
    truth_boundary: str
    evidence_state: str

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_type": self.claim_type,
            "allowed": self.allowed,
            "present_roles": list(self.present_roles),
            "missing_roles": list(self.missing_roles),
            "truth_boundary": self.truth_boundary,
            "evidence_state": self.evidence_state,
        }


_RULES: dict[str, ClaimRule] = {
    "generated_cpp20": ClaimRule("generated_cpp20", frozenset({"generated_header"}), "A stored source artifact proves generation only; it does not prove compilation, correctness, or performance."),
    "artifact_compiles": ClaimRule("artifact_compiles", frozenset({"compile_verification_manifest"}), "Compile evidence is toolchain/environment specific and is not semantic correctness evidence."),
    "artifact_correct_supported_routes": ClaimRule("artifact_correct_supported_routes", frozenset({"full_artifact_verification_manifest"}), "The differential gate covers the supported generated routes and tested operation sequences, not arbitrary concurrency or unsupported semantics."),
    "measured_speedup": ClaimRule(
        "measured_speedup",
        frozenset({"experiment_manifest", "raw_measurements", "statistical_summary", "machine_profile", "baseline_manifest"}),
        "A speedup claim is scoped to the frozen benchmark matrix, baseline identities, machine/toolchain and statistical protocol represented by the evidence bundle.",
    ),
    "beam_search_quality": ClaimRule("beam_search_quality", frozenset({"experiment_manifest", "search_quality_report"}), "Search-quality evidence against MORPHEUS's bounded model oracle is not the same as measured hardware optimality."),
    "calibration_improves_decisions": ClaimRule("calibration_improves_decisions", frozenset({"experiment_manifest", "raw_measurements", "prediction_evaluation", "machine_profile"}), "Calibration benefit must be evaluated on held-out measurements from the declared machine/workload protocol."),
    "distribution_calibration_evidence": ClaimRule("distribution_calibration_evidence", frozenset({"distribution_calibration_manifest", "raw_measurements", "machine_profile"}), "This claim establishes a content-hashed primitive calibration package bound to declared access distributions, implementation identities and machine provenance; it is not end-to-end candidate performance evidence."),
    "distribution_calibration_improves_decisions": ClaimRule(
        "distribution_calibration_improves_decisions",
        frozenset({"experiment_manifest", "distribution_calibration_manifest", "raw_measurements", "prediction_evaluation", "machine_profile"}),
        "Distribution-aware calibration benefit requires held-out decision evaluation plus exact distribution/implementation/machine provenance; primitive calibration alone cannot establish decision improvement.",
    ),
    "runtime_adaptation_benefit": ClaimRule("runtime_adaptation_benefit", frozenset({"experiment_manifest", "raw_measurements", "transition_cost_report", "statistical_summary", "runtime_trace"}), "Adaptation benefit must include transition cost and is scoped to the measured drift scenario."),
    "same_process_generated_migration": ClaimRule(
        "same_process_generated_migration",
        frozenset({"generated_migration_verification_manifest"}),
        "This claim is limited to a provenance-bound pair of generated configurations completing logical-state transfer, shadow validation, atomic same-process publication, concurrent immutable-reader checks, a post-publication health gate and rollback on a recorded local toolchain. It does not establish concurrent-writer migration, cross-process/distributed hot replacement, production availability or performance superiority.",
    ),
    "generated_migration_transition_cost_measured": ClaimRule(
        "generated_migration_transition_cost_measured",
        frozenset({"experiment_manifest", "generated_migration_campaign", "generated_migration_campaign_summary", "generated_migration_transition_cost_evidence", "machine_profile"}),
        "This claim establishes measured same-process generated-migration transition costs only for the complete frozen RQ7 matrix on the packaged machine/toolchain identity. The required attestation is unavailable to CI-smoke, partial or mixed-environment campaigns. It does not establish a scaling law, performance superiority, cross-machine generalization, concurrent-writer migration, cross-process replacement or production SLA behavior.",
    ),
    "rq7_systematic_record_count_effect": ClaimRule(
        "rq7_systematic_record_count_effect",
        frozenset({
            "experiment_manifest",
            "generated_migration_campaign",
            "generated_migration_transition_cost_evidence",
            "measurement_environment_record",
            "rq7_analysis_provenance",
            "rq7_analysis_source",
            "rq7_confirmatory_analysis",
            "rq7_record_count_effect_evidence",
            "machine_profile",
        }),
        "This claim permits only the H7-v1 positive conclusion authorized by the packaged rq7_record_count_effect_evidence attestation: a systematic record-count effect was supported within the frozen users_demo workload, generated candidate pair, factor matrix and single machine/toolchain identity, with start/end environment metadata covering all 24 cells in one non-CI measurement invocation. The result is bound to exact packaged H7 analysis source bytes and recorded Python runtime. If H7 is not confirmed, the positive-result attestation cannot be minted and this claim remains blocked. Environment/source provenance improve auditability but do not prove perfect laboratory control or cross-runtime equivalence. This is not an asymptotic complexity law, a cross-machine generalization, a performance-superiority claim, or evidence for concurrent-writer/cross-process production migration.",
    ),
    "live_hot_swap": ClaimRule("live_hot_swap", frozenset({"live_swap_manifest", "concurrent_stress_report", "rollback_report"}), "A live-hot-swap claim requires data-plane transition evidence under concurrent access, not merely control-plane authorization or the narrower same-process generated-migration verifier."),
    "state_of_art": ClaimRule(
        "state_of_art",
        frozenset({"experiment_manifest", "raw_measurements", "statistical_summary", "machine_profile", "external_baseline_manifest", "prior_art_matrix"}),
        "State-of-the-art language is permitted only for the exact evaluated scope and contemporary external baselines; broad universal superiority is never inferred.",
    ),
}


def known_claim_types() -> tuple[str, ...]:
    return tuple(sorted(_RULES))


def _canonicalize_roles(evidence_roles: Iterable[str]) -> frozenset[str]:
    canonical: set[str] = set()
    for role in evidence_roles:
        if not isinstance(role, str):
            raise TypeError("evidence roles must be strings")
        if role != role.strip() or not _ROLE_RE.fullmatch(role):
            raise ValueError(f"invalid evidence role identity: {role!r}")
        if role in canonical:
            raise ValueError(f"duplicate evidence role: {role}")
        canonical.add(role)
    return frozenset(canonical)


def evaluate_claim(claim_type: str, evidence_roles: Iterable[str]) -> ClaimDecision:
    try:
        rule = _RULES[claim_type]
    except KeyError as exc:
        raise ValueError(f"unknown claim type: {claim_type}") from exc
    present = _canonicalize_roles(evidence_roles)
    missing = rule.required_roles - present
    allowed = not missing
    return ClaimDecision(
        claim_type=claim_type,
        allowed=allowed,
        present_roles=tuple(sorted(present)),
        missing_roles=tuple(sorted(missing)),
        truth_boundary=rule.truth_boundary,
        evidence_state="CLAIM_EVIDENCE_GATE_SATISFIED" if allowed else "CLAIM_EVIDENCE_INCOMPLETE",
    )


def evaluate_claim_bundle(claims: Iterable[tuple[str, Iterable[str]]]) -> dict[str, object]:
    decisions = [evaluate_claim(claim_type, roles) for claim_type, roles in claims]
    allowed = all(item.allowed for item in decisions)
    return {
        "allowed": allowed,
        "decisions": [item.as_dict() for item in decisions],
        "evidence_state": "RELEASE_CLAIM_BUNDLE_EVIDENCE_COMPLETE" if allowed else "RELEASE_CLAIM_BUNDLE_BLOCKED_BY_MISSING_EVIDENCE",
    }
