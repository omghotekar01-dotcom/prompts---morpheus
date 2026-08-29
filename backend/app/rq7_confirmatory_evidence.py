from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from .evidence_validation import EvidenceValidation
from .rq7_confirmatory_analysis import EVIDENCE_STATE, SCHEMA


ROLE = "rq7_confirmatory_analysis"
_RECORD_COUNTS = {128, 1024, 8192, 65536}
_READERS = {1, 4, 16}
_TRANSITIONS = {10, 100}


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _finite_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and (numeric > 0 if positive else True)


def validate_rq7_confirmatory_analysis_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected RQ7 confirmatory analysis schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("RQ7 confirmatory analysis must target rq7-generated-migration-v1")
    if payload.get("evidence_state") != EVIDENCE_STATE:
        raise ValueError("unexpected RQ7 confirmatory analysis evidence_state")
    for field in (
        "manifest_sha256",
        "campaign_sha256",
        "machine_profile_sha256",
        "machine_fingerprint_sha256",
        "analysis_sha256",
    ):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"RQ7 confirmatory analysis has invalid {field}")
    source = str(payload.get("source_candidate_id", "")).strip()
    target = str(payload.get("target_candidate_id", "")).strip()
    if not source or not target or source == target:
        raise ValueError("RQ7 confirmatory analysis requires distinct source/target candidate ids")
    if payload.get("primary_metric") != "migrate_validate_activate_ns_per":
        raise ValueError("RQ7 confirmatory analysis has unexpected primary_metric")
    if payload.get("analysis_unit") != "CELL_MEDIAN_WITH_MATCHED_FACTOR_BLOCKS":
        raise ValueError("RQ7 confirmatory analysis has unexpected analysis_unit")
    if payload.get("raw_repetitions_are_not_independent_workloads") is not True:
        raise ValueError("RQ7 confirmatory analysis must preserve the non-independence boundary")
    if payload.get("alpha") != 0.05:
        raise ValueError("RQ7 confirmatory analysis v1 requires alpha=0.05")
    if payload.get("h7_decision") not in {"SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE", "NOT_FULLY_CONFIRMED"}:
        raise ValueError("RQ7 confirmatory analysis has invalid h7_decision")

    record = payload.get("record_count_effect")
    if not isinstance(record, Mapping) or record.get("block_count") != 6:
        raise ValueError("RQ7 record-count effect requires six reader×transition blocks")
    slopes = record.get("block_slopes")
    if not isinstance(slopes, list) or len(slopes) != 6:
        raise ValueError("RQ7 record-count effect requires six block slopes")
    seen_record_blocks: set[tuple[int, int]] = set()
    for item in slopes:
        if not isinstance(item, Mapping):
            raise ValueError("RQ7 block slope must be an object")
        readers = item.get("readers")
        transitions = item.get("transitions")
        if readers not in _READERS or transitions not in _TRANSITIONS:
            raise ValueError("RQ7 block slope contains an out-of-matrix factor")
        key = (int(readers), int(transitions))
        if key in seen_record_blocks:
            raise ValueError("RQ7 record-count block slopes must be unique")
        seen_record_blocks.add(key)
        medians = item.get("cell_medians_ns")
        if not isinstance(medians, list) or len(medians) != 4 or not all(_finite_number(value, positive=True) for value in medians):
            raise ValueError("RQ7 record-count block slope requires four positive cell medians")
        if not _finite_number(item.get("log_cost_slope_per_record_doubling")) or not _finite_number(item.get("multiplicative_cost_ratio_per_doubling"), positive=True):
            raise ValueError("RQ7 record-count block slope has invalid effect values")
    if seen_record_blocks != {(reader, transition) for reader in _READERS for transition in _TRANSITIONS}:
        raise ValueError("RQ7 record-count block slopes do not cover the frozen matrix")
    if record.get("bootstrap_rounds") != 10_000 or record.get("bootstrap_seed") != 7007:
        raise ValueError("RQ7 record-count bootstrap protocol mismatch")
    record_ci = record.get("bootstrap_95_ci_cost_ratio_per_doubling")
    if not isinstance(record_ci, list) or len(record_ci) != 2 or not all(_finite_number(value, positive=True) for value in record_ci):
        raise ValueError("RQ7 record-count bootstrap CI is invalid")
    if record_ci[0] > record_ci[1]:
        raise ValueError("RQ7 record-count bootstrap CI is reversed")
    record_decision = record.get("confirmatory_decision_alpha_0_05")
    if record_decision not in {"SUPPORTED", "NOT_CONFIRMED"}:
        raise ValueError("RQ7 record-count confirmatory decision is invalid")
    if record_decision == "SUPPORTED" and record_ci[0] <= 1.0:
        raise ValueError("RQ7 supported record-count effect requires CI ratio lower bound > 1")

    reader = payload.get("reader_pressure_sensitivity")
    if not isinstance(reader, Mapping) or reader.get("family") != "RQ7_READER_PRESSURE_SENSITIVITY":
        raise ValueError("RQ7 reader-pressure family is invalid")
    contrasts = reader.get("contrasts")
    expected_contrasts = {"readers_4_vs_1", "readers_16_vs_1"}
    if not isinstance(contrasts, Mapping) or set(contrasts) != expected_contrasts:
        raise ValueError("RQ7 reader-pressure contrasts must be exactly 4-vs-1 and 16-vs-1")
    for label, contrast in contrasts.items():
        if not isinstance(contrast, Mapping) or contrast.get("block_count") != 8:
            raise ValueError(f"RQ7 reader contrast {label} requires eight matched blocks")
        if contrast.get("bootstrap_rounds") != 10_000 or contrast.get("bootstrap_seed") != 7007:
            raise ValueError(f"RQ7 reader contrast {label} bootstrap protocol mismatch")
        if not _finite_number(contrast.get("geometric_mean_ratio"), positive=True):
            raise ValueError(f"RQ7 reader contrast {label} has invalid effect ratio")
    correction = reader.get("multiple_comparison_correction")
    if not isinstance(correction, Mapping) or correction.get("method") != "HOLM_BONFERRONI_STEP_DOWN" or correction.get("family_size") != 2 or correction.get("alpha") != 0.05:
        raise ValueError("RQ7 reader-pressure Holm-Bonferroni family is invalid")
    hypotheses = correction.get("hypotheses")
    if not isinstance(hypotheses, list) or len(hypotheses) != 2 or {item.get("label") for item in hypotheses if isinstance(item, Mapping)} != expected_contrasts:
        raise ValueError("RQ7 reader-pressure Holm hypotheses do not match the declared contrasts")

    transition = payload.get("transition_count_robustness")
    if not isinstance(transition, Mapping) or transition.get("block_count") != 12 or transition.get("label") != "transitions_100_vs_10":
        raise ValueError("RQ7 transition-count robustness requires twelve matched blocks")
    if transition.get("bootstrap_rounds") != 10_000 or transition.get("bootstrap_seed") != 7007:
        raise ValueError("RQ7 transition-count bootstrap protocol mismatch")

    model = payload.get("global_log_cost_model")
    if not isinstance(model, Mapping) or model.get("model") != "ADDITIVE_OLS_ON_LOG_CELL_MEDIAN_COST" or model.get("cell_count") != 24:
        raise ValueError("RQ7 global log-cost model identity/cell count is invalid")
    if model.get("inference_use") != "DESCRIPTIVE_RESIDUAL_AND_EFFECT_SIZE_MODEL_ONLY":
        raise ValueError("RQ7 OLS model cannot be promoted to confirmatory p-value inference")
    residuals = model.get("residuals")
    if not isinstance(residuals, list) or len(residuals) != 24:
        raise ValueError("RQ7 global log-cost model requires 24 residual records")
    for field in ("r_squared", "rmse_log_cost", "max_abs_log_residual"):
        if not _finite_number(model.get(field)):
            raise ValueError(f"RQ7 global log-cost model has invalid {field}")

    safety = payload.get("reader_safety")
    if not isinstance(safety, Mapping) or safety.get("invalid_reader_observations") != 0:
        raise ValueError("RQ7 confirmatory analysis requires zero invalid reader observations")
    if not isinstance(safety.get("total_reader_observations"), int) or safety.get("total_reader_observations", 0) <= 0:
        raise ValueError("RQ7 confirmatory analysis requires positive reader observations")
    if safety.get("decision") != "ZERO_INVALID_OBSERVATIONS_FOR_FROZEN_CAMPAIGN":
        raise ValueError("RQ7 reader-safety decision is inconsistent")
    expected_h7_decision = (
        "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE"
        if record_decision == "SUPPORTED"
        else "NOT_FULLY_CONFIRMED"
    )
    if payload.get("h7_decision") != expected_h7_decision:
        raise ValueError("RQ7 h7_decision is inconsistent with the confirmatory record-count decision")

    raw_cells = payload.get("raw_cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != 24:
        raise ValueError("RQ7 confirmatory analysis requires all 24 raw factor cells")
    seen_cells: set[tuple[int, int, int]] = set()
    for cell in raw_cells:
        if not isinstance(cell, Mapping):
            raise ValueError("RQ7 raw cell must be an object")
        factors = cell.get("factors")
        if not isinstance(factors, Mapping):
            raise ValueError("RQ7 raw cell lacks factors")
        key = (int(factors.get("record_count", -1)), int(factors.get("readers", -1)), int(factors.get("transitions", -1)))
        if key[0] not in _RECORD_COUNTS or key[1] not in _READERS or key[2] not in _TRANSITIONS or key in seen_cells:
            raise ValueError("RQ7 raw cells contain duplicate or out-of-matrix factors")
        seen_cells.add(key)
        migrate = cell.get("migrate_validate_activate_ns_per")
        rollback = cell.get("rollback_ns_per")
        round_trip = cell.get("round_trip_transition_ns_per")
        if not all(isinstance(values, list) and len(values) == 10 for values in (migrate, rollback, round_trip)):
            raise ValueError("RQ7 raw cells require ten repetitions for all timing metrics")
        if not all(_finite_number(value, positive=True) for values in (migrate, rollback, round_trip) for value in values):
            raise ValueError("RQ7 raw timing observations must be positive finite numbers")
    expected_cells = {(record, readers, transitions) for record in _RECORD_COUNTS for readers in _READERS for transitions in _TRANSITIONS}
    if seen_cells != expected_cells:
        raise ValueError("RQ7 raw cells do not cover the frozen matrix")

    core = {key: value for key, value in payload.items() if key != "analysis_sha256"}
    if _canonical_sha256(core) != payload.get("analysis_sha256"):
        raise ValueError("RQ7 confirmatory analysis_sha256 does not match analysis content")


def validate_rq7_confirmatory_analysis_bytes(data: bytes) -> EvidenceValidation:
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("analysis is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid JSON: {exc.msg}",))
    if not isinstance(payload, dict):
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))
    try:
        validate_rq7_confirmatory_analysis_payload(payload)
    except ValueError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (str(exc),))
    return EvidenceValidation(
        ROLE,
        True,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED",
        ("validated H7-v1 matched-block analysis, Holm family, residual model, raw-cell coverage, reader-safety invariant and content hash",),
    )
