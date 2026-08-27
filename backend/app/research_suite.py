from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import statistics
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_MAX_EXPERIMENTS = 100_000


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite_number(value: float, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True)
class FrozenExperiment:
    experiment_id: str
    study_id: str
    hypothesis: str
    metric: str
    lower_is_better: bool
    repetitions: int
    seeds: tuple[int, ...]
    factors: dict[str, Any]
    factor_sha256: str
    evidence_state: str = "FROZEN_EXPERIMENT_PLAN_NOT_EXECUTED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "study_id": self.study_id,
            "hypothesis": self.hypothesis,
            "metric": self.metric,
            "lower_is_better": self.lower_is_better,
            "repetitions": self.repetitions,
            "seeds": list(self.seeds),
            "factors": self.factors,
            "factor_sha256": self.factor_sha256,
            "evidence_state": self.evidence_state,
        }


@dataclass(frozen=True)
class ExperimentManifest:
    schema: str
    study_id: str
    hypothesis: str
    metric: str
    lower_is_better: bool
    repetitions: int
    seeds: tuple[int, ...]
    axes: dict[str, tuple[Any, ...]]
    experiments: tuple[FrozenExperiment, ...]
    manifest_sha256: str
    evidence_state: str = "FROZEN_EXPERIMENT_MATRIX_NOT_EXECUTED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "study_id": self.study_id,
            "hypothesis": self.hypothesis,
            "metric": self.metric,
            "lower_is_better": self.lower_is_better,
            "repetitions": self.repetitions,
            "seeds": list(self.seeds),
            "axes": {key: list(values) for key, values in self.axes.items()},
            "experiments": [item.as_dict() for item in self.experiments],
            "manifest_sha256": self.manifest_sha256,
            "evidence_state": self.evidence_state,
        }


def freeze_experiment_matrix(
    *,
    study_id: str,
    hypothesis: str,
    metric: str,
    lower_is_better: bool,
    repetitions: int,
    seeds: Sequence[int],
    axes: Mapping[str, Sequence[Any]],
    max_experiments: int = _MAX_EXPERIMENTS,
) -> ExperimentManifest:
    """Freeze a Cartesian experiment matrix into deterministic IDs.

    This function creates plans, not benchmark evidence. IDs depend only on the
    declared study contract and factor values, making manifests replayable and
    safe to cite from a paper/release without relying on wall-clock timestamps.
    """

    if not study_id.strip():
        raise ValueError("study_id cannot be empty")
    if not hypothesis.strip():
        raise ValueError("hypothesis cannot be empty")
    if not metric.strip():
        raise ValueError("metric cannot be empty")
    if repetitions < 1 or repetitions > 10_000:
        raise ValueError("repetitions must be in [1, 10000]")
    normalized_seeds = tuple(int(seed) for seed in seeds)
    if not normalized_seeds:
        raise ValueError("at least one seed is required")
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must be unique")
    if max_experiments < 1 or max_experiments > _MAX_EXPERIMENTS:
        raise ValueError(f"max_experiments must be in [1, {_MAX_EXPERIMENTS}]")
    if not axes:
        raise ValueError("at least one experiment axis is required")

    normalized_axes: dict[str, tuple[Any, ...]] = {}
    theoretical = 1
    for raw_name in sorted(axes):
        name = str(raw_name).strip()
        if not name:
            raise ValueError("axis name cannot be empty")
        values = tuple(axes[raw_name])
        if not values:
            raise ValueError(f"axis {name!r} cannot be empty")
        # Canonical JSON validation rejects opaque/non-serializable factors.
        for value in values:
            _canonical_json(value)
        normalized_axes[name] = values
        theoretical *= len(values)
        if theoretical > max_experiments:
            raise ValueError(
                f"experiment matrix expands to more than {max_experiments} combinations"
            )

    axis_names = tuple(normalized_axes)
    experiments: list[FrozenExperiment] = []
    for values in itertools.product(*(normalized_axes[name] for name in axis_names)):
        factors = dict(zip(axis_names, values, strict=True))
        factor_hash = _sha256(factors)
        identity = {
            "schema": "morpheus-experiment-id-v1",
            "study_id": study_id,
            "hypothesis": hypothesis,
            "metric": metric,
            "lower_is_better": bool(lower_is_better),
            "repetitions": repetitions,
            "seeds": normalized_seeds,
            "factors": factors,
        }
        experiment_hash = _sha256(identity)
        experiments.append(
            FrozenExperiment(
                experiment_id=f"mx-{experiment_hash[:20]}",
                study_id=study_id,
                hypothesis=hypothesis,
                metric=metric,
                lower_is_better=bool(lower_is_better),
                repetitions=repetitions,
                seeds=normalized_seeds,
                factors=factors,
                factor_sha256=factor_hash,
            )
        )

    manifest_without_hash = {
        "schema": "morpheus-experiment-manifest-v1",
        "study_id": study_id,
        "hypothesis": hypothesis,
        "metric": metric,
        "lower_is_better": bool(lower_is_better),
        "repetitions": repetitions,
        "seeds": normalized_seeds,
        "axes": normalized_axes,
        "experiment_ids": [item.experiment_id for item in experiments],
    }
    manifest_hash = _sha256(manifest_without_hash)
    return ExperimentManifest(
        schema="morpheus-experiment-manifest-v1",
        study_id=study_id,
        hypothesis=hypothesis,
        metric=metric,
        lower_is_better=bool(lower_is_better),
        repetitions=repetitions,
        seeds=normalized_seeds,
        axes=normalized_axes,
        experiments=tuple(experiments),
        manifest_sha256=manifest_hash,
    )


