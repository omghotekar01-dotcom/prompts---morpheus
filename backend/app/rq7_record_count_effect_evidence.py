from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from .evidence_validation import EvidenceValidation
from .measurement_environment import (
    LOCAL_RECORD_EVIDENCE_STATE,
    validate_measurement_environment_record,
)
from .rq7_analysis_provenance import validate_rq7_analysis_provenance_payload
from .rq7_confirmatory_evidence import validate_rq7_confirmatory_analysis_payload


ROLE = "rq7_record_count_effect_evidence"
SCHEMA = "morpheus-rq7-record-count-effect-evidence-v1"
EVIDENCE_STATE = "SUPPORTED_RQ7_RECORD_COUNT_EFFECT_FOR_FROZEN_SINGLE_MACHINE_SCOPE"
CLAIM_SCOPE = "SYSTEMATIC_RECORD_COUNT_EFFECT_SUPPORTED_WITHIN_FROZEN_RQ7_SINGLE_MACHINE_SCOPE"

_TRUTH_BOUNDARIES = [
    "This attestation exists only when the frozen H7-v1 analysis reports SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE and the predeclared record-count decision is SUPPORTED.",
    "The effect is characterized over six frozen reader×transition blocks using per-cell medians, an exact two-sided sign test and a deterministic block bootstrap; timing repetitions are not treated as independent workloads.",
    "The measurement-environment record must cover all 24 cells in one fresh non-CI invocation with observable stable affinity and governor/power policy, but that metadata is not proof of perfect laboratory control.",
    "The attestation does not establish an asymptotic complexity law, superiority over another system, cross-machine generalization, concurrent-writer safety, cross-process replacement or production SLA behavior.",
]


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value != "0" * 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _finite_positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("RQ7 effect value must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError("RQ7 effect value must be finite and positive")
    return numeric


def _validated_supported_effect(analysis: Mapping[str, Any]) -> dict[str, Any]:
    validate_rq7_confirmatory_analysis_payload(analysis)
    if analysis.get("h7_decision") != "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE":
        raise ValueError("RQ7 record-count effect attestation requires H7 to be supported")
    record = analysis.get("record_count_effect")
    if not isinstance(record, Mapping):
        raise ValueError("RQ7 analysis lacks record-count effect")
    if record.get("confirmatory_decision_alpha_0_05") != "SUPPORTED":
        raise ValueError("RQ7 record-count effect attestation requires the frozen record-count decision to be SUPPORTED")
    if record.get("block_count") != 6:
        raise ValueError("RQ7 record-count effect attestation requires six matched blocks")
    ratio = _finite_positive(record.get("geometric_mean_cost_ratio_per_record_doubling"))
    ci = record.get("bootstrap_95_ci_cost_ratio_per_doubling")
    if not isinstance(ci, list) or len(ci) != 2:
        raise ValueError("RQ7 record-count effect attestation requires a two-bound bootstrap CI")
    ci_low = _finite_positive(ci[0])
    ci_high = _finite_positive(ci[1])
    if not 1.0 < ci_low <= ci_high:
        raise ValueError("supported RQ7 record-count effect requires bootstrap ratio CI strictly above one")
    sign = record.get("sign_test")
    if not isinstance(sign, Mapping) or sign.get("method") != "EXACT_TWO_SIDED_SIGN_TEST":
        raise ValueError("RQ7 record-count effect attestation requires the exact sign test")
    p_value = sign.get("p_two_sided")
    if isinstance(p_value, bool) or not isinstance(p_value, (int, float)) or not math.isfinite(float(p_value)):
        raise ValueError("RQ7 record-count effect attestation requires a finite sign-test p-value")
    if not 0.0 <= float(p_value) <= 0.05:
        raise ValueError("supported RQ7 record-count effect requires sign-test p <= 0.05")
    return {
        "matched_block_count": 6,
        "geometric_mean_cost_ratio_per_record_doubling": ratio,
        "bootstrap_95_ci_cost_ratio_per_doubling": [ci_low, ci_high],
        "bootstrap_rounds": record.get("bootstrap_rounds"),
        "bootstrap_seed": record.get("bootstrap_seed"),
        "exact_sign_test_p_two_sided": float(p_value),
        "confirmatory_decision_alpha_0_05": "SUPPORTED",
    }


def _validate_environment_for_supported_claim(environment: Mapping[str, Any]) -> None:
    validate_measurement_environment_record(environment)
    if environment.get("evidence_state") != LOCAL_RECORD_EVIDENCE_STATE:
        raise ValueError("RQ7 record-count effect attestation requires non-CI local environment metadata")
    coverage = environment.get("coverage")
    stability = environment.get("observed_stability")
    start = environment.get("start_snapshot")
    if not isinstance(coverage, Mapping) or not isinstance(stability, Mapping) or not isinstance(start, Mapping):
        raise ValueError("RQ7 record-count effect attestation requires environment coverage and stability")
    if coverage.get("complete_single_invocation_coverage") is not True:
        raise ValueError("RQ7 record-count effect attestation requires complete single-invocation environment coverage")
    if coverage.get("covered_experiment_count") != 24 or coverage.get("planned_experiments") != 24:
        raise ValueError("RQ7 record-count effect attestation requires environment coverage of all 24 cells")
    if coverage.get("resumed_from_campaign_sha256") is not None:
        raise ValueError("RQ7 record-count effect attestation does not accept resumed multi-invocation coverage")
    if stability.get("same_logical_cpu_count") is not True or stability.get("process_affinity_stable") is not True:
        raise ValueError("RQ7 record-count effect attestation requires observed stable CPU count and process affinity")
    power_observed = bool(start.get("linux_scaling_governors")) or start.get("windows_active_power_scheme") is not None
    power_stable = stability.get("linux_governors_stable") is True or stability.get("windows_power_scheme_stable") is True
    if not power_observed or not power_stable:
        raise ValueError("RQ7 record-count effect attestation requires an observable stable governor or Windows power scheme")


def build_rq7_record_count_effect_evidence(
    analysis: Mapping[str, Any],
    provenance: Mapping[str, Any],
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    effect = _validated_supported_effect(analysis)
    validate_rq7_analysis_provenance_payload(provenance)
    _validate_environment_for_supported_claim(environment)

    for field in ("analysis_sha256", "campaign_sha256", "manifest_sha256", "machine_fingerprint_sha256"):
        if provenance.get(field) != analysis.get(field):
            raise ValueError(f"RQ7 analysis provenance {field} does not match supported analysis")
    if environment.get("campaign_sha256") != analysis.get("campaign_sha256"):
        raise ValueError("RQ7 environment campaign does not match supported analysis")
    if environment.get("machine_fingerprint_sha256") != analysis.get("machine_fingerprint_sha256"):
        raise ValueError("RQ7 environment machine fingerprint does not match supported analysis")

    covered = environment["coverage"]["covered_experiment_ids"]
    expected_ids = [str(cell["experiment_id"]) for cell in analysis["raw_cells"]]
    if set(covered) != set(expected_ids) or len(covered) != len(expected_ids) or len(expected_ids) != 24:
        raise ValueError("RQ7 environment coverage does not match all supported analysis cells")

    core = {
        "schema": SCHEMA,
        "study_id": analysis["study_id"],
        "manifest_sha256": analysis["manifest_sha256"],
        "campaign_sha256": analysis["campaign_sha256"],
        "machine_fingerprint_sha256": analysis["machine_fingerprint_sha256"],
        "analysis_sha256": analysis["analysis_sha256"],
        "analysis_provenance_sha256": provenance["provenance_sha256"],
        "analysis_source_sha256": provenance["analysis_source_sha256"],
        "measurement_environment_record_sha256": environment["record_sha256"],
        "effect": effect,
        "reader_safety_decision": analysis["reader_safety"]["decision"],
        "h7_decision": analysis["h7_decision"],
        "evidence_state": EVIDENCE_STATE,
        "claim_scope": CLAIM_SCOPE,
        "truth_boundaries": list(_TRUTH_BOUNDARIES),
    }
    if core["reader_safety_decision"] != "ZERO_INVALID_OBSERVATIONS_FOR_FROZEN_CAMPAIGN":
        raise ValueError("RQ7 record-count effect attestation requires the zero-invalid-reader decision")
    return {**core, "attestation_sha256": _canonical_sha256(core)}


def validate_rq7_record_count_effect_evidence_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected RQ7 record-count effect evidence schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("RQ7 record-count effect evidence must target rq7-generated-migration-v1")
    for field in (
        "manifest_sha256",
        "campaign_sha256",
        "machine_fingerprint_sha256",
        "analysis_sha256",
        "analysis_provenance_sha256",
        "analysis_source_sha256",
        "measurement_environment_record_sha256",
        "attestation_sha256",
    ):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"RQ7 record-count effect evidence has invalid {field}")
    if payload.get("evidence_state") != EVIDENCE_STATE or payload.get("claim_scope") != CLAIM_SCOPE:
        raise ValueError("RQ7 record-count effect evidence state/scope is invalid")
    if payload.get("h7_decision") != "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE":
        raise ValueError("RQ7 record-count effect evidence requires supported H7 decision")
    if payload.get("reader_safety_decision") != "ZERO_INVALID_OBSERVATIONS_FOR_FROZEN_CAMPAIGN":
        raise ValueError("RQ7 record-count effect evidence requires zero-invalid-reader decision")
    effect = payload.get("effect")
    if not isinstance(effect, Mapping):
        raise ValueError("RQ7 record-count effect evidence lacks effect object")
    if effect.get("matched_block_count") != 6 or effect.get("confirmatory_decision_alpha_0_05") != "SUPPORTED":
        raise ValueError("RQ7 record-count effect evidence has invalid block/decision identity")
    ratio = _finite_positive(effect.get("geometric_mean_cost_ratio_per_record_doubling"))
    ci = effect.get("bootstrap_95_ci_cost_ratio_per_doubling")
    if not isinstance(ci, list) or len(ci) != 2:
        raise ValueError("RQ7 record-count effect evidence has invalid bootstrap CI")
    ci_low = _finite_positive(ci[0])
    ci_high = _finite_positive(ci[1])
    if ratio <= 1.0 or not 1.0 < ci_low <= ci_high:
        raise ValueError("RQ7 record-count effect evidence must encode a positive supported ratio effect")
    if effect.get("bootstrap_rounds") != 10_000 or effect.get("bootstrap_seed") != 7007:
        raise ValueError("RQ7 record-count effect evidence bootstrap protocol mismatch")
    p_value = effect.get("exact_sign_test_p_two_sided")
    if isinstance(p_value, bool) or not isinstance(p_value, (int, float)) or not 0.0 <= float(p_value) <= 0.05:
        raise ValueError("RQ7 record-count effect evidence requires exact sign-test p <= 0.05")
    if payload.get("truth_boundaries") != _TRUTH_BOUNDARIES:
        raise ValueError("RQ7 record-count effect evidence truth boundaries are invalid")
    core = {key: value for key, value in payload.items() if key != "attestation_sha256"}
    if _canonical_sha256(core) != payload.get("attestation_sha256"):
        raise ValueError("RQ7 record-count effect evidence attestation hash mismatch")


def validate_rq7_record_count_effect_evidence_bytes(data: bytes) -> EvidenceValidation:
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("record-count effect evidence is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid JSON: {exc.msg}",))
    if not isinstance(payload, dict):
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))
    try:
        validate_rq7_record_count_effect_evidence_payload(payload)
    except ValueError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (str(exc),))
    return EvidenceValidation(
        ROLE,
        True,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
        ("validated positive H7 record-count effect decision, uncertainty, source/provenance/environment identities and attestation hash",),
    )
