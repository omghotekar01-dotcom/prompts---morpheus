from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .generated_migration_campaign import GeneratedMigrationCampaignReport
from .multiple_comparisons import holm_bonferroni


SCHEMA = "morpheus-rq7-confirmatory-analysis-v1"
EVIDENCE_STATE = "CONFIRMATORY_ANALYSIS_OF_COMPLETE_LOCAL_RQ7_CAMPAIGN"
_RECORD_COUNTS = (128, 1024, 8192, 65536)
_READERS = (1, 4, 16)
_TRANSITIONS = (10, 100)
_REPETITIONS = 10
_BOOTSTRAP_ROUNDS = 10_000
_BOOTSTRAP_SEED = 7007
_ALPHA = 0.05


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(float(value) for value in values)
    if probability <= 0:
        return ordered[0]
    if probability >= 1:
        return ordered[-1]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _exact_two_sided_sign_test(values: Iterable[float], *, tolerance: float = 1e-15) -> dict[str, Any]:
    positive = negative = ties = 0
    for raw in values:
        value = float(raw)
        if value > tolerance:
            positive += 1
        elif value < -tolerance:
            negative += 1
        else:
            ties += 1
    n = positive + negative
    if n == 0:
        p_value = None
    else:
        tail = min(positive, negative)
        one_tail = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
        p_value = min(1.0, 2.0 * one_tail)
    return {
        "positive": positive,
        "negative": negative,
        "ties": ties,
        "non_ties": n,
        "p_two_sided": p_value,
        "method": "EXACT_TWO_SIDED_SIGN_TEST",
    }


def _bootstrap_mean_ci(values: Sequence[float]) -> tuple[float, float]:
    if len(values) < 2:
        raise ValueError("bootstrap requires at least two resampling units")
    rng = random.Random(_BOOTSTRAP_SEED)
    numeric = [float(value) for value in values]
    n = len(numeric)
    means = [statistics.fmean(numeric[rng.randrange(n)] for _ in range(n)) for _ in range(_BOOTSTRAP_ROUNDS)]
    return _quantile(means, 0.025), _quantile(means, 0.975)


def _simple_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("slope requires equal-length vectors with at least two points")
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0:
        raise ValueError("slope predictor has zero variance")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator


def _solve_linear_system(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    n = len(vector)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("linear system must be square")
    augmented = [list(map(float, row)) + [float(vector[index])] for index, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise ValueError("design matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            augmented[row] = [
                current - factor * reference
                for current, reference in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[row][-1] for row in range(n)]


def _ols(design: Sequence[Sequence[float]], response: Sequence[float]) -> tuple[list[float], list[float], float]:
    if len(design) != len(response) or not design:
        raise ValueError("OLS requires non-empty aligned design/response")
    columns = len(design[0])
    if columns == 0 or any(len(row) != columns for row in design):
        raise ValueError("OLS design rows must have equal non-zero width")
    xtx = [[0.0 for _ in range(columns)] for _ in range(columns)]
    xty = [0.0 for _ in range(columns)]
    for row, target in zip(design, response, strict=True):
        for i in range(columns):
            xty[i] += row[i] * target
            for j in range(columns):
                xtx[i][j] += row[i] * row[j]
    coefficients = _solve_linear_system(xtx, xty)
    residuals = [
        target - sum(coefficient * feature for coefficient, feature in zip(coefficients, row, strict=True))
        for row, target in zip(design, response, strict=True)
    ]
    mean_response = statistics.fmean(response)
    total = sum((value - mean_response) ** 2 for value in response)
    residual_sum = sum(value**2 for value in residuals)
    r_squared = 1.0 - residual_sum / total if total > 0 else 1.0
    return coefficients, residuals, r_squared


@dataclass(frozen=True)
class _Cell:
    experiment_id: str
    record_count: int
    readers: int
    transitions: int
    migrate: tuple[int, ...]
    rollback: tuple[int, ...]

    @property
    def migrate_median(self) -> float:
        return float(statistics.median(self.migrate))

    @property
    def rollback_median(self) -> float:
        return float(statistics.median(self.rollback))

    def raw_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "factors": {
                "record_count": self.record_count,
                "readers": self.readers,
                "transitions": self.transitions,
            },
            "migrate_validate_activate_ns_per": list(self.migrate),
            "rollback_ns_per": list(self.rollback),
            "round_trip_transition_ns_per": [migrate + rollback for migrate, rollback in zip(self.migrate, self.rollback, strict=True)],
            "migrate_median_ns": self.migrate_median,
            "rollback_median_ns": self.rollback_median,
        }


def _validated_cells(campaign: GeneratedMigrationCampaignReport) -> dict[tuple[int, int, int], _Cell]:
    if campaign.study_id != "rq7-generated-migration-v1":
        raise ValueError("H7 analysis requires RQ7 v1")
    if not campaign.complete or not campaign.comparable_environment:
        raise ValueError("H7 analysis requires a complete comparable RQ7 campaign")
    if campaign.evidence_state != "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS":
        raise ValueError("H7 analysis requires complete non-CI local measurements")
    if len(campaign.entries) != len(_RECORD_COUNTS) * len(_READERS) * len(_TRANSITIONS):
        raise ValueError("H7 analysis requires all 24 frozen factor cells")

    cells: dict[tuple[int, int, int], _Cell] = {}
    for entry in campaign.entries:
        factors = entry.factors
        record_count = int(factors.get("record_count", -1))
        readers = int(factors.get("readers", -1))
        transitions = int(factors.get("transitions", -1))
        if record_count not in _RECORD_COUNTS or readers not in _READERS or transitions not in _TRANSITIONS:
            raise ValueError("H7 campaign contains a factor outside the frozen v1 matrix")
        key = (record_count, readers, transitions)
        if key in cells:
            raise ValueError("H7 campaign contains duplicate factor cells")
        report = entry.report
        if not report.success or report.evidence_state != "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST":
            raise ValueError("H7 analysis cannot consume failed, CI-smoke or mixed-environment reports")
        if report.config.record_count != record_count or report.config.readers != readers or report.config.transitions != transitions:
            raise ValueError("H7 report configuration differs from frozen factor identity")
        if report.config.repetitions != _REPETITIONS or len(report.rows) != _REPETITIONS:
            raise ValueError("H7 v1 requires exactly 10 repetitions per factor cell")
        if any(row.invalid_reads != 0 for row in report.rows):
            raise ValueError("H7 reader-safety analysis requires zero invalid reader observations")
        migrate = tuple(int(row.migrate_validate_activate_ns_per) for row in report.rows)
        rollback = tuple(int(row.rollback_ns_per) for row in report.rows)
        if any(value <= 0 for value in (*migrate, *rollback)):
            raise ValueError("H7 timing observations must be strictly positive")
        cells[key] = _Cell(entry.experiment_id, record_count, readers, transitions, migrate, rollback)

    expected = {(record_count, readers, transitions) for record_count in _RECORD_COUNTS for readers in _READERS for transitions in _TRANSITIONS}
    if set(cells) != expected:
        raise ValueError("H7 campaign factor coverage differs from the frozen matrix")
    return cells


def _log_ratio_analysis(values: Sequence[float], *, label: str) -> dict[str, Any]:
    sign = _exact_two_sided_sign_test(values)
    mean_log = statistics.fmean(values)
    median_log = float(statistics.median(values))
    low, high = _bootstrap_mean_ci(values)
    return {
        "label": label,
        "resampling_unit": "MATCHED_FACTOR_BLOCK",
        "block_count": len(values),
        "mean_log_ratio": mean_log,
        "median_log_ratio": median_log,
        "geometric_mean_ratio": math.exp(mean_log),
        "median_ratio": math.exp(median_log),
        "bootstrap_95_ci_geometric_mean_ratio": [math.exp(low), math.exp(high)],
        "bootstrap_rounds": _BOOTSTRAP_ROUNDS,
        "bootstrap_seed": _BOOTSTRAP_SEED,
        "sign_test": sign,
    }


def analyze_rq7_confirmatory(campaign: GeneratedMigrationCampaignReport) -> dict[str, Any]:
    cells = _validated_cells(campaign)

    record_slopes: list[dict[str, Any]] = []
    x = [math.log2(record_count / _RECORD_COUNTS[0]) for record_count in _RECORD_COUNTS]
    for readers in _READERS:
        for transitions in _TRANSITIONS:
            medians = [cells[(record_count, readers, transitions)].migrate_median for record_count in _RECORD_COUNTS]
            slope = _simple_slope(x, [math.log(value) for value in medians])
            record_slopes.append(
                {
                    "readers": readers,
                    "transitions": transitions,
                    "log_cost_slope_per_record_doubling": slope,
                    "multiplicative_cost_ratio_per_doubling": math.exp(slope),
                    "cell_medians_ns": medians,
                }
            )
    slopes = [item["log_cost_slope_per_record_doubling"] for item in record_slopes]
    record_sign = _exact_two_sided_sign_test(slopes)
    slope_low, slope_high = _bootstrap_mean_ci(slopes)
    mean_slope = statistics.fmean(slopes)
    record_supported = bool(
        record_sign["p_two_sided"] is not None
        and record_sign["p_two_sided"] <= _ALPHA
        and slope_low > 0.0
    )
    record_effect = {
        "resampling_unit": "READER_X_TRANSITION_BLOCK",
        "block_count": len(slopes),
        "block_slopes": record_slopes,
        "mean_log_cost_slope_per_record_doubling": mean_slope,
        "median_log_cost_slope_per_record_doubling": float(statistics.median(slopes)),
        "geometric_mean_cost_ratio_per_record_doubling": math.exp(mean_slope),
        "bootstrap_95_ci_cost_ratio_per_doubling": [math.exp(slope_low), math.exp(slope_high)],
        "bootstrap_rounds": _BOOTSTRAP_ROUNDS,
        "bootstrap_seed": _BOOTSTRAP_SEED,
        "sign_test": record_sign,
        "confirmatory_decision_alpha_0_05": "SUPPORTED" if record_supported else "NOT_CONFIRMED",
    }

    reader_analyses: dict[str, dict[str, Any]] = {}
    reader_p_values: dict[str, float] = {}
    for target_reader in (4, 16):
        log_ratios = [
            math.log(cells[(record_count, target_reader, transitions)].migrate_median / cells[(record_count, 1, transitions)].migrate_median)
            for record_count in _RECORD_COUNTS
            for transitions in _TRANSITIONS
        ]
        label = f"readers_{target_reader}_vs_1"
        analysis = _log_ratio_analysis(log_ratios, label=label)
        reader_analyses[label] = analysis
        p_value = analysis["sign_test"]["p_two_sided"]
        if p_value is None:
            raise ValueError("reader-pressure sign test is undefined")
        reader_p_values[label] = float(p_value)
    reader_holm = holm_bonferroni(reader_p_values, alpha=_ALPHA).as_dict()
    corrected = {item["label"]: item for item in reader_holm["hypotheses"]}
    for label, analysis in reader_analyses.items():
        analysis["holm_bonferroni"] = corrected[label]
    reader_pressure = {
        "family": "RQ7_READER_PRESSURE_SENSITIVITY",
        "contrasts": reader_analyses,
        "multiple_comparison_correction": reader_holm,
        "truth_boundary": "A rejected reader-pressure contrast establishes sensitivity within the frozen matrix; it does not establish a universal concurrency law.",
    }

    transition_log_ratios = [
        math.log(cells[(record_count, readers, 100)].migrate_median / cells[(record_count, readers, 10)].migrate_median)
        for record_count in _RECORD_COUNTS
        for readers in _READERS
    ]
    transition_robustness = _log_ratio_analysis(transition_log_ratios, label="transitions_100_vs_10")
    transition_robustness["truth_boundary"] = (
        "This contrast detects systematic per-transition timing sensitivity to measurement-duration setting. "
        "A non-significant result is not an equivalence or no-effect proof."
    )

    ordered_cells = [cells[(record_count, readers, transitions)] for record_count in _RECORD_COUNTS for readers in _READERS for transitions in _TRANSITIONS]
    design: list[list[float]] = []
    response: list[float] = []
    for cell in ordered_cells:
        design.append(
            [
                1.0,
                math.log2(cell.record_count / _RECORD_COUNTS[0]),
                1.0 if cell.readers == 4 else 0.0,
                1.0 if cell.readers == 16 else 0.0,
                1.0 if cell.transitions == 100 else 0.0,
            ]
        )
        response.append(math.log(cell.migrate_median))
    coefficients, residuals, r_squared = _ols(design, response)
    coefficient_names = ("intercept_log_ns", "record_doubling", "readers_4_vs_1", "readers_16_vs_1", "transitions_100_vs_10")
    coefficient_map = dict(zip(coefficient_names, coefficients, strict=True))
    global_model = {
        "model": "ADDITIVE_OLS_ON_LOG_CELL_MEDIAN_COST",
        "inference_use": "DESCRIPTIVE_RESIDUAL_AND_EFFECT_SIZE_MODEL_ONLY",
        "formula": "ln(cell_median_ns) ~ record_doublings + I(readers=4) + I(readers=16) + I(transitions=100)",
        "cell_count": len(ordered_cells),
        "coefficients": coefficient_map,
        "multiplicative_effects": {
            "record_cost_ratio_per_doubling": math.exp(coefficient_map["record_doubling"]),
            "readers_4_vs_1_ratio": math.exp(coefficient_map["readers_4_vs_1"]),
            "readers_16_vs_1_ratio": math.exp(coefficient_map["readers_16_vs_1"]),
            "transitions_100_vs_10_ratio": math.exp(coefficient_map["transitions_100_vs_10"]),
        },
        "r_squared": r_squared,
        "rmse_log_cost": math.sqrt(statistics.fmean(value**2 for value in residuals)),
        "max_abs_log_residual": max(abs(value) for value in residuals),
        "residuals": [
            {
                "experiment_id": cell.experiment_id,
                "record_count": cell.record_count,
                "readers": cell.readers,
                "transitions": cell.transitions,
                "observed_median_ns": cell.migrate_median,
                "predicted_median_ns": math.exp(response[index] - residuals[index]),
                "log_residual": residuals[index],
            }
            for index, cell in enumerate(ordered_cells)
        ],
        "truth_boundary": "No p-values are derived from this OLS fit; confirmatory decisions use the predeclared matched-block analyses above.",
    }

    total_reader_observations = sum(row.reads for entry in campaign.entries for row in entry.report.rows)
    invalid_reader_observations = sum(row.invalid_reads for entry in campaign.entries for row in entry.report.rows)
    reader_safety = {
        "total_reader_observations": total_reader_observations,
        "invalid_reader_observations": invalid_reader_observations,
        "decision": "ZERO_INVALID_OBSERVATIONS_FOR_FROZEN_CAMPAIGN" if invalid_reader_observations == 0 else "FAILED",
        "truth_boundary": "Zero observed invalid immutable-reader generations supports only the executed frozen campaign; it is not a proof of all concurrent executions.",
    }

    h7_supported = record_supported and invalid_reader_observations == 0
    core = {
        "schema": SCHEMA,
        "study_id": campaign.study_id,
        "manifest_sha256": campaign.manifest_sha256,
        "campaign_sha256": campaign.campaign_sha256,
        "machine_profile_sha256": campaign.machine_profile_sha256,
        "machine_fingerprint_sha256": campaign.machine_fingerprint_sha256,
        "source_candidate_id": campaign.source_candidate_id,
        "target_candidate_id": campaign.target_candidate_id,
        "primary_metric": "migrate_validate_activate_ns_per",
        "analysis_unit": "CELL_MEDIAN_WITH_MATCHED_FACTOR_BLOCKS",
        "raw_repetitions_are_not_independent_workloads": True,
        "alpha": _ALPHA,
        "record_count_effect": record_effect,
        "reader_pressure_sensitivity": reader_pressure,
        "transition_count_robustness": transition_robustness,
        "global_log_cost_model": global_model,
        "reader_safety": reader_safety,
        "raw_cells": [cell.raw_dict() for cell in ordered_cells],
        "h7_decision": "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE" if h7_supported else "NOT_FULLY_CONFIRMED",
        "evidence_state": EVIDENCE_STATE,
        "truth_boundaries": [
            "The confirmatory unit is the matched factor block built from per-cell medians; the 10 timing repetitions inside a cell are not treated as independent workloads.",
            "The record-count test characterizes systematic direction/effect within six frozen reader×transition blocks and does not establish an asymptotic complexity law.",
            "Reader-pressure contrasts are Holm-Bonferroni corrected as one two-hypothesis confirmatory family.",
            "Transition-count sensitivity is a robustness contrast; non-significance cannot be interpreted as equivalence.",
            "All inference is scoped to one generated candidate pair, one workload, one machine/toolchain fingerprint and the frozen RQ7 matrix.",
            "Cross-machine generalization, concurrent-writer safety, production SLA behavior and superiority over another system remain unestablished."
        ],
    }
    return {**core, "analysis_sha256": _canonical_sha256(core)}