@dataclass(frozen=True)
class PairedObservation:
    label: str
    baseline: float
    treatment: float

    def validate(self) -> None:
        if not self.label.strip():
            raise ValueError("paired observation label cannot be empty")
        _finite_number(self.baseline, "baseline")
        _finite_number(self.treatment, "treatment")


@dataclass(frozen=True)
class PairedAnalysis:
    metric: str
    lower_is_better: bool
    sample_count: int
    wins: int
    ties: int
    losses: int
    win_rate_excluding_ties: float | None
    mean_improvement: float
    median_improvement: float
    mean_relative_improvement: float | None
    geometric_mean_treatment_over_baseline: float | None
    paired_effect_dz: float | None
    exact_sign_test_p_two_sided: float | None
    bootstrap_confidence: float
    bootstrap_mean_improvement_ci: tuple[float, float]
    bootstrap_rounds: int
    bootstrap_seed: int
    evidence_state: str = "ANALYZED_CALLER_SUPPLIED_PAIRED_MEASUREMENTS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "lower_is_better": self.lower_is_better,
            "sample_count": self.sample_count,
            "wins": self.wins,
            "ties": self.ties,
            "losses": self.losses,
            "win_rate_excluding_ties": self.win_rate_excluding_ties,
            "mean_improvement": self.mean_improvement,
            "median_improvement": self.median_improvement,
            "mean_relative_improvement": self.mean_relative_improvement,
            "geometric_mean_treatment_over_baseline": self.geometric_mean_treatment_over_baseline,
            "paired_effect_dz": self.paired_effect_dz,
            "exact_sign_test_p_two_sided": self.exact_sign_test_p_two_sided,
            "bootstrap_confidence": self.bootstrap_confidence,
            "bootstrap_mean_improvement_ci": list(self.bootstrap_mean_improvement_ci),
            "bootstrap_rounds": self.bootstrap_rounds,
            "bootstrap_seed": self.bootstrap_seed,
            "evidence_state": self.evidence_state,
            "truth_note": (
                "Statistics summarize caller-supplied paired measurements; MORPHEUS does not infer how those measurements were collected."
            ),
        }


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute quantile of empty values")
    if probability <= 0:
        return float(sorted_values[0])
    if probability >= 1:
        return float(sorted_values[-1])
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction)


def _two_sided_sign_test(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    tail = min(wins, losses)
    one_tail = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return min(1.0, 2.0 * one_tail)


def analyze_paired_measurements(
    *,
    metric: str,
    observations: Sequence[PairedObservation],
    lower_is_better: bool = True,
    bootstrap_rounds: int = 4_000,
    bootstrap_seed: int = 1337,
    confidence: float = 0.95,
    tie_tolerance: float = 1e-12,
) -> PairedAnalysis:
    """Analyze a paired benchmark comparison with deterministic resampling.

    Positive `improvement` always means the treatment is better, independent of
    metric direction. This keeps paper tables and automated claim checks from
    silently flipping signs between latency and throughput studies.
    """

    if not metric.strip():
        raise ValueError("metric cannot be empty")
    if len(observations) < 2:
        raise ValueError("at least two paired observations are required")
    if bootstrap_rounds < 100 or bootstrap_rounds > 100_000:
        raise ValueError("bootstrap_rounds must be in [100, 100000]")
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be between 0.5 and 1")
    if tie_tolerance < 0 or not math.isfinite(tie_tolerance):
        raise ValueError("tie_tolerance must be finite and non-negative")

    items = list(observations)
    for item in items:
        item.validate()

    improvements: list[float] = []
    relative: list[float] = []
    positive_ratios: list[float] = []
    wins = ties = losses = 0
    for item in items:
        baseline = float(item.baseline)
        treatment = float(item.treatment)
        improvement = baseline - treatment if lower_is_better else treatment - baseline
        improvements.append(improvement)
        if abs(improvement) <= tie_tolerance:
            ties += 1
        elif improvement > 0:
            wins += 1
        else:
            losses += 1
        if baseline != 0:
            relative.append(improvement / abs(baseline))
        if baseline > 0 and treatment > 0:
            positive_ratios.append(treatment / baseline)

    mean_improvement = statistics.fmean(improvements)
    median_improvement = statistics.median(improvements)
    stdev = statistics.stdev(improvements) if len(improvements) > 1 else 0.0
    effect_dz = mean_improvement / stdev if stdev > 0 else None

    rng = random.Random(int(bootstrap_seed))
    means: list[float] = []
    n = len(improvements)
    for _ in range(bootstrap_rounds):
        means.append(statistics.fmean(improvements[rng.randrange(n)] for _ in range(n)))
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    ci = (_quantile(means, alpha), _quantile(means, 1.0 - alpha))

    non_ties = wins + losses
    win_rate = wins / non_ties if non_ties else None
    mean_relative = statistics.fmean(relative) if relative else None
    geometric_ratio = (
        math.exp(statistics.fmean(math.log(value) for value in positive_ratios))
        if positive_ratios
        else None
    )

    return PairedAnalysis(
        metric=metric,
        lower_is_better=bool(lower_is_better),
        sample_count=n,
        wins=wins,
        ties=ties,
        losses=losses,
        win_rate_excluding_ties=win_rate,
        mean_improvement=mean_improvement,
        median_improvement=median_improvement,
        mean_relative_improvement=mean_relative,
        geometric_mean_treatment_over_baseline=geometric_ratio,
        paired_effect_dz=effect_dz,
        exact_sign_test_p_two_sided=_two_sided_sign_test(wins, losses),
        bootstrap_confidence=confidence,
        bootstrap_mean_improvement_ci=ci,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=int(bootstrap_seed),
    )
